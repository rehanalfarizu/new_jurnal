#!/usr/bin/env python3
"""Verify that metrics reproduce within tolerance from frozen predictions.

This script recomputes MAE, RMSE and R2 from the held-out prediction files
WITHOUT calling fit(). It compares against the stored metrics and reports
the absolute difference.

Residual sign convention used elsewhere: prediction - actual.
Negative residual means underprediction (actual > predicted).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(actual: Any, predicted: Any) -> dict[str, float]:
    """Compute MAE, RMSE, R2 using the same functions as the main pipeline."""
    y_true = np.asarray(actual, dtype=float)
    y_pred = np.asarray(predicted, dtype=float)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def load_csv(path: Path) -> list[dict[str, str]]:
    """Load CSV as list of dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_stored_metrics(path: Path) -> dict[tuple[str, str], float]:
    """Load stored metrics as {(model, metric): value}."""
    rows = load_csv(path)
    result = {}
    for row in rows:
        if row.get("split") == "test":
            model = row["model"]
            metric = row["metric"]
            value = float(row["value"])
            result[(model, metric)] = value
    return result


def main() -> int:
    root = Path(__file__).resolve().parent.parent

    # Load prediction files
    test_pred_path = root / "results" / "metrics" / "test_predictions.csv"
    ablation_pred_path = root / "results" / "metrics" / "occupancy_ablation_test_predictions.csv"

    test_pred = load_csv(test_pred_path)
    ablation_pred = load_csv(ablation_pred_path)

    # Extract arrays from test_predictions.csv
    actual = np.array([float(r["actual_power_w"]) for r in test_pred])
    persistence_pred = np.array([float(r["persistence_prediction_w"]) for r in test_pred])
    historical_pred = np.array([float(r["historical_power_ridge_prediction_w"]) for r in test_pred])
    non_occ_pred = np.array([float(r["non_occupancy_multivariate_ridge_prediction_w"]) for r in test_pred])

    # Extract arrays from ablation file (test split only)
    ablation_test = [r for r in ablation_pred if r["split"] == "test"]
    ablation_actual = np.array([float(r["actual_power_w"]) for r in ablation_test])
    control_pred = np.array([float(r["control_prediction_w"]) for r in ablation_test])
    treatment_pred = np.array([float(r["treatment_prediction_w"]) for r in ablation_test])

    # Verify arrays match
    assert len(actual) == len(ablation_actual), "Test sample count mismatch"
    assert np.allclose(actual, ablation_actual), "Actual values mismatch between files"
    assert np.allclose(non_occ_pred, control_pred), "Control prediction mismatch"

    # Recompute metrics
    recomputed = {
        ("persistence", "test"): regression_metrics(actual, persistence_pred),
        ("historical_power_ridge", "test"): regression_metrics(actual, historical_pred),
        ("non_occupancy_multivariate_ridge", "test"): regression_metrics(actual, non_occ_pred),
        ("occupancy_multivariate_ridge", "test"): regression_metrics(ablation_actual, treatment_pred),
    }

    # Also compute control metrics from ablation file for cross-check
    control_metrics = regression_metrics(ablation_actual, control_pred)

    # Load stored metrics
    stored_forecast = load_stored_metrics(root / "results" / "metrics" / "forecast_metrics.csv")
    stored_ablation = {}
    ablation_rows = load_csv(root / "results" / "metrics" / "occupancy_ablation_metrics.csv")
    for row in ablation_rows:
        if row.get("split") == "test":
            model = row["model"]
            metric = row["metric"]
            stored_ablation[(model, metric)] = float(row["value"])

    # Compare and collect differences
    comparisons = []
    max_abs_diff = 0.0

    model_mapping = {
        "persistence": "persistence",
        "historical_power_ridge": "historical_power_ridge",
        "non_occupancy_multivariate_ridge": "non_occupancy_multivariate_ridge",
    }

    # Stage 3 models from forecast_metrics.csv
    for model_key, model_stored in model_mapping.items():
        for metric in ["mae", "rmse", "r2"]:
            recomp_val = recomputed[(model_key, "test")][metric]
            stored_val = stored_forecast.get((model_stored, metric))
            if stored_val is not None:
                diff = abs(recomp_val - stored_val)
                max_abs_diff = max(max_abs_diff, diff)
                comparisons.append({
                    "model": model_key,
                    "metric": metric,
                    "stored_value": stored_val,
                    "recomputed_value": recomp_val,
                    "abs_diff": diff,
                    "source": "forecast_metrics.csv",
                })

    # Stage 4 models from occupancy_ablation_metrics.csv
    for model_key, role in [("non_occupancy_multivariate_ridge", "control"),
                            ("occupancy_multivariate_ridge", "treatment")]:
        for metric in ["mae", "rmse", "r2"]:
            if model_key == "non_occupancy_multivariate_ridge":
                recomp_val = control_metrics[metric]
            else:
                recomp_val = recomputed[(model_key, "test")][metric]
            stored_val = stored_ablation.get((model_key, metric))
            if stored_val is not None:
                diff = abs(recomp_val - stored_val)
                max_abs_diff = max(max_abs_diff, diff)
                comparisons.append({
                    "model": f"{model_key} ({role})",
                    "metric": metric,
                    "stored_value": stored_val,
                    "recomputed_value": recomp_val,
                    "abs_diff": diff,
                    "source": "occupancy_ablation_metrics.csv",
                })

    # MAE improvement check
    stored_improvement = None
    bootstrap_path = root / "results" / "metrics" / "occupancy_ablation_bootstrap.csv"
    bootstrap_rows = load_csv(bootstrap_path)
    if bootstrap_rows:
        stored_improvement = float(bootstrap_rows[0]["observed_mae_improvement_w"])

    control_mae = control_metrics["mae"]
    treatment_mae = recomputed[("occupancy_multivariate_ridge", "test")]["mae"]
    recomputed_improvement = control_mae - treatment_mae

    improvement_diff = abs(recomputed_improvement - stored_improvement) if stored_improvement else None
    if improvement_diff is not None:
        max_abs_diff = max(max_abs_diff, improvement_diff)
        comparisons.append({
            "model": "mae_improvement",
            "metric": "control_minus_treatment",
            "stored_value": stored_improvement,
            "recomputed_value": recomputed_improvement,
            "abs_diff": improvement_diff,
            "source": "occupancy_ablation_bootstrap.csv",
        })

    # Determine pass/fail
    tolerance = 1e-9
    passed = max_abs_diff <= tolerance

    # Print results
    print("=" * 70)
    print("REPRODUCTION CHECK RESULTS")
    print("=" * 70)
    print(f"\nTolerance: {tolerance}")
    print(f"Max absolute difference: {max_abs_diff:.2e}")
    print(f"Status: {'PASS' if passed else 'FAIL'}")
    print("\nPer-metric comparison:")
    print("-" * 70)
    for c in comparisons:
        status = "OK" if c["abs_diff"] <= tolerance else "DIFF"
        print(f"  {c['model']:45} {c['metric']:6} diff={c['abs_diff']:.2e} [{status}]")
    print("-" * 70)

    # Write CSV output
    output_csv = root / "results" / "tables" / "reproduction_check.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "metric", "stored_value",
                                                "recomputed_value", "abs_diff", "source"])
        writer.writeheader()
        writer.writerows(comparisons)
    print(f"\nWrote: {output_csv}")

    # Write JSON output
    output_json = root / "results" / "metrics" / "reproduction_check.json"
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python scripts/verify_reproduction.py",
        "tolerance": tolerance,
        "max_abs_diff": max_abs_diff,
        "pass": passed,
        "test_sample_count": len(actual),
        "comparisons_count": len(comparisons),
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote: {output_json}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
