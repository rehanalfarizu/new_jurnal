import unittest

from src.twin_state.canonical import CanonicalStateTransformer, parse_timestamp_utc


RANGES = {
    "temperature_c": {"min": 0, "max": 60},
    "humidity_percent": {"min": 0, "max": 100},
    "voltage_v": {"min": 0, "max": 300},
    "current_a": {"min": 0, "max": 50},
    "power_w": {"min": 0, "max": 5000},
    "occupancy_count": {"min": 0, "max": 100},
}


def raw_record(**overrides):
    record = {
        "Timestamp": "2026-02-23 23:14:43.896301",
        "DeviceID": "RASPBERRY_PI_GATEWAY_001",
        "Suhu (C)": "27.5",
        "Kelembaban (%)": "65",
        "Tegangan (V)": "220",
        "Arus (A)": "2.2",
        "Daya (W)": "484",
        "Jumlah Orang": "0",
    }
    record.update(overrides)
    return record


class TimestampUtcTest(unittest.TestCase):
    def test_naive_timestamp_dilokalisasi_tanpa_pergeseran(self):
        parsed, policy = parse_timestamp_utc("2026-02-23 23:14:43.896301")
        self.assertEqual(parsed.isoformat(), "2026-02-23T23:14:43.896301+00:00")
        self.assertEqual(policy, "localized_naive_as_utc")

    def test_timestamp_dengan_offset_dikonversi_ke_utc(self):
        parsed, policy = parse_timestamp_utc("2026-02-24T06:14:43.896301+07:00")
        self.assertEqual(parsed.isoformat(), "2026-02-23T23:14:43.896301+00:00")
        self.assertEqual(policy, "converted_offset_to_utc")


class CanonicalStateTest(unittest.TestCase):
    def setUp(self):
        self.transformer = CanonicalStateTransformer(
            room_id="unresolved", validation_ranges=RANGES
        )

    def test_raw_record_diubah_ke_struktur_canonical(self):
        state = self.transformer.transform(
            raw_record(), source_row_number=2, source_file_sha256="abc"
        )
        self.assertEqual(state["timestamp_utc"], "2026-02-23T23:14:43.896301Z")
        self.assertEqual(state["environment"]["temperature_c"], 27.5)
        self.assertEqual(state["occupancy"]["count"], 0)
        self.assertTrue(state["data_quality"]["valid"])
        self.assertIsNone(state["data_quality"]["staleness_seconds"])
        self.assertIn("room_id_unresolved", state["data_quality"]["flags"])

    def test_missing_occupancy_berbeda_dari_nol(self):
        missing = self.transformer.transform(raw_record(**{"Jumlah Orang": ""}))
        zero = self.transformer.transform(raw_record(**{"Jumlah Orang": "0"}))
        self.assertIsNone(missing["occupancy"]["count"])
        self.assertFalse(missing["data_quality"]["valid"])
        self.assertEqual(zero["occupancy"]["count"], 0)
        self.assertTrue(zero["data_quality"]["valid"])

    def test_outlier_dipertahankan_dan_diberi_flag(self):
        state = self.transformer.transform(raw_record(**{"Suhu (C)": "61"}))
        self.assertEqual(state["environment"]["temperature_c"], 61.0)
        self.assertFalse(state["data_quality"]["valid"])
        self.assertIn("out_of_range_temperature_c", state["data_quality"]["flags"])


if __name__ == "__main__":
    unittest.main()
