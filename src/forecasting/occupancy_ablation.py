"""Occupancy ablation study dengan control dan treatment yang berpasangan."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.evaluation.metrics import regression_metrics
from src.evaluation.temporal import build_temporal_split, classify_modeling_samples
from src.features.time_series import (
    BASELINE3_FEATURES,
    FEATURE_DEFINITIONS,
    OCCUPANCY_FEATURES,
    OCCUPANCY_TREATMENT_FEATURES,
    add_forecasting_features,
    add_power_target,
    resample_sensor_csv,
)
from src.forecasting.pipeline import (
    _iso_utc,
    _sha256,
    _write_csv,
    fit_ridge_with_validation,
)


CONTROL_MODEL = "non_occupancy_multivariate_ridge"
TREATMENT_MODEL = "occupancy_multivariate_ridge"


def moving_block_bootstrap_paired_improvement(
    control_absolute_error: np.ndarray,
    treatment_absolute_error: np.ndarray,
    *,
    block_size: int,
    iterations: int,
    confidence_level: float,
    random_seed: int,
) -> dict[str, Any]:
    """Estimasi CI improvement MAE dengan moving block bootstrap berpasangan.

    Improvement didefinisikan sebagai absolute error control dikurangi absolute
    error treatment. Nilai positif berarti treatment menurunkan MAE.
    """

    control = np.asarray(control_absolute_error, dtype=float)
    treatment = np.asarray(treatment_absolute_error, dtype=float)
    if control.shape != treatment.shape or control.ndim != 1:
        raise ValueError("error control dan treatment harus berupa vektor berpasangan")
    if len(control) == 0:
        raise ValueError("bootstrap memerlukan minimal satu sample")
    if iterations <= 0 or block_size <= 0:
        raise ValueError("iterations dan block_size harus positif")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level harus berada di antara 0 dan 1")

    paired_improvement = control - treatment
    effective_block_size = min(block_size, len(paired_improvement))
    block_count = math.ceil(len(paired_improvement) / effective_block_size)
    maximum_start = len(paired_improvement) - effective_block_size
    rng = np.random.default_rng(random_seed)
    bootstrap_means = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        starts = rng.integers(0, maximum_start + 1, size=block_count)
        sampled = np.concatenate(
            [
                paired_improvement[start : start + effective_block_size]
                for start in starts
            ]
        )[: len(paired_improvement)]
        bootstrap_means[iteration] = sampled.mean()

    alpha = (1 - confidence_level) / 2
    lower, upper = np.quantile(bootstrap_means, [alpha, 1 - alpha])
    return {
        "method": "moving_block_bootstrap_paired_absolute_error_improvement",
        "metric": "mae_improvement_w",
        "metric_definition": "mae_control_minus_mae_treatment",
        "block_size_samples": effective_block_size,
        "iterations": iterations,
        "confidence_level": confidence_level,
        "observed_mae_improvement_w": float(paired_improvement.mean()),
        "mae_improvement_ci_lower_w": float(lower),
        "mae_improvement_ci_upper_w": float(upper),
        "supports_positive_improvement": bool(lower > 0),
    }


def _build_ablation_figures(
    comparison: pd.DataFrame,
    occupancy_error: pd.DataFrame,
    figures_dir: Path,
) -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/new_jurnal_matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    labels = ["Control\nwithout occupancy", "Treatment\nwith occupancy"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    x = np.arange(2)
    width = 0.35
    axes[0].bar(x - width / 2, comparison["test_mae_w"], width, label="MAE")
    axes[0].bar(x + width / 2, comparison["test_rmse_w"], width, label="RMSE")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Error (W)")
    axes[0].set_title("Test error")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(x, comparison["test_r2"], color=["#6c8ebf", "#82b366"])
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("R²")
    axes[1].set_title("Test R²")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Occupancy ablation pada common test samples")
    fig.tight_layout()
    fig.savefig(figures_dir / "occupancy_ablation_comparison.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 5))
    positions = np.arange(len(occupancy_error))
    axis.plot(
        positions,
        occupancy_error["control_mae_w"],
        marker="o",
        label="Control without occupancy",
    )
    axis.plot(
        positions,
        occupancy_error["treatment_mae_w"],
        marker="o",
        label="Treatment with occupancy",
    )
    axis.set_xticks(positions, occupancy_error["occupancy_count"].astype(int))
    axis.set_xlabel("Occupancy count pada waktu t")
    axis.set_ylabel("MAE (W)")
    axis.set_title("Test MAE berdasarkan occupancy level")
    axis.legend()
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figures_dir / "occupancy_level_error.png", dpi=160)
    plt.close(fig)


def _git_metadata(repository_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {"git_commit": commit, "working_tree_dirty": dirty}


def run_occupancy_ablation(
    *,
    input_path: str | Path,
    config_path: str | Path = "configs/experiment.yaml",
    features_config_path: str | Path = "configs/features.yaml",
    processed_output_path: str | Path = "data/processed/modeling_1min.csv",
    tables_dir: str | Path = "results/tables",
    metrics_dir: str | Path = "results/metrics",
    figures_dir: str | Path = "results/figures",
) -> dict[str, Any]:
    """Jalankan control-versus-treatment occupancy ablation secara fair."""

    config_path = Path(config_path)
    features_config_path = Path(features_config_path)
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with features_config_path.open(encoding="utf-8") as handle:
        feature_config = yaml.safe_load(handle)

    configured_control = feature_config["model_feature_sets"][CONTROL_MODEL]
    configured_treatment = feature_config["model_feature_sets"][TREATMENT_MODEL]
    if configured_control != BASELINE3_FEATURES:
        raise ValueError("control feature set tidak konsisten dengan source code")
    if configured_treatment != OCCUPANCY_TREATMENT_FEATURES:
        raise ValueError("treatment feature set tidak konsisten dengan source code")

    horizon = int(config["forecast"]["horizon_minutes"])
    frame, resampling = resample_sensor_csv(input_path)
    resampling.pop("raw_power_values")
    frame = add_power_target(frame, horizon_minutes=horizon)
    frame = add_forecasting_features(frame)
    split_labels, split_table = build_temporal_split(
        frame.index,
        train_fraction=float(config["evaluation"]["train_fraction"]),
        validation_fraction=float(config["evaluation"]["validation_fraction"]),
        test_fraction=float(config["evaluation"]["test_fraction"]),
    )
    frame = classify_modeling_samples(frame, split_labels, OCCUPANCY_TREATMENT_FEATURES)
    usable = frame[frame["usable_for_modeling"]].copy()
    if usable.empty:
        raise ValueError("tidak ada common sample untuk occupancy ablation")

    alphas = [float(value) for value in config["forecast"]["ridge_alphas"]]
    control_audit, control_tuning, control_predictions = fit_ridge_with_validation(
        usable, BASELINE3_FEATURES, alphas, CONTROL_MODEL
    )
    treatment_audit, treatment_tuning, treatment_predictions = fit_ridge_with_validation(
        usable, OCCUPANCY_TREATMENT_FEATURES, alphas, TREATMENT_MODEL
    )
    audits = {CONTROL_MODEL: control_audit, TREATMENT_MODEL: treatment_audit}
    prediction_store = {
        CONTROL_MODEL: control_predictions,
        TREATMENT_MODEL: treatment_predictions,
    }

    metric_store: dict[str, dict[str, dict[str, float]]] = {}
    metric_rows: list[dict[str, Any]] = []
    for model_name in (CONTROL_MODEL, TREATMENT_MODEL):
        metric_store[model_name] = {}
        for split_name in ("validation", "test"):
            split_frame = usable[usable["split"] == split_name]
            metrics = regression_metrics(
                split_frame["target_power_30m"], prediction_store[model_name][split_name]
            )
            metric_store[model_name][split_name] = metrics
            for metric_name, value in metrics.items():
                metric_rows.append(
                    {
                        "model": model_name,
                        "role": "control" if model_name == CONTROL_MODEL else "treatment",
                        "split": split_name,
                        "metric": metric_name,
                        "value": value,
                        "unit": "W" if metric_name in ("mae", "rmse") else "dimensionless",
                        "target": "target_power_30m",
                    }
                )

    control_test = metric_store[CONTROL_MODEL]["test"]
    treatment_test = metric_store[TREATMENT_MODEL]["test"]
    comparison_rows = []
    for model_name, role in ((CONTROL_MODEL, "control"), (TREATMENT_MODEL, "treatment")):
        test_metrics = metric_store[model_name]["test"]
        validation_metrics = metric_store[model_name]["validation"]
        comparison_rows.append(
            {
                "model": model_name,
                "role": role,
                "feature_count": audits[model_name]["feature_count"],
                "occupancy_feature_count": 0 if role == "control" else len(OCCUPANCY_FEATURES),
                "selected_alpha": audits[model_name]["selected_alpha"],
                "validation_mae_w": validation_metrics["mae"],
                "validation_rmse_w": validation_metrics["rmse"],
                "validation_r2": validation_metrics["r2"],
                "test_mae_w": test_metrics["mae"],
                "test_rmse_w": test_metrics["rmse"],
                "test_r2": test_metrics["r2"],
                "delta_mae_w_vs_control": test_metrics["mae"] - control_test["mae"],
                "delta_rmse_w_vs_control": test_metrics["rmse"] - control_test["rmse"],
                "delta_r2_vs_control": test_metrics["r2"] - control_test["r2"],
                "mae_improvement_w_vs_control": control_test["mae"] - test_metrics["mae"],
                "mae_percentage_improvement": (
                    (control_test["mae"] - test_metrics["mae"]) / control_test["mae"] * 100
                ),
            }
        )
    comparison = pd.DataFrame(comparison_rows)

    test = usable[usable["split"] == "test"].copy()
    test["control_prediction_w"] = control_predictions["test"]
    test["treatment_prediction_w"] = treatment_predictions["test"]
    test["control_absolute_error_w"] = (
        test["control_prediction_w"] - test["target_power_30m"]
    ).abs()
    test["treatment_absolute_error_w"] = (
        test["treatment_prediction_w"] - test["target_power_30m"]
    ).abs()

    occupancy_rows = []
    for occupancy, group in test.groupby("occupancy_count", sort=True):
        occupancy_rows.append(
            {
                "occupancy_count": int(occupancy),
                "sample_count": len(group),
                "control_mae_w": group["control_absolute_error_w"].mean(),
                "treatment_mae_w": group["treatment_absolute_error_w"].mean(),
                "difference_treatment_minus_control_w": (
                    group["treatment_absolute_error_w"].mean()
                    - group["control_absolute_error_w"].mean()
                ),
            }
        )
    occupancy_error = pd.DataFrame(occupancy_rows)

    uncertainty = config["occupancy_ablation"]["uncertainty"]
    bootstrap = moving_block_bootstrap_paired_improvement(
        test["control_absolute_error_w"].to_numpy(),
        test["treatment_absolute_error_w"].to_numpy(),
        block_size=int(uncertainty["block_size_samples"]),
        iterations=int(uncertainty["iterations"]),
        confidence_level=float(uncertainty["confidence_level"]),
        random_seed=int(config["random_seed"]),
    )

    control_view = usable.loc[
        usable[BASELINE3_FEATURES + ["target_power_30m", "split"]].notna().all(axis=1)
    ]
    treatment_view = usable.loc[
        usable[OCCUPANCY_TREATMENT_FEATURES + ["target_power_30m", "split"]]
        .notna()
        .all(axis=1)
    ]
    timestamps_equal = control_view.index.equals(treatment_view.index)
    targets_equal = timestamps_equal and control_view["target_power_30m"].equals(
        treatment_view["target_power_30m"]
    )
    splits_equal = timestamps_equal and control_view["split"].equals(treatment_view["split"])
    control_alphas = [float(row["alpha"]) for row in control_tuning]
    treatment_alphas = [float(row["alpha"]) for row in treatment_tuning]
    fair_checks = pd.DataFrame(
        [
            {"check": "control_sample_timestamp_equals_treatment", "passed": timestamps_equal, "detail": f"{len(control_view)} control dan {len(treatment_view)} treatment samples"},
            {"check": "control_target_equals_treatment", "passed": targets_equal, "detail": "Target dibandingkan setelah alignment timestamp"},
            {"check": "control_split_equals_treatment", "passed": splits_equal, "detail": "Label split dibandingkan setelah alignment timestamp"},
            {"check": "model_family_equal", "passed": True, "detail": "Ridge untuk control dan treatment"},
            {"check": "tuning_budget_equal", "passed": control_alphas == treatment_alphas, "detail": json.dumps(control_alphas)},
            {"check": "preprocessing_policy_equal", "passed": True, "detail": "Satu resampling, target, gap policy, dan sample mask digunakan bersama"},
        ]
    )
    if not bool(fair_checks["passed"].all()):
        raise AssertionError("fair ablation check gagal")

    tables_path = Path(tables_dir)
    metrics_path = Path(metrics_dir)
    figures_path = Path(figures_dir)
    tables_path.mkdir(parents=True, exist_ok=True)
    metrics_path.mkdir(parents=True, exist_ok=True)
    _write_csv(comparison, tables_path / "occupancy_ablation_comparison.csv")
    _write_csv(occupancy_error, tables_path / "occupancy_level_error.csv")
    _write_csv(fair_checks, tables_path / "fair_ablation_check.csv")
    _write_csv(
        pd.DataFrame(control_tuning + treatment_tuning),
        tables_path / "occupancy_ablation_validation_tuning.csv",
    )
    _write_csv(pd.DataFrame([bootstrap]), metrics_path / "occupancy_ablation_bootstrap.csv")
    _write_csv(pd.DataFrame(metric_rows), metrics_path / "occupancy_ablation_metrics.csv")

    predictions = pd.DataFrame(
        {
            "timestamp_utc": [_iso_utc(value) for value in test.index],
            "target_timestamp_utc": test["target_timestamp_utc"].map(_iso_utc).to_numpy(),
            "split": test["split"].to_numpy(),
            "occupancy_count": test["occupancy_count"].astype(int).to_numpy(),
            "actual_power_w": test["target_power_30m"].to_numpy(),
            "control_prediction_w": test["control_prediction_w"].to_numpy(),
            "treatment_prediction_w": test["treatment_prediction_w"].to_numpy(),
            "control_absolute_error_w": test["control_absolute_error_w"].to_numpy(),
            "treatment_absolute_error_w": test["treatment_absolute_error_w"].to_numpy(),
        }
    )
    _write_csv(predictions, metrics_path / "occupancy_ablation_test_predictions.csv")

    feature_rows = []
    for feature in OCCUPANCY_TREATMENT_FEATURES:
        feature_rows.append(
            {
                "feature": feature,
                **FEATURE_DEFINITIONS[feature],
                "used_by_control": feature in BASELINE3_FEATURES,
                "used_by_treatment": True,
                "occupancy_feature": feature in OCCUPANCY_FEATURES,
            }
        )
    _write_csv(pd.DataFrame(feature_rows), tables_path / "occupancy_ablation_feature_definition.csv")

    processed = frame.reset_index()
    processed["timestamp_utc"] = processed["timestamp_utc"].map(_iso_utc)
    processed["target_timestamp_utc"] = processed["target_timestamp_utc"].map(_iso_utc)
    _write_csv(processed, processed_output_path)
    _build_ablation_figures(comparison, occupancy_error, figures_path)

    repository_root = Path.cwd().resolve()
    code_files = [
        Path(__file__),
        Path(__file__).parents[1] / "features" / "time_series.py",
        Path(__file__).parent / "pipeline.py",
        Path(__file__).parents[1] / "evaluation" / "temporal.py",
    ]
    manifest = {
        "stage": 4,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": config["occupancy_ablation"]["research_question"],
        "input_file": Path(input_path).name,
        "input_sha256": _sha256(input_path),
        "config_sha256": _sha256(config_path),
        "features_config_sha256": _sha256(features_config_path),
        "code_sha256": {str(path.relative_to(repository_root)): _sha256(path) for path in code_files},
        **_git_metadata(repository_root),
        "python_random_seed": int(config["random_seed"]),
        "cadence_minutes": int(config["forecast"]["cadence_minutes"]),
        "forecast_horizon_minutes": horizon,
        "split": split_table.assign(
            start_timestamp_utc=lambda data: data["start_timestamp_utc"].map(_iso_utc),
            end_timestamp_utc=lambda data: data["end_timestamp_utc"].map(_iso_utc),
        ).to_dict(orient="records"),
        "common_usable_samples": len(usable),
        "raw_records": int(resampling["raw_records"]),
        "minute_bins": len(frame),
        "excluded_samples": len(frame) - len(usable),
        "control_audit": control_audit,
        "treatment_audit": treatment_audit,
        "fair_ablation_all_passed": bool(fair_checks["passed"].all()),
        "bootstrap": bootstrap,
        "official_outputs": {
            "comparison": str(tables_path / "occupancy_ablation_comparison.csv"),
            "occupancy_level_error": str(tables_path / "occupancy_level_error.csv"),
            "fair_check": str(tables_path / "fair_ablation_check.csv"),
            "metrics": str(metrics_path / "occupancy_ablation_metrics.csv"),
            "bootstrap": str(metrics_path / "occupancy_ablation_bootstrap.csv"),
            "predictions": str(metrics_path / "occupancy_ablation_test_predictions.csv"),
            "comparison_figure": str(figures_path / "occupancy_ablation_comparison.png"),
            "occupancy_error_figure": str(figures_path / "occupancy_level_error.png"),
        },
    }
    manifest_path = metrics_path / "occupancy_ablation_manifest.json"
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary_manifest, manifest_path)

    return {
        "dataset_sha256": manifest["input_sha256"],
        "raw_records": resampling["raw_records"],
        "minute_bins": len(frame),
        "usable_samples": len(usable),
        "excluded_samples": len(frame) - len(usable),
        "control": {**control_audit, **metric_store[CONTROL_MODEL]},
        "treatment": {**treatment_audit, **metric_store[TREATMENT_MODEL]},
        "fair_ablation_all_passed": bool(fair_checks["passed"].all()),
        "bootstrap": bootstrap,
        "output_paths": manifest["official_outputs"],
    }
