"""Pipeline end-to-end untuk forecasting foundation Tahap 3."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import yaml

from src.evaluation.metrics import regression_metrics
from src.evaluation.temporal import build_temporal_split, classify_modeling_samples
from src.features.time_series import (
    BASELINE2_FEATURES,
    BASELINE3_FEATURES,
    FEATURE_DEFINITIONS,
    add_forecasting_features,
    add_power_target,
    resample_sensor_csv,
)


MODEL_FEATURES = {
    "historical_power_ridge": BASELINE2_FEATURES,
    "non_occupancy_multivariate_ridge": BASELINE3_FEATURES,
}


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _iso_utc(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def _write_csv(frame: pd.DataFrame, path: str | Path, *, index: bool = False) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    frame.to_csv(temporary, index=index)
    os.replace(temporary, destination)


def _power_profile(values: np.ndarray, source: str) -> dict[str, Any]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    return {
        "source": source,
        "count": len(finite),
        "mean_w": float(np.mean(finite)),
        "sample_std_w": float(np.std(finite, ddof=1)),
        "min_w": float(np.min(finite)),
        "p25_w": float(np.quantile(finite, 0.25)),
        "median_w": float(np.quantile(finite, 0.50)),
        "p75_w": float(np.quantile(finite, 0.75)),
        "max_w": float(np.max(finite)),
    }


def _fit_ridge_with_validation(
    samples: pd.DataFrame,
    features: Sequence[str],
    alphas: Sequence[float],
    model_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, np.ndarray]]:
    train = samples[samples["split"] == "train"]
    validation = samples[samples["split"] == "validation"]
    test = samples[samples["split"] == "test"]
    scaler = StandardScaler()
    train_x = scaler.fit_transform(train[list(features)])
    validation_x = scaler.transform(validation[list(features)])
    test_x = scaler.transform(test[list(features)])
    train_y = train["target_power_30m"].to_numpy()
    validation_y = validation["target_power_30m"].to_numpy()
    test_y = test["target_power_30m"].to_numpy()

    tuning_rows: list[dict[str, Any]] = []
    fitted: dict[float, Ridge] = {}
    for alpha in alphas:
        model = Ridge(alpha=float(alpha))
        model.fit(train_x, train_y)
        validation_prediction = model.predict(validation_x)
        metrics = regression_metrics(validation_y, validation_prediction)
        tuning_rows.append(
            {
                "model": model_name,
                "alpha": float(alpha),
                "selection_split": "validation",
                "validation_mae_w": metrics["mae"],
                "validation_rmse_w": metrics["rmse"],
                "validation_r2": metrics["r2"],
            }
        )
        fitted[float(alpha)] = model

    best_row = min(tuning_rows, key=lambda row: (row["validation_mae_w"], row["alpha"]))
    selected_alpha = float(best_row["alpha"])
    selected_model = fitted[selected_alpha]
    predictions = {
        "validation": selected_model.predict(validation_x),
        "test": selected_model.predict(test_x),
    }
    audit = {
        "selected_alpha": selected_alpha,
        "feature_count": len(features),
        "features": list(features),
        "scaler_fit_split": "train",
        "scaler_fit_rows": len(train),
        "scaler_fit_start_utc": _iso_utc(train.index.min()),
        "scaler_fit_end_utc": _iso_utc(train.index.max()),
        "scaler_mean": scaler.mean_.tolist(),
    }
    return audit, tuning_rows, predictions


def _build_figures(
    samples: pd.DataFrame,
    selected_model: str,
    predictions: np.ndarray,
    figures_dir: Path,
) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/new_jurnal_matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    test = samples[samples["split"] == "test"].copy()
    test["prediction"] = predictions
    figures_dir.mkdir(parents=True, exist_ok=True)

    first_timestamp = test.index.min()
    segment_end = first_timestamp + pd.Timedelta(days=7)
    segment = test.loc[test.index <= segment_end]
    display_index = pd.date_range(first_timestamp, segment_end, freq="1min", tz="UTC")
    actual = segment["target_power_30m"].reindex(display_index)
    predicted = segment["prediction"].reindex(display_index)

    fig, axis = plt.subplots(figsize=(13, 5))
    axis.plot(actual.index, actual, label="Actual power t+30", linewidth=1.1)
    axis.plot(predicted.index, predicted, label="Predicted power t+30", linewidth=1.0, alpha=0.85)
    axis.set_title(f"Actual vs predicted pada tujuh hari awal test — {selected_model}")
    axis.set_xlabel("Timestamp UTC")
    axis.set_ylabel("Power (W)")
    axis.legend()
    axis.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figures_dir / "forecast_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    errors = test["prediction"].to_numpy() - test["target_power_30m"].to_numpy()
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.hist(errors, bins=80, color="#2f6f9f", alpha=0.9)
    axis.axvline(0, color="black", linewidth=1)
    axis.set_title(f"Distribusi forecast error pada test — {selected_model}")
    axis.set_xlabel("Prediction − actual (W)")
    axis.set_ylabel("Jumlah sample")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figures_dir / "forecast_error_distribution.png", dpi=160)
    plt.close(fig)


def run_forecasting_foundation(
    *,
    input_path: str | Path,
    config_path: str | Path,
    features_config_path: str | Path,
    processed_output_path: str | Path,
    tables_dir: str | Path,
    metrics_dir: str | Path,
    figures_dir: str | Path,
) -> dict[str, Any]:
    """Jalankan seluruh Tahap 3 tanpa memakai occupancy sebagai feature."""

    with Path(config_path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with Path(features_config_path).open(encoding="utf-8") as handle:
        features_config = yaml.safe_load(handle)

    forecast_config = config["forecast"]
    evaluation_config = config["evaluation"]
    horizon = int(forecast_config["horizon_minutes"])
    cadence = int(forecast_config["cadence_minutes"])
    if cadence != 1:
        raise ValueError("implementasi Tahap 3 mensyaratkan cadence_minutes: 1")
    if features_config["model_feature_sets"]["historical_power_ridge"] != BASELINE2_FEATURES:
        raise ValueError("features.yaml tidak konsisten dengan historical power features")
    if features_config["model_feature_sets"]["non_occupancy_multivariate_ridge"] != BASELINE3_FEATURES:
        raise ValueError("features.yaml tidak konsisten dengan multivariate features")

    frame, resampling = resample_sensor_csv(input_path)
    raw_power_values = resampling.pop("raw_power_values")
    frame = add_power_target(frame, horizon_minutes=horizon)
    frame = add_forecasting_features(frame)

    split_labels, split_table = build_temporal_split(
        frame.index,
        train_fraction=float(evaluation_config["train_fraction"]),
        validation_fraction=float(evaluation_config["validation_fraction"]),
        test_fraction=float(evaluation_config["test_fraction"]),
    )
    frame = classify_modeling_samples(frame, split_labels, BASELINE3_FEATURES)
    usable = frame[frame["usable_for_modeling"]].copy()
    if usable.empty:
        raise ValueError("tidak ada sample usable setelah gap dan boundary handling")

    table_path = Path(tables_dir)
    metric_path = Path(metrics_dir)
    figure_path = Path(figures_dir)
    table_path.mkdir(parents=True, exist_ok=True)
    metric_path.mkdir(parents=True, exist_ok=True)

    reason_counts = frame["exclusion_reason"].value_counts().reindex(
        [
            "usable",
            "minute_bin_tanpa_telemetry",
            "minute_bin_tidak_lengkap",
            "feature_window_tidak_lengkap",
            "target_t_plus_30_tidak_tersedia",
            "forecast_horizon_melintasi_gap",
            "target_melintasi_split_boundary",
        ],
        fill_value=0,
    )
    summary_rows = [
        ("raw_records", resampling["raw_records"], "record", "Jumlah record CSV sebelum agregasi"),
        ("cadence_minutes", cadence, "menit", "Cadence modeling tetap"),
        ("minute_bins_total", resampling["minute_bins_total"], "bin", "Seluruh grid dari waktu awal sampai akhir"),
        ("minute_bins_with_telemetry", resampling["minute_bins_with_telemetry"], "bin", "Bin dengan minimal satu raw record"),
        ("minute_bins_complete", resampling["minute_bins_complete"], "bin", "Enam variabel hasil agregasi tersedia"),
        ("minute_bins_missing", resampling["minute_bins_missing"], "bin", "Bin tanpa telemetry; tetap missing"),
        ("minute_bins_partial", resampling["minute_bins_partial"], "bin", "Bin memiliki telemetry tetapi tidak lengkap"),
        ("candidate_state_times", len(frame), "sample", "Seluruh minute-bin sebelum eligibility"),
        ("usable_modeling_samples", len(usable), "sample", "Common sample untuk seluruh baseline"),
        ("samples_not_used", len(frame) - len(usable), "sample", "Tidak digunakan karena gap, feature window, target, atau boundary"),
        ("forecast_horizon_minutes", horizon, "menit", "Target tepat pada t+30 minute-bin"),
        ("occupancy_used_as_feature", "false", "boolean", "Occupancy ablation ditunda ke Tahap 4"),
    ]
    modeling_summary = pd.DataFrame(summary_rows, columns=["metric", "value", "unit", "description"])
    _write_csv(modeling_summary, table_path / "modeling_dataset_summary.csv")

    exclusions = pd.DataFrame(
        {
            "reason": reason_counts.index,
            "sample_count": reason_counts.values,
            "proportion_of_minute_bins": reason_counts.values / len(frame),
        }
    )
    _write_csv(exclusions, table_path / "sample_exclusion_summary.csv")

    minute_power_values = frame["power_w"].dropna().to_numpy()
    power_comparison = pd.DataFrame(
        [
            _power_profile(raw_power_values, "raw_record_power"),
            _power_profile(minute_power_values, "one_minute_mean_power"),
        ]
    )
    _write_csv(power_comparison, table_path / "power_resampling_comparison.csv")

    feature_rows = []
    for name in BASELINE3_FEATURES:
        definition = FEATURE_DEFINITIONS[name]
        feature_rows.append(
            {
                "feature": name,
                **definition,
                "used_by_historical_power_ridge": name in BASELINE2_FEATURES,
                "used_by_non_occupancy_multivariate_ridge": name in BASELINE3_FEATURES,
                "uses_occupancy": False,
            }
        )
    _write_csv(pd.DataFrame(feature_rows), table_path / "feature_definition.csv")

    split_counts = frame.groupby("split", observed=True).size().rename("minute_bins_observed")
    usable_counts = usable.groupby("split", observed=True).size().rename("usable_samples")
    crossed = (
        frame[frame["exclusion_reason"] == "target_melintasi_split_boundary"]
        .groupby("split", observed=True)
        .size()
        .rename("boundary_excluded_samples")
    )
    split_table = split_table.set_index("split").join([split_counts, usable_counts, crossed]).fillna(0)
    split_table["usable_samples"] = split_table["usable_samples"].astype(int)
    split_table["boundary_excluded_samples"] = split_table["boundary_excluded_samples"].astype(int)
    split_table["start_timestamp_utc"] = split_table["start_timestamp_utc"].map(_iso_utc)
    split_table["end_timestamp_utc"] = split_table["end_timestamp_utc"].map(_iso_utc)
    split_table = split_table.reset_index()
    _write_csv(split_table, table_path / "temporal_split.csv")

    ridge_alphas = [float(value) for value in forecast_config["ridge_alphas"]]
    prediction_store: dict[str, dict[str, np.ndarray]] = {}
    audit_store: dict[str, dict[str, Any]] = {}
    tuning_rows: list[dict[str, Any]] = []
    for model_name, feature_names in MODEL_FEATURES.items():
        audit, model_tuning, predictions = _fit_ridge_with_validation(
            usable, feature_names, ridge_alphas, model_name
        )
        audit_store[model_name] = audit
        tuning_rows.extend(model_tuning)
        prediction_store[model_name] = predictions
    _write_csv(pd.DataFrame(tuning_rows), table_path / "validation_tuning.csv")

    validation = usable[usable["split"] == "validation"]
    test = usable[usable["split"] == "test"]
    prediction_store["persistence"] = {
        "validation": validation["power_w"].to_numpy(),
        "test": test["power_w"].to_numpy(),
    }

    metric_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    model_order = ["persistence", "historical_power_ridge", "non_occupancy_multivariate_ridge"]
    metric_by_model: dict[str, dict[str, dict[str, float]]] = {}
    for model_name in model_order:
        metric_by_model[model_name] = {}
        for split_name, split_frame in (("validation", validation), ("test", test)):
            values = regression_metrics(
                split_frame["target_power_30m"], prediction_store[model_name][split_name]
            )
            metric_by_model[model_name][split_name] = values
            for metric_name, value in values.items():
                metric_rows.append(
                    {
                        "model": model_name,
                        "split": split_name,
                        "metric": metric_name,
                        "value": value,
                        "unit": "W" if metric_name in ("mae", "rmse") else "dimensionless",
                        "target": "target_power_30m",
                        "target_unit": "W",
                    }
                )

    selected_for_figure = min(
        model_order,
        key=lambda name: metric_by_model[name]["validation"]["mae"],
    )
    for model_name in model_order:
        audit = audit_store.get(model_name)
        comparison_rows.append(
            {
                "model": model_name,
                "feature_set": "current_power_only" if model_name == "persistence" else "|".join(audit["features"]),
                "selected_alpha": "" if audit is None else audit["selected_alpha"],
                "model_fit_split": "not_applicable" if audit is None else "train",
                "scaler_fit_split": "not_applicable" if audit is None else audit["scaler_fit_split"],
                "validation_mae_w": metric_by_model[model_name]["validation"]["mae"],
                "validation_rmse_w": metric_by_model[model_name]["validation"]["rmse"],
                "validation_r2": metric_by_model[model_name]["validation"]["r2"],
                "test_mae_w": metric_by_model[model_name]["test"]["mae"],
                "test_rmse_w": metric_by_model[model_name]["test"]["rmse"],
                "test_r2": metric_by_model[model_name]["test"]["r2"],
                "selected_from_validation_for_figures": model_name == selected_for_figure,
            }
        )
    _write_csv(pd.DataFrame(comparison_rows), table_path / "baseline_model_comparison.csv")
    _write_csv(pd.DataFrame(metric_rows), metric_path / "forecast_metrics.csv")

    test_predictions = pd.DataFrame(
        {
            "timestamp_utc": [_iso_utc(value) for value in test.index],
            "target_timestamp_utc": test["target_timestamp_utc"].map(_iso_utc).to_numpy(),
            "actual_power_w": test["target_power_30m"].to_numpy(),
            "current_power_w": test["power_w"].to_numpy(),
            "persistence_prediction_w": prediction_store["persistence"]["test"],
            "historical_power_ridge_prediction_w": prediction_store["historical_power_ridge"]["test"],
            "non_occupancy_multivariate_ridge_prediction_w": prediction_store[
                "non_occupancy_multivariate_ridge"
            ]["test"],
        }
    )
    _write_csv(test_predictions, metric_path / "test_predictions.csv")

    processed = frame.reset_index()
    processed["timestamp_utc"] = processed["timestamp_utc"].map(_iso_utc)
    processed["target_timestamp_utc"] = processed["target_timestamp_utc"].map(_iso_utc)
    _write_csv(processed, processed_output_path)

    _build_figures(
        usable,
        selected_for_figure,
        prediction_store[selected_for_figure]["test"],
        figure_path,
    )

    code_files = [
        Path(__file__),
        Path(__file__).parents[1] / "features" / "time_series.py",
        Path(__file__).parents[1] / "evaluation" / "temporal.py",
        Path(__file__).parents[1] / "evaluation" / "metrics.py",
    ]
    manifest = {
        "stage": 3,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": Path(input_path).name,
        "input_sha256": _sha256(input_path),
        "config_sha256": _sha256(config_path),
        "features_config_sha256": _sha256(features_config_path),
        "code_sha256": {str(path.relative_to(Path.cwd())): _sha256(path) for path in code_files},
        "random_seed": config["random_seed"],
        "cadence_minutes": cadence,
        "horizon_minutes": horizon,
        "occupancy_feature_used": False,
        "common_usable_samples": len(usable),
        "selected_for_figures_by_validation_mae": selected_for_figure,
        "ridge_audit": audit_store,
    }
    manifest_path = metric_path / "forecast_run_manifest.json"
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary_manifest, manifest_path)

    return {
        "raw_records": resampling["raw_records"],
        "minute_bins": len(frame),
        "missing_bins": resampling["minute_bins_missing"],
        "usable_samples": len(usable),
        "samples_not_used": len(frame) - len(usable),
        "split_boundaries": split_table.to_dict(orient="records"),
        "selected_for_figures": selected_for_figure,
        "test_metrics": {name: metric_by_model[name]["test"] for name in model_order},
    }
