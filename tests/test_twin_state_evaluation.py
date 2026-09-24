import csv
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from src.twin_state.evaluation import evaluate_canonical_state


FIELDNAMES = [
    "Timestamp",
    "DeviceID",
    "Suhu (C)",
    "Kelembaban (%)",
    "Tegangan (V)",
    "Arus (A)",
    "Daya (W)",
    "Jumlah Orang",
]

CONFIG = {
    "data": {"source_timezone": "UTC"},
    "canonical_state": {
        "schema_version": "1.0.0-research",
        "room_id": "unresolved",
        "validation_ranges": {
            "temperature_c": {"min": 0, "max": 60},
            "humidity_percent": {"min": 0, "max": 100},
            "voltage_v": {"min": 0, "max": 300},
            "current_a": {"min": 0, "max": 50},
            "power_w": {"min": 0, "max": 5000},
            "occupancy_count": {"min": 0, "max": 100},
        },
    },
    "preprocessing": {"gap_threshold_seconds": 60},
}


class TwinStateEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "sensor_data.csv"
        self.config = self.root / "experiment.yaml"
        with self.config.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(CONFIG, handle)
        with self.source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(FIELDNAMES)
            writer.writerows(
                [
                    ["2026-01-01 00:00:00.000000", "dev-1", "25", "60", "220", "1", "220", "0"],
                    ["2026-01-01 00:00:01.000000", "dev-1", "26", "61", "221", "1", "221", "1"],
                    ["invalid", "", "not-numeric", "62", "222", "1", "222", "1.5"],
                ]
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_pipeline_mengukur_schema_kualitas_dan_correctness(self):
        tables = self.root / "tables"
        metrics = self.root / "metrics"
        result = evaluate_canonical_state(
            input_path=self.source,
            config_path=self.config,
            tables_dir=tables,
            metrics_dir=metrics,
        )
        self.assertEqual(result["total_raw_records_evaluated"], 3)
        self.assertEqual(result["successful_canonical_transformations"], 3)
        self.assertEqual(result["failed_canonical_transformations"], 0)
        self.assertEqual(result["schema_conforming_records"], 3)
        self.assertEqual(result["determinism_failures"], 0)
        for name in (
            "canonical_state_evaluation.csv",
            "canonical_field_mapping.csv",
            "digital_twin_data_quality.csv",
        ):
            self.assertTrue((tables / name).is_file())
        manifest = json.loads(
            (metrics / "canonical_state_evaluation_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["summary"]["timestamp_validity_rate"], 2 / 3)
        self.assertEqual(
            manifest["summary"]["staleness_unavailable_records"], 3
        )


if __name__ == "__main__":
    unittest.main()
