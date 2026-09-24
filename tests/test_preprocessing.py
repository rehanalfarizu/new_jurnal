import csv
from pathlib import Path
import tempfile
import unittest

from src.preprocessing.pipeline import analyze_dataset, write_canonical_dataset


CONFIG = {
    "data": {"source_timezone": "UTC"},
    "canonical_state": {
        "schema_version": "1.0.0-research",
        "room_id": "unresolved",
        "validation_ranges": {
            "temperature_c": {"min": 0, "max": 60, "source": "test"},
            "humidity_percent": {"min": 0, "max": 100, "source": "test"},
            "voltage_v": {"min": 0, "max": 300, "source": "test"},
            "current_a": {"min": 0, "max": 50, "source": "test"},
            "power_w": {"min": 0, "max": 5000, "source": "test"},
            "occupancy_count": {"min": 0, "max": 100, "source": "test"},
        },
    },
    "preprocessing": {"gap_threshold_seconds": 60},
}

FIELDNAMES = [
    "Timestamp", "DeviceID", "Suhu (C)", "Kelembaban (%)",
    "Tegangan (V)", "Arus (A)", "Daya (W)", "Jumlah Orang",
]


class PreprocessingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "sensor_data.csv"
        rows = [
            ["2026-01-01 00:01:10.000000", "dev-1", "26", "60", "220", "1", "220", "1"],
            ["2026-01-01 00:00:01.000000", "dev-1", "27", "61", "221", "1", "221", "0"],
            ["2026-01-01 00:00:01.000000", "dev-1", "27", "61", "221", "1", "221", "0"],
            ["2026-01-01 00:00:00.000000", "dev-1", "28", "62", "222", "1", "", "101"],
        ]
        with self.source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(FIELDNAMES)
            writer.writerows(rows)

    def tearDown(self):
        self.temp.cleanup()

    def _read_metric(self, path, metric):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["metrik"] == metric:
                    return row["nilai"]
        self.fail(f"metrik tidak ditemukan: {metric}")

    def test_eksplorasi_menghitung_duplikasi_gap_dan_missing(self):
        output = self.root / "results"
        result = analyze_dataset(self.source, output, CONFIG)
        self.assertEqual(result["total_rows"], 4)
        self.assertFalse(result["chronological"])
        self.assertEqual(result["exact_duplicate_rows"], 1)
        self.assertEqual(result["duplicate_timestamp_rows"], 1)
        self.assertEqual(result["gap_count"], 1)
        self.assertEqual(self._read_metric(output / "data_quality_summary.csv", "missing_cells"), "1")

    def test_preprocessing_mengurutkan_dan_tidak_menghapus_record(self):
        output = self.root / "canonical.csv"
        result = write_canonical_dataset(self.source, output, CONFIG)
        self.assertEqual(result["rows_written"], 4)
        with output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4)
        timestamps = [row["timestamp_utc"] for row in rows]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(rows[-1]["source_row_number"], "2")


if __name__ == "__main__":
    unittest.main()
