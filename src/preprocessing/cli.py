"""Command-line interface untuk eksplorasi dan preprocessing Tahap 2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import analyze_dataset, load_stage2_config, write_canonical_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Eksplorasi, validasi, dan canonicalisasi dataset sensor smart-room."
    )
    parser.add_argument("--config", default="configs/experiment.yaml", help="Path konfigurasi YAML")
    subparsers = parser.add_subparsers(dest="command", required=True)

    explore = subparsers.add_parser("explore", help="Buat tabel eksplorasi dan kualitas data")
    explore.add_argument("--input", required=True, help="Path sensor_data.csv")
    explore.add_argument("--output-dir", default="results/tables", help="Direktori tabel hasil")

    preprocess = subparsers.add_parser("preprocess", help="Tulis CSV canonical terurut")
    preprocess.add_argument("--input", required=True, help="Path sensor_data.csv")
    preprocess.add_argument(
        "--output",
        default="data/processed/canonical_sensor_data.csv",
        help="Path keluaran canonical CSV",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_stage2_config(Path(args.config))
    if args.command == "explore":
        result = analyze_dataset(args.input, args.output_dir, config)
    else:
        result = write_canonical_dataset(args.input, args.output, config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
