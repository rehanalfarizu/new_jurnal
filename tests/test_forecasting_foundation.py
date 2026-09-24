import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.evaluation.temporal import build_temporal_split, classify_modeling_samples
from src.features.time_series import (
    BASELINE2_FEATURES,
    BASELINE3_FEATURES,
    FEATURE_DEFINITIONS,
    add_forecasting_features,
    add_power_target,
    resample_sensor_csv,
)
from src.forecasting.pipeline import fit_ridge_with_validation


FIELDNAMES = [
    "Timestamp", "DeviceID", "Suhu (C)", "Kelembaban (%)",
    "Tegangan (V)", "Arus (A)", "Daya (W)", "Jumlah Orang",
]


class ResamplingTest(unittest.TestCase):
    def test_agregasi_satu_menit_dan_bin_kosong(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sensor_data.csv"
            rows = [
                ["2026-01-01 00:00:01.000000", "dev", "20", "50", "220", "1", "100", "1"],
                ["2026-01-01 00:00:59.000000", "dev", "22", "52", "222", "3", "200", "2"],
                ["2026-01-01 00:02:00.000000", "dev", "24", "54", "224", "5", "300", "3"],
            ]
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(FIELDNAMES)
                writer.writerows(rows)
            frame, metadata = resample_sensor_csv(path)

        self.assertEqual(metadata["raw_records"], 3)
        self.assertEqual(metadata["minute_bins_total"], 3)
        self.assertEqual(metadata["minute_bins_missing"], 1)
        self.assertEqual(frame.iloc[0]["power_w"], 150.0)
        self.assertEqual(frame.iloc[0]["occupancy_count"], 2.0)
        self.assertTrue(np.isnan(frame.iloc[1]["power_w"]))


class TargetAndFeatureTest(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2026-01-01", periods=61, freq="1min", tz="UTC")
        self.frame = pd.DataFrame(
            {
                "power_w": np.arange(61, dtype=float),
                "temperature_c": 25.0,
                "humidity_percent": 60.0,
                "voltage_v": 220.0,
                "current_a": 1.0,
                "occupancy_count": 0.0,
                "raw_record_count": 1,
                "has_telemetry": True,
                "complete_bin": True,
            },
            index=self.index,
        )

    def test_target_tepat_tiga_puluh_menit_bukan_row_raw(self):
        frame = self.frame.copy()
        frame.loc[self.index[30], "power_w"] = np.nan
        targeted = add_power_target(frame, horizon_minutes=30)
        self.assertTrue(np.isnan(targeted.loc[self.index[0], "target_power_30m"]))
        self.assertEqual(targeted.loc[self.index[1], "target_power_30m"], 31.0)
        self.assertEqual(
            targeted.loc[self.index[1], "target_timestamp_utc"], self.index[31]
        )

    def test_horizon_yang_melintasi_bin_kosong_tidak_usable(self):
        frame = self.frame.copy()
        frame.loc[self.index[15], "has_telemetry"] = False
        frame.loc[self.index[15], "complete_bin"] = False
        frame.loc[self.index[15], "power_w"] = np.nan
        targeted = add_power_target(frame, horizon_minutes=30)
        labels, _boundaries = build_temporal_split(targeted.index)
        classified = classify_modeling_samples(targeted, labels, ["power_w"])
        self.assertFalse(classified.loc[self.index[0], "usable_for_modeling"])
        self.assertEqual(
            classified.loc[self.index[0], "exclusion_reason"],
            "forecast_horizon_melintasi_gap",
        )

    def test_rolling_feature_tidak_berubah_oleh_future_value(self):
        original = add_forecasting_features(self.frame)
        changed = self.frame.copy()
        changed.loc[self.index[36] :, "power_w"] = 9999.0
        changed_features = add_forecasting_features(changed)
        for feature in BASELINE2_FEATURES:
            self.assertEqual(
                original.loc[self.index[35], feature],
                changed_features.loc[self.index[35], feature],
                feature,
            )

    def test_semua_feature_memiliki_offset_maksimum_non_future(self):
        self.assertTrue(
            all(FEATURE_DEFINITIONS[name]["source_offset_max"] <= 0 for name in BASELINE3_FEATURES)
        )


class TemporalSplitTest(unittest.TestCase):
    def test_split_kronologis_dan_target_tidak_melintasi_boundary(self):
        index = pd.date_range("2026-01-01", periods=200, freq="1min", tz="UTC")
        frame = pd.DataFrame(
            {
                "power_w": np.arange(200, dtype=float),
                "has_telemetry": True,
                "complete_bin": True,
            },
            index=index,
        )
        frame = add_power_target(frame, horizon_minutes=5)
        labels, boundaries = build_temporal_split(index)
        classified = classify_modeling_samples(frame, labels, ["power_w"])

        self.assertEqual(boundaries.iloc[0]["end_timestamp_utc"], index[139])
        self.assertEqual(boundaries.iloc[1]["start_timestamp_utc"], index[140])
        self.assertEqual(boundaries.iloc[2]["start_timestamp_utc"], index[170])
        self.assertEqual(
            classified.loc[index[135], "exclusion_reason"],
            "target_melintasi_split_boundary",
        )
        self.assertTrue(classified.loc[index[134], "usable_for_modeling"])
        usable = classified[classified["usable_for_modeling"]]
        self.assertTrue((usable["split"] == usable["target_split"]).all())

    def test_scaler_hanya_fit_pada_train(self):
        index = pd.date_range("2026-01-01", periods=20, freq="1min", tz="UTC")
        samples = pd.DataFrame(index=index)
        for feature in BASELINE2_FEATURES:
            samples[feature] = np.arange(20, dtype=float)
        samples["target_power_30m"] = np.arange(20, dtype=float) * 2
        samples["split"] = ["train"] * 10 + ["validation"] * 5 + ["test"] * 5
        audit, _tuning, _predictions = fit_ridge_with_validation(
            samples,
            BASELINE2_FEATURES,
            [1.0],
            "test_model",
        )
        self.assertEqual(audit["scaler_fit_split"], "train")
        self.assertEqual(audit["scaler_fit_rows"], 10)
        self.assertAlmostEqual(audit["scaler_mean"][0], 4.5)


if __name__ == "__main__":
    unittest.main()
