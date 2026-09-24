import unittest

import numpy as np
import pandas as pd

from src.features.time_series import (
    BASELINE3_FEATURES,
    FEATURE_DEFINITIONS,
    OCCUPANCY_FEATURES,
    OCCUPANCY_TREATMENT_FEATURES,
    add_forecasting_features,
)
from src.forecasting.occupancy_ablation import moving_block_bootstrap_paired_improvement


class OccupancyFeatureTest(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2026-01-01", periods=61, freq="1min", tz="UTC")
        self.frame = pd.DataFrame(
            {
                "power_w": np.arange(61, dtype=float),
                "temperature_c": 25.0,
                "humidity_percent": 60.0,
                "voltage_v": 220.0,
                "current_a": 1.0,
                "occupancy_count": np.arange(61, dtype=float) % 6,
            },
            index=self.index,
        )

    def test_treatment_adalah_control_dengan_tambahan_occupancy(self):
        self.assertEqual(OCCUPANCY_TREATMENT_FEATURES[: len(BASELINE3_FEATURES)], BASELINE3_FEATURES)
        self.assertEqual(
            OCCUPANCY_TREATMENT_FEATURES[len(BASELINE3_FEATURES) :], OCCUPANCY_FEATURES
        )

    def test_occupancy_feature_tidak_menggunakan_future_value(self):
        original = add_forecasting_features(self.frame)
        changed = self.frame.copy()
        changed.loc[self.index[36] :, "occupancy_count"] = 99
        changed_features = add_forecasting_features(changed)
        for feature in OCCUPANCY_FEATURES:
            self.assertEqual(
                original.loc[self.index[35], feature],
                changed_features.loc[self.index[35], feature],
                feature,
            )

    def test_metadata_occupancy_feature_non_future(self):
        self.assertTrue(
            all(FEATURE_DEFINITIONS[name]["source_offset_max"] <= 0 for name in OCCUPANCY_FEATURES)
        )


class BlockBootstrapTest(unittest.TestCase):
    def test_bootstrap_berpasangan_deterministik(self):
        control = np.array([2.0, 3.0, 4.0, 5.0] * 20)
        treatment = control - 0.5
        first = moving_block_bootstrap_paired_improvement(
            control,
            treatment,
            block_size=8,
            iterations=100,
            confidence_level=0.95,
            random_seed=42,
        )
        second = moving_block_bootstrap_paired_improvement(
            control,
            treatment,
            block_size=8,
            iterations=100,
            confidence_level=0.95,
            random_seed=42,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["metric"], "mae_improvement_w")
        self.assertEqual(
            first["metric_definition"], "mae_control_minus_mae_treatment"
        )
        self.assertAlmostEqual(first["observed_mae_improvement_w"], 0.5)
        self.assertAlmostEqual(first["mae_improvement_ci_lower_w"], 0.5)
        self.assertAlmostEqual(first["mae_improvement_ci_upper_w"], 0.5)
        self.assertTrue(first["supports_positive_improvement"])

    def test_daftar_occupancy_terdiri_dari_sebelas_feature(self):
        self.assertEqual(len(OCCUPANCY_FEATURES), 11)


if __name__ == "__main__":
    unittest.main()
