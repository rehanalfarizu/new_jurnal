"""CLI untuk Decision-Support Scenario Evaluation Tahap 6."""

from __future__ import annotations

import argparse
import json

from .evaluation import run_decision_support_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Jalankan Decision-Support Scenario Evaluation dari output resmi Tahap 4."
    )
    parser.add_argument(
        "--predictions",
        default="results/metrics/occupancy_ablation_test_predictions.csv",
    )
    parser.add_argument("--modeling-state", default="data/processed/modeling_1min.csv")
    parser.add_argument("--experiment-config", default="configs/experiment.yaml")
    parser.add_argument("--decision-config", default="configs/decision_support.yaml")
    parser.add_argument("--device-summary", default="results/tables/device_summary.csv")
    parser.add_argument(
        "--stage4-manifest", default="results/metrics/occupancy_ablation_manifest.json"
    )
    parser.add_argument(
        "--stage5-manifest",
        default="results/metrics/canonical_state_evaluation_manifest.json",
    )
    parser.add_argument("--tables-dir", default="results/tables")
    parser.add_argument("--metrics-dir", default="results/metrics")
    parser.add_argument("--figures-dir", default="results/figures")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = run_decision_support_evaluation(
        predictions_path=args.predictions,
        modeling_path=args.modeling_state,
        experiment_config_path=args.experiment_config,
        decision_config_path=args.decision_config,
        device_summary_path=args.device_summary,
        stage4_manifest_path=args.stage4_manifest,
        stage5_manifest_path=args.stage5_manifest,
        tables_dir=args.tables_dir,
        metrics_dir=args.metrics_dir,
        figures_dir=args.figures_dir,
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
