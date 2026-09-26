import json
from pathlib import Path
import unittest

from src.decision_support.engine import (
    DecisionSupportEngine,
    DecisionSupportInput,
    detect_contradictions,
)


CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "decision_support.yaml"


class DecisionSupportEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = DecisionSupportEngine.from_yaml(CONFIG_PATH)

    @staticmethod
    def state(**overrides):
        values = {
            "timestamp_utc": "2026-05-10T16:39:00Z",
            "occupancy_count": 1,
            "current_power_w": 35.0,
            "forecast_power_30m_w": 35.5,
            "temperature_c": 28.0,
            "humidity_percent": 60.0,
            "device_id": "RASPBERRY_PI_GATEWAY_001",
            "room_id": "unresolved",
        }
        values.update(overrides)
        return DecisionSupportInput(**values)

    def test_unoccupied_elevated_power_memicu_rule_001(self):
        result = self.engine.evaluate(
            self.state(occupancy_count=0, current_power_w=40.1, forecast_power_30m_w=39.0)
        )
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-001"])
        self.assertIn("40.000000 W", result[0]["reason"])

    def test_forecast_delta_memicu_rule_002_dan_tercatat(self):
        result = self.engine.evaluate(
            self.state(current_power_w=35.0, forecast_power_30m_w=37.1)
        )
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-002"])
        self.assertAlmostEqual(result[0]["input_state"]["forecast_delta_w"], 2.1)

    def test_occupied_environment_memicu_rule_003(self):
        result = self.engine.evaluate(self.state(temperature_c=32.1))
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-003"])
        self.assertIn("threshold skenario", result[0]["reason"])

    def test_threshold_bersifat_strict_greater_than(self):
        result = self.engine.evaluate(
            self.state(
                occupancy_count=0,
                current_power_w=40.0,
                forecast_power_30m_w=40.0,
                temperature_c=32.0,
                humidity_percent=75.0,
            )
        )
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-004"])

    def test_setiap_recommendation_memiliki_reason_dan_threshold_trace(self):
        result = self.engine.evaluate(
            self.state(
                occupancy_count=1,
                current_power_w=35.0,
                forecast_power_30m_w=38.0,
                temperature_c=33.0,
            )
        )
        self.assertGreaterEqual(len(result), 2)
        for item in result:
            self.assertTrue(item["reason"].strip())
            self.assertTrue(item["threshold_configuration"])
            self.assertTrue(item["recommendation_id"].startswith("DS-"))

    def test_missing_occupancy_berbeda_dari_occupancy_nol(self):
        missing = self.engine.evaluate(self.state(occupancy_count=None))
        zero = self.engine.evaluate(self.state(occupancy_count=0))
        self.assertEqual(missing[0]["rule_id"], "DS-RULE-000")
        self.assertNotEqual(missing, zero)
        self.assertIn("occupancy_count_missing", missing[0]["reason"])

    def test_missing_forecast_tidak_dianggap_nol(self):
        result = self.engine.evaluate(self.state(forecast_power_30m_w=None))
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-000"])
        self.assertIsNone(result[0]["input_state"]["forecast_delta_w"])
        self.assertIn("forecast_power_30m_w_missing", result[0]["reason"])

    def test_input_non_finite_ditangani(self):
        result = self.engine.evaluate(self.state(current_power_w=float("nan")))
        self.assertEqual(result[0]["rule_id"], "DS-RULE-000")
        self.assertIn("current_power_w_invalid", result[0]["reason"])

    def test_no_action_dapat_dihasilkan(self):
        result = self.engine.evaluate(self.state())
        self.assertEqual([item["rule_id"] for item in result], ["DS-RULE-004"])
        self.assertEqual(result[0]["action_class"], "no_action")

    def test_output_deterministik(self):
        state = self.state(current_power_w=35.0, forecast_power_30m_w=38.0)
        first = self.engine.evaluate(state)
        second = self.engine.evaluate(state)
        self.assertEqual(
            json.dumps(first, sort_keys=True, ensure_ascii=False),
            json.dumps(second, sort_keys=True, ensure_ascii=False),
        )

    def test_recommendation_kontradiktif_terdeteksi(self):
        recommendations = [
            {"rule_id": "DS-RULE-001", "action_class": "inspect_active_load"},
            {"rule_id": "DS-RULE-004", "action_class": "no_action"},
        ]
        self.assertEqual(
            detect_contradictions(recommendations),
            ["no_action_with_active_recommendation"],
        )


if __name__ == "__main__":
    unittest.main()
