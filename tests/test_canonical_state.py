import copy
import unittest

from src.twin_state.canonical import (
    CanonicalStateTransformer,
    parse_timestamp_utc,
    validate_canonical_state_schema,
)


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

    def test_invalid_timestamp_dideteksi(self):
        state = self.transformer.transform(raw_record(Timestamp="bukan-timestamp"))
        self.assertIsNone(state["timestamp_utc"])
        self.assertFalse(state["data_quality"]["valid"])
        self.assertIn("invalid_timestamp", state["data_quality"]["flags"])

    def test_missing_required_field_dideteksi(self):
        state = self.transformer.transform(raw_record(DeviceID=""))
        self.assertIsNone(state["device_id"])
        self.assertFalse(state["data_quality"]["valid"])
        self.assertIn("missing_device_id", state["data_quality"]["flags"])

    def test_incorrect_numeric_type_dideteksi(self):
        state = self.transformer.transform(raw_record(**{"Daya (W)": "tidak-numerik"}))
        self.assertIsNone(state["electrical"]["power_w"])
        self.assertFalse(state["data_quality"]["valid"])
        self.assertIn("invalid_numeric_power_w", state["data_quality"]["flags"])

    def test_transformasi_deterministik(self):
        raw = raw_record()
        first = self.transformer.transform(
            raw, source_row_number=2, source_file_sha256="abc"
        )
        second = self.transformer.transform(
            raw, source_row_number=2, source_file_sha256="abc"
        )
        self.assertEqual(first, second)

    def test_nilai_telemetry_dipertahankan(self):
        state = self.transformer.transform(raw_record())
        self.assertEqual(state["device_id"], "RASPBERRY_PI_GATEWAY_001")
        self.assertEqual(state["environment"]["temperature_c"], 27.5)
        self.assertEqual(state["environment"]["humidity_percent"], 65.0)
        self.assertEqual(state["electrical"]["voltage_v"], 220.0)
        self.assertEqual(state["electrical"]["current_a"], 2.2)
        self.assertEqual(state["electrical"]["power_w"], 484.0)
        self.assertEqual(state["occupancy"]["count"], 0)

    def test_room_id_unresolved_tidak_membuat_telemetry_invalid(self):
        state = self.transformer.transform(raw_record())
        self.assertEqual(state["room_id"], "unresolved")
        self.assertIn("room_id_unresolved", state["data_quality"]["flags"])
        self.assertTrue(state["data_quality"]["valid"])

    def test_staleness_tetap_none_tanpa_bukti_timestamp_independen(self):
        state = self.transformer.transform(raw_record())
        self.assertIsNone(state["data_quality"]["staleness_seconds"])

    def test_validator_schema_menerima_state_valid(self):
        state = self.transformer.transform(raw_record())
        self.assertEqual(validate_canonical_state_schema(state), [])

    def test_validator_schema_mendeteksi_field_hilang_dan_tipe_salah(self):
        state = self.transformer.transform(raw_record())
        invalid = copy.deepcopy(state)
        del invalid["electrical"]["power_w"]
        invalid["occupancy"]["count"] = 1.5
        violations = validate_canonical_state_schema(invalid)
        self.assertIn("missing_canonical_field_electrical.power_w", violations)
        self.assertIn("invalid_type_occupancy.count", violations)


if __name__ == "__main__":
    unittest.main()
