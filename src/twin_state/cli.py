"""CLI evaluasi empiris Canonical Twin State Tahap 5."""

from __future__ import annotations

import argparse
import json

from .evaluation import evaluate_canonical_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluasi schema, completeness, temporal integrity, dan kualitas Canonical Twin State."
    )
    parser.add_argument("--input", required=True, help="Path sensor_data.csv")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--tables-dir", default="results/tables")
    parser.add_argument("--metrics-dir", default="results/metrics")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = evaluate_canonical_state(
        input_path=args.input,
        config_path=args.config,
        tables_dir=args.tables_dir,
        metrics_dir=args.metrics_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
