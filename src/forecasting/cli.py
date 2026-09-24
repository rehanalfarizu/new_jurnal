"""CLI Tahap 3 untuk forecasting foundation."""

from __future__ import annotations

import argparse
import json

from .pipeline import run_forecasting_foundation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bangun time series satu menit dan evaluasi baseline forecasting non-occupancy."
    )
    parser.add_argument("--input", required=True, help="Path sensor_data.csv")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--features-config", default="configs/features.yaml")
    parser.add_argument("--processed-output", default="data/processed/modeling_1min.csv")
    parser.add_argument("--tables-dir", default="results/tables")
    parser.add_argument("--metrics-dir", default="results/metrics")
    parser.add_argument("--figures-dir", default="results/figures")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_forecasting_foundation(
        input_path=args.input,
        config_path=args.config,
        features_config_path=args.features_config,
        processed_output_path=args.processed_output,
        tables_dir=args.tables_dir,
        metrics_dir=args.metrics_dir,
        figures_dir=args.figures_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
