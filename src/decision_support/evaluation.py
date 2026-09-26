"""Pipeline Decision-Support Scenario Evaluation Tahap 6."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from src.twin_state.canonical import UNRESOLVED_ROOM_ID

from .engine import DecisionSupportEngine, DecisionSupportInput, load_decision_support_config


SCENARIO_COLUMNS = [
    "sample_id",
    "recommendation_id",
    "timestamp_utc",
    "target_timestamp_utc",
    "split",
    "schema_version",
    "room_id",
    "device_id",
    "occupancy_count",
    "current_power_w",
    "forecast_power_30m_w",
    "forecast_delta_w",
    "temperature_c",
    "humidity_percent",
    "rule_id",
    "rule_name",
    "threshold_configuration_json",
    "recommendation_text",
    "reason",
    "severity",
    "priority",
    "action_class",
    "contradiction_detected",
    "contradiction_reasons_json",
    "input_state_json",
    "source_forecast_model",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


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


def _sample_id(timestamp_utc: str) -> str:
    return "SAMPLE-" + hashlib.sha256(timestamp_utc.encode("utf-8")).hexdigest()[:16].upper()


def _load_single_device_id(path: Path) -> tuple[str | None, str]:
    if not path.is_file():
        return None, "device_summary_unavailable"
    frame = pd.read_csv(path)
    if "device_id" not in frame.columns or len(frame) != 1:
        return None, "device_id_not_uniquely_resolved"
    device_id = str(frame.iloc[0]["device_id"]).strip()
    if not device_id:
        return None, "device_id_empty"
    return device_id, "single_device_from_stage_2_summary"


def _time_period(timestamp: pd.Timestamp, periods: Sequence[Mapping[str, Any]]) -> str:
    hour = int(timestamp.hour)
    for period in periods:
        if int(period["start_hour_inclusive"]) <= hour < int(period["end_hour_exclusive"]):
            return str(period["name"])
    raise ValueError(f"hour UTC {hour} tidak tercakup konfigurasi time period")


def load_decision_support_inputs(
    *,
    predictions_path: str | Path,
    modeling_path: str | Path,
    experiment_config_path: str | Path,
    decision_config: Mapping[str, Any],
    device_summary_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Gabungkan output forecast Tahap 4 dan state saat ini secara one-to-one."""

    predictions_path = Path(predictions_path)
    modeling_path = Path(modeling_path)
    if not predictions_path.is_file():
        raise FileNotFoundError(f"output forecast tidak ditemukan: {predictions_path}")
    if not modeling_path.is_file():
        raise FileNotFoundError(
            f"modeling dataset tidak ditemukan: {modeling_path}; jalankan ulang Tahap 4 bila perlu"
        )

    with Path(experiment_config_path).open(encoding="utf-8") as handle:
        experiment_config = yaml.safe_load(handle)
    schema_version = str(experiment_config["canonical_state"]["schema_version"])
    room_id = str(experiment_config["canonical_state"].get("room_id") or UNRESOLVED_ROOM_ID)
    device_id, device_resolution = _load_single_device_id(Path(device_summary_path))

    prediction_columns = [
        "timestamp_utc",
        "target_timestamp_utc",
        "split",
        "occupancy_count",
        "treatment_prediction_w",
    ]
    state_columns = [
        "timestamp_utc",
        "temperature_c",
        "humidity_percent",
        "power_w",
        "occupancy_count",
    ]
    predictions = pd.read_csv(predictions_path, usecols=prediction_columns)
    states = pd.read_csv(modeling_path, usecols=state_columns)
    prediction_duplicate_timestamps = int(predictions["timestamp_utc"].duplicated().sum())
    state_duplicate_timestamps = int(states["timestamp_utc"].duplicated().sum())
    if prediction_duplicate_timestamps:
        raise ValueError("output forecast memiliki duplicate timestamp")
    if state_duplicate_timestamps:
        raise ValueError("modeling dataset memiliki duplicate timestamp")

    expected_split = str(decision_config["input"]["evaluation_split"])
    unexpected_splits = sorted(set(predictions["split"].dropna().astype(str)) - {expected_split})
    if unexpected_splits:
        raise ValueError(f"output forecast memuat split di luar {expected_split}: {unexpected_splits}")

    merged = predictions.merge(
        states,
        on="timestamp_utc",
        how="left",
        validate="one_to_one",
        suffixes=("_forecast", "_state"),
        indicator=True,
    )
    unmatched_state_rows = int((merged["_merge"] != "both").sum())
    if unmatched_state_rows:
        raise ValueError(f"{unmatched_state_rows} timestamp forecast tidak memiliki state")
    merged.drop(columns="_merge", inplace=True)

    occupancy_mismatch = int(
        (
            merged["occupancy_count_forecast"].astype(float)
            != merged["occupancy_count_state"].astype(float)
        ).sum()
    )
    if occupancy_mismatch:
        raise ValueError(f"occupancy forecast dan state berbeda pada {occupancy_mismatch} sample")

    merged.rename(
        columns={
            "occupancy_count_state": "occupancy_count",
            "power_w": "current_power_w",
            "treatment_prediction_w": "forecast_power_30m_w",
        },
        inplace=True,
    )
    merged.drop(columns="occupancy_count_forecast", inplace=True)
    merged["timestamp_utc"] = pd.to_datetime(merged["timestamp_utc"], utc=True)
    merged["target_timestamp_utc"] = pd.to_datetime(merged["target_timestamp_utc"], utc=True)
    merged.sort_values("timestamp_utc", inplace=True, kind="stable")
    merged.reset_index(drop=True, inplace=True)
    merged["room_id"] = room_id
    merged["device_id"] = device_id
    merged["schema_version"] = schema_version
    merged["forecast_delta_w"] = (
        merged["forecast_power_30m_w"] - merged["current_power_w"]
    )
    merged["time_period_utc"] = [
        _time_period(timestamp, decision_config["time_periods_utc"])
        for timestamp in merged["timestamp_utc"]
    ]

    required = [
        "timestamp_utc",
        "occupancy_count",
        "current_power_w",
        "forecast_power_30m_w",
        "temperature_c",
        "humidity_percent",
    ]
    metadata = {
        "prediction_rows": int(len(predictions)),
        "state_rows": int(len(states)),
        "merged_rows": int(len(merged)),
        "unmatched_state_rows": unmatched_state_rows,
        "occupancy_mismatch_rows": occupancy_mismatch,
        "prediction_duplicate_timestamps": prediction_duplicate_timestamps,
        "state_duplicate_timestamps": state_duplicate_timestamps,
        "missing_required_input_values": int(merged[required].isna().sum().sum()),
        "device_id": device_id,
        "device_resolution": device_resolution,
        "room_id": room_id,
        "room_resolution": (
            "unresolved_preserved_from_experiment_config"
            if room_id == UNRESOLVED_ROOM_ID
            else "configured_room_id"
        ),
        "schema_version": schema_version,
    }
    return merged, metadata


def _evaluate_frame(
    inputs: pd.DataFrame,
    engine: DecisionSupportEngine,
    forecast_model: str,
) -> tuple[pd.DataFrame, dict[str, list[dict[str, Any]]]]:
    rows: list[dict[str, Any]] = []
    traces: dict[str, list[dict[str, Any]]] = {}
    for record in inputs.itertuples(index=False):
        timestamp = record.timestamp_utc.isoformat().replace("+00:00", "Z")
        target_timestamp = record.target_timestamp_utc.isoformat().replace("+00:00", "Z")
        state = DecisionSupportInput(
            timestamp_utc=timestamp,
            occupancy_count=int(record.occupancy_count),
            current_power_w=float(record.current_power_w),
            forecast_power_30m_w=float(record.forecast_power_30m_w),
            temperature_c=float(record.temperature_c),
            humidity_percent=float(record.humidity_percent),
            device_id=record.device_id,
            room_id=record.room_id,
            schema_version=record.schema_version,
        )
        recommendations = engine.evaluate(state)
        sample_id = _sample_id(timestamp)
        traces[sample_id] = recommendations
        for recommendation in recommendations:
            input_state = recommendation["input_state"]
            rows.append(
                {
                    "sample_id": sample_id,
                    "recommendation_id": recommendation["recommendation_id"],
                    "timestamp_utc": recommendation["timestamp_utc"],
                    "target_timestamp_utc": target_timestamp,
                    "split": record.split,
                    "schema_version": input_state["schema_version"],
                    "room_id": input_state["room_id"],
                    "device_id": input_state["device_id"],
                    "occupancy_count": input_state["occupancy_count"],
                    "current_power_w": input_state["current_power_w"],
                    "forecast_power_30m_w": input_state["forecast_power_30m_w"],
                    "forecast_delta_w": input_state["forecast_delta_w"],
                    "temperature_c": input_state["temperature_c"],
                    "humidity_percent": input_state["humidity_percent"],
                    "rule_id": recommendation["rule_id"],
                    "rule_name": recommendation["rule_name"],
                    "threshold_configuration_json": json.dumps(
                        recommendation["threshold_configuration"],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "recommendation_text": recommendation["recommendation_text"],
                    "reason": recommendation["reason"],
                    "severity": recommendation["severity"],
                    "priority": recommendation["priority"],
                    "action_class": recommendation["action_class"],
                    "contradiction_detected": recommendation["contradiction_detected"],
                    "contradiction_reasons_json": json.dumps(
                        recommendation["contradiction_reasons"], separators=(",", ":")
                    ),
                    "input_state_json": json.dumps(
                        input_state,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "source_forecast_model": forecast_model,
                }
            )
    return pd.DataFrame(rows, columns=SCENARIO_COLUMNS), traces


def _consistency_table(
    inputs: pd.DataFrame,
    scenarios: pd.DataFrame,
    traces: Mapping[str, list[dict[str, Any]]],
    repeated_traces: Mapping[str, list[dict[str, Any]]],
    input_metadata: Mapping[str, Any],
) -> pd.DataFrame:
    deterministic_failures = sum(
        json.dumps(traces[key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        != json.dumps(repeated_traces[key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for key in traces
    )
    contradiction_samples = int(
        scenarios.loc[scenarios["contradiction_detected"], "sample_id"].nunique()
    )
    checks = [
        ("forecast_state_one_to_one_alignment", input_metadata["unmatched_state_rows"] == 0, input_metadata["unmatched_state_rows"], 0, "Setiap timestamp prediksi mempunyai satu state."),
        ("occupancy_value_alignment", input_metadata["occupancy_mismatch_rows"] == 0, input_metadata["occupancy_mismatch_rows"], 0, "Occupancy pada output forecast sama dengan modeling state."),
        ("required_input_completeness", input_metadata["missing_required_input_values"] == 0, input_metadata["missing_required_input_values"], 0, "Field input minimum tidak missing."),
        ("recommendation_reason_trace", bool(scenarios["reason"].fillna("").str.strip().ne("").all()), int(scenarios["reason"].fillna("").str.strip().eq("").sum()), 0, "Setiap recommendation memiliki reason."),
        ("threshold_configuration_trace", bool(scenarios["threshold_configuration_json"].fillna("").str.strip().ne("").all()), int(scenarios["threshold_configuration_json"].fillna("").str.strip().eq("").sum()), 0, "Setiap recommendation merekam konfigurasi rule."),
        ("recommendation_id_unique", not scenarios["recommendation_id"].duplicated().any(), int(scenarios["recommendation_id"].duplicated().sum()), 0, "Recommendation ID unik pada output resmi."),
        ("deterministic_output", deterministic_failures == 0, deterministic_failures, 0, "Input identik dievaluasi dua kali dengan hasil identik."),
        ("contradictory_recommendation_count", contradiction_samples == 0, contradiction_samples, 0, "Fallback no-action tidak muncul bersama active recommendation."),
        ("all_samples_receive_trace", scenarios["sample_id"].nunique() == len(inputs), int(scenarios["sample_id"].nunique()), int(len(inputs)), "Setiap sample menghasilkan minimal satu trace."),
    ]
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "observed_value": observed,
                "expected_value": expected,
                "detail": detail,
            }
            for check_id, passed, observed, expected, detail in checks
        ]
    )


def _rule_summary(
    scenarios: pd.DataFrame,
    config: Mapping[str, Any],
    sample_count: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    recommendation_count = len(scenarios)
    for rule in config["rules"].values():
        matched = scenarios[scenarios["rule_id"] == rule["rule_id"]]
        count = int(len(matched))
        rows.append(
            {
                "rule_id": rule["rule_id"],
                "rule_name": rule["name"],
                "action_class": rule["action_class"],
                "severity": rule["severity"],
                "priority": int(rule["priority"]),
                "threshold_basis": rule["threshold_basis"],
                "threshold_configuration_json": json.dumps(
                    {key: value for key, value in rule.items() if key not in {"recommendation_text", "name", "severity", "priority", "action_class"}},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "recommendation_text": rule["recommendation_text"],
                "recommendation_count": count,
                "sample_count": int(matched["sample_id"].nunique()),
                "sample_coverage": count / sample_count if sample_count else 0.0,
                "recommendation_share": count / recommendation_count if recommendation_count else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _distribution_summary(inputs: pd.DataFrame, scenarios: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    sample_action = scenarios.assign(is_action=scenarios["action_class"] != "no_action").groupby("sample_id")["is_action"].any()
    sample_frame = inputs.copy()
    sample_frame["timestamp_text"] = sample_frame["timestamp_utc"].map(lambda value: value.isoformat().replace("+00:00", "Z"))
    sample_frame["sample_id"] = sample_frame["timestamp_text"].map(_sample_id)
    sample_frame["has_action"] = sample_frame["sample_id"].map(sample_action).fillna(False).astype(bool)
    recommendation_counts = scenarios.groupby("sample_id").size()
    sample_frame["recommendation_count"] = sample_frame["sample_id"].map(recommendation_counts).fillna(0).astype(int)

    occupancy_distribution: dict[str, Any] = {}
    for occupancy, group in sample_frame.groupby("occupancy_count", sort=True):
        occupancy_distribution[str(int(occupancy))] = {
            "sample_count": int(len(group)),
            "samples_with_active_recommendation": int(group["has_action"].sum()),
            "no_action_count": int((~group["has_action"]).sum()),
            "recommendation_count": int(group["recommendation_count"].sum()),
        }

    period_distribution: dict[str, Any] = {}
    for period, group in sample_frame.groupby("time_period_utc", sort=False):
        period_distribution[str(period)] = {
            "sample_count": int(len(group)),
            "samples_with_active_recommendation": int(group["has_action"].sum()),
            "no_action_count": int((~group["has_action"]).sum()),
            "recommendation_count": int(group["recommendation_count"].sum()),
        }
    return occupancy_distribution, period_distribution


def _build_figures(
    inputs: pd.DataFrame,
    scenarios: pd.DataFrame,
    rule_summary: pd.DataFrame,
    figures_dir: Path,
) -> list[str]:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/new_jurnal_matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []

    fig, axis = plt.subplots(figsize=(9, 5))
    axis.bar(rule_summary["rule_id"], rule_summary["recommendation_count"], color="#4C78A8")
    axis.set_xlabel("Rule ID")
    axis.set_ylabel("Jumlah recommendation")
    axis.set_title("Frekuensi recommendation berdasarkan rule")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = figures_dir / "decision_support_rule_frequency.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    outputs.append(str(path))

    action_by_sample = scenarios.assign(is_action=scenarios["action_class"] != "no_action").groupby("sample_id")["is_action"].any()
    sample_frame = inputs[["timestamp_utc", "occupancy_count"]].copy()
    sample_frame["sample_id"] = sample_frame["timestamp_utc"].map(
        lambda value: _sample_id(value.isoformat().replace("+00:00", "Z"))
    )
    sample_frame["status"] = np.where(
        sample_frame["sample_id"].map(action_by_sample).fillna(False),
        "active recommendation",
        "no action",
    )
    pivot = sample_frame.groupby(["occupancy_count", "status"]).size().unstack(fill_value=0)
    pivot = pivot.reindex(columns=["active recommendation", "no action"], fill_value=0)
    fig, axis = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", stacked=True, ax=axis, color=["#F58518", "#9D9D9D"])
    axis.set_xlabel("Occupancy count")
    axis.set_ylabel("Jumlah sample")
    axis.set_title("Distribusi recommendation berdasarkan occupancy")
    axis.legend(title="Status")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = figures_dir / "decision_support_occupancy_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    outputs.append(str(path))

    groups = []
    labels = []
    for rule_id in rule_summary["rule_id"]:
        values = scenarios.loc[scenarios["rule_id"] == rule_id, "forecast_delta_w"].dropna().to_numpy()
        if len(values):
            groups.append(values)
            labels.append(rule_id)
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.boxplot(groups, tick_labels=labels, showfliers=False)
    axis.axhline(0, color="black", linewidth=0.8, alpha=0.6)
    axis.set_xlabel("Rule ID")
    axis.set_ylabel("forecast_delta_w (W)")
    axis.set_title("Forecast delta pada setiap kategori recommendation")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = figures_dir / "decision_support_forecast_delta.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    outputs.append(str(path))
    return outputs


def run_decision_support_evaluation(
    *,
    predictions_path: str | Path = "results/metrics/occupancy_ablation_test_predictions.csv",
    modeling_path: str | Path = "data/processed/modeling_1min.csv",
    experiment_config_path: str | Path = "configs/experiment.yaml",
    decision_config_path: str | Path = "configs/decision_support.yaml",
    device_summary_path: str | Path = "results/tables/device_summary.csv",
    stage4_manifest_path: str | Path = "results/metrics/occupancy_ablation_manifest.json",
    stage5_manifest_path: str | Path = "results/metrics/canonical_state_evaluation_manifest.json",
    tables_dir: str | Path = "results/tables",
    metrics_dir: str | Path = "results/metrics",
    figures_dir: str | Path = "results/figures",
) -> dict[str, Any]:
    """Jalankan evaluasi skenario tanpa melatih ulang model forecasting."""

    repository_root = Path.cwd().resolve()
    predictions_path = Path(predictions_path)
    modeling_path = Path(modeling_path)
    experiment_config_path = Path(experiment_config_path)
    decision_config_path = Path(decision_config_path)
    device_summary_path = Path(device_summary_path)
    stage4_manifest_path = Path(stage4_manifest_path)
    stage5_manifest_path = Path(stage5_manifest_path)
    tables_dir = Path(tables_dir)
    metrics_dir = Path(metrics_dir)
    figures_dir = Path(figures_dir)

    decision_config = load_decision_support_config(decision_config_path)
    engine = DecisionSupportEngine(decision_config)
    inputs, input_metadata = load_decision_support_inputs(
        predictions_path=predictions_path,
        modeling_path=modeling_path,
        experiment_config_path=experiment_config_path,
        decision_config=decision_config,
        device_summary_path=device_summary_path,
    )
    forecast_model = str(decision_config["input"]["forecast_model"])
    scenarios, traces = _evaluate_frame(inputs, engine, forecast_model)
    _repeated_scenarios, repeated_traces = _evaluate_frame(inputs, engine, forecast_model)

    sample_count = int(len(inputs))
    rule_summary = _rule_summary(scenarios, decision_config, sample_count)
    consistency = _consistency_table(
        inputs, scenarios, traces, repeated_traces, input_metadata
    )
    occupancy_distribution, period_distribution = _distribution_summary(inputs, scenarios)

    scenario_path = tables_dir / "decision_support_scenarios.csv"
    rule_summary_path = tables_dir / "decision_support_rule_summary.csv"
    consistency_path = tables_dir / "decision_support_consistency.csv"
    manifest_path = metrics_dir / "decision_support_manifest.json"
    _write_csv(scenario_path, scenarios)
    _write_csv(rule_summary_path, rule_summary)
    _write_csv(consistency_path, consistency)
    figure_paths = _build_figures(inputs, scenarios, rule_summary, figures_dir)

    no_action_count = int(
        scenarios.loc[scenarios["rule_id"] == "DS-RULE-004", "sample_id"].nunique()
    )
    active_sample_count = int(
        scenarios.loc[scenarios["action_class"] != "no_action", "sample_id"].nunique()
    )
    contradiction_count = int(
        scenarios.loc[scenarios["contradiction_detected"], "sample_id"].nunique()
    )
    invalid_input_count = int(
        scenarios.loc[scenarios["rule_id"] == "DS-RULE-000", "sample_id"].nunique()
    )
    multiple_recommendation_samples = int((scenarios.groupby("sample_id").size() > 1).sum())
    per_rule = {
        row.rule_id: int(row.recommendation_count)
        for row in rule_summary.itertuples(index=False)
    }

    with stage4_manifest_path.open(encoding="utf-8") as handle:
        stage4_manifest = json.load(handle)
    with stage5_manifest_path.open(encoding="utf-8") as handle:
        stage5_manifest = json.load(handle)
    raw_checksum_consistent = (
        stage4_manifest.get("input_sha256") == stage5_manifest.get("input_sha256")
    )
    manifest = {
        "stage": 6,
        "evaluation_name": decision_config["evaluation_name"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "official_stage_4_test_predictions_joined_to_stage_3_modeling_state",
        "forecast_model_retrained": False,
        "forecast_model": forecast_model,
        "forecast_horizon_minutes": int(decision_config["input"]["forecast_horizon_minutes"]),
        "forecast_delta_definition": "forecast_power_30m_w - current_power_w",
        "input_files": {
            "predictions": str(predictions_path),
            "modeling_state": str(modeling_path),
            "experiment_config": str(experiment_config_path),
            "decision_support_config": str(decision_config_path),
            "device_summary": str(device_summary_path),
            "stage_4_manifest": str(stage4_manifest_path),
            "stage_5_manifest": str(stage5_manifest_path),
        },
        "input_sha256": {
            "predictions": _sha256(predictions_path),
            "modeling_state": _sha256(modeling_path),
            "experiment_config": _sha256(experiment_config_path),
            "decision_support_config": _sha256(decision_config_path),
            "device_summary": _sha256(device_summary_path),
            "stage_4_manifest": _sha256(stage4_manifest_path),
            "stage_5_manifest": _sha256(stage5_manifest_path),
        },
        "output_sha256": {
            "scenarios": _sha256(scenario_path),
            "rule_summary": _sha256(rule_summary_path),
            "consistency": _sha256(consistency_path),
            "figures": {path: _sha256(Path(path)) for path in figure_paths},
        },
        "code_sha256": {
            "src/decision_support/engine.py": _sha256(repository_root / "src/decision_support/engine.py"),
            "src/decision_support/evaluation.py": _sha256(repository_root / "src/decision_support/evaluation.py"),
        },
        **_git_metadata(repository_root),
        "input_alignment": input_metadata,
        "raw_dataset_checksum_consistent_between_stage_4_and_stage_5": raw_checksum_consistent,
        "summary": {
            "evaluated_sample_count": sample_count,
            "recommendation_count": int(len(scenarios)),
            "active_recommendation_sample_count": active_sample_count,
            "recommendation_coverage": active_sample_count / sample_count if sample_count else 0.0,
            "no_action_count": no_action_count,
            "invalid_input_count": invalid_input_count,
            "multiple_recommendation_sample_count": multiple_recommendation_samples,
            "contradictory_recommendation_count": contradiction_count,
            "determinism_failure_count": int(
                consistency.loc[consistency["check_id"] == "deterministic_output", "observed_value"].iloc[0]
            ),
            "all_consistency_checks_passed": bool((consistency["status"] == "PASS").all()),
            "recommendation_count_by_rule": per_rule,
            "evaluation_start_timestamp_utc": inputs["timestamp_utc"].min().isoformat().replace("+00:00", "Z"),
            "evaluation_end_timestamp_utc": inputs["timestamp_utc"].max().isoformat().replace("+00:00", "Z"),
        },
        "occupancy_distribution": occupancy_distribution,
        "time_period_distribution_utc": period_distribution,
        "threshold_interpretation": "Semua threshold numerik rule operasional adalah declared research scenario threshold, bukan safety limit atau validated comfort standard.",
        "limitations": [
            "Recommendation belum diuji terhadap tindakan manusia.",
            "Tidak tersedia data accept/reject recommendation.",
            "Tidak tersedia measured post-recommendation energy outcome.",
            "Tidak dilakukan causal evaluation.",
            "Threshold belum mempunyai basis literatur dan diperlakukan sebagai declared research scenario threshold.",
            "Sistem tidak melakukan autonomous control.",
        ],
        "official_outputs": {
            "scenarios": str(scenario_path),
            "rule_summary": str(rule_summary_path),
            "consistency": str(consistency_path),
            "manifest": str(manifest_path),
            "figures": figure_paths,
        },
    }
    _write_json(manifest_path, manifest)
    return manifest
