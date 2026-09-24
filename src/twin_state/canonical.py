"""Transformasi satu record CSV menjadi canonical twin state.

Modul ini sengaja tidak melakukan imputasi, penghapusan outlier, atau penentuan
``room_id`` secara implisit. Nilai mentah yang tidak dapat divalidasi tetap
direpresentasikan sebagai ``None`` dan dijelaskan melalui quality flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from numbers import Real
from typing import Any, Mapping


DEFAULT_SCHEMA_VERSION = "1.0.0-research"
UNRESOLVED_ROOM_ID = "unresolved"

RAW_COLUMNS = {
    "timestamp": "Timestamp",
    "device_id": "DeviceID",
    "temperature_c": "Suhu (C)",
    "humidity_percent": "Kelembaban (%)",
    "voltage_v": "Tegangan (V)",
    "current_a": "Arus (A)",
    "power_w": "Daya (W)",
    "occupancy_count": "Jumlah Orang",
}


@dataclass(frozen=True)
class RangeRule:
    """Batas validasi inklusif untuk satu variabel."""

    minimum: float
    maximum: float


def parse_timestamp_utc(value: str) -> tuple[datetime, str]:
    """Parse timestamp dan hasilkan waktu aware UTC tanpa menggeser waktu naive.

    Timestamp tanpa suffix diperlakukan sebagai waktu UTC sesuai provenance
    sistem. Angka jam, menit, detik, dan mikrodetiknya tidak dikonversi.
    """

    text = value.strip()
    if not text:
        raise ValueError("timestamp kosong")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc), "localized_naive_as_utc"
    return parsed.astimezone(timezone.utc), "converted_offset_to_utc"


def _parse_float(value: Any, field: str, flags: list[str]) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        flags.append(f"missing_{field}")
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        flags.append(f"invalid_numeric_{field}")
        return None
    if not math.isfinite(parsed):
        flags.append(f"non_finite_{field}")
        return None
    return parsed


class CanonicalStateTransformer:
    """Transformer deterministik raw record ke canonical twin state."""

    def __init__(
        self,
        *,
        room_id: str | None = UNRESOLVED_ROOM_ID,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
        validation_ranges: Mapping[str, Mapping[str, float]] | None = None,
    ) -> None:
        self.room_id = room_id or UNRESOLVED_ROOM_ID
        self.schema_version = schema_version
        self.validation_ranges = {
            name: RangeRule(float(rule["min"]), float(rule["max"]))
            for name, rule in (validation_ranges or {}).items()
        }

    def transform(
        self,
        raw: Mapping[str, Any],
        *,
        source_row_number: int | None = None,
        source_file_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Ubah tepat satu record dan sertakan hasil validasinya."""

        flags: list[str] = []
        raw_timestamp = "" if raw.get(RAW_COLUMNS["timestamp"]) is None else str(
            raw.get(RAW_COLUMNS["timestamp"])
        )
        timestamp_utc: datetime | None
        timestamp_policy: str | None
        try:
            timestamp_utc, timestamp_policy = parse_timestamp_utc(raw_timestamp)
        except (TypeError, ValueError):
            timestamp_utc, timestamp_policy = None, None
            flags.append("invalid_timestamp")

        device_id = "" if raw.get(RAW_COLUMNS["device_id"]) is None else str(
            raw.get(RAW_COLUMNS["device_id"])
        ).strip()
        if not device_id:
            device_id = None
            flags.append("missing_device_id")

        if self.room_id == UNRESOLVED_ROOM_ID:
            flags.append("room_id_unresolved")

        values: dict[str, float | int | None] = {}
        for field in (
            "temperature_c",
            "humidity_percent",
            "voltage_v",
            "current_a",
            "power_w",
        ):
            values[field] = _parse_float(raw.get(RAW_COLUMNS[field]), field, flags)

        occupancy = _parse_float(
            raw.get(RAW_COLUMNS["occupancy_count"]), "occupancy_count", flags
        )
        if occupancy is not None:
            if not occupancy.is_integer():
                flags.append("non_integer_occupancy_count")
                occupancy_value: int | None = None
            else:
                occupancy_value = int(occupancy)
        else:
            occupancy_value = None
        values["occupancy_count"] = occupancy_value

        for field, value in values.items():
            rule = self.validation_ranges.get(field)
            if value is not None and rule is not None:
                if float(value) < rule.minimum or float(value) > rule.maximum:
                    flags.append(f"out_of_range_{field}")

        invalid_prefixes = (
            "missing_",
            "invalid_",
            "non_finite_",
            "non_integer_",
            "out_of_range_",
        )
        valid = not any(flag.startswith(invalid_prefixes) for flag in flags)

        return {
            "schema_version": self.schema_version,
            "timestamp_utc": (
                timestamp_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
                if timestamp_utc is not None
                else None
            ),
            "room_id": self.room_id,
            "device_id": device_id,
            "environment": {
                "temperature_c": values["temperature_c"],
                "humidity_percent": values["humidity_percent"],
            },
            "electrical": {
                "voltage_v": values["voltage_v"],
                "current_a": values["current_a"],
                "power_w": values["power_w"],
            },
            "occupancy": {"count": values["occupancy_count"]},
            "data_quality": {
                "valid": valid,
                "staleness_seconds": None,
                "flags": flags,
            },
            "provenance": {
                "source_file_sha256": source_file_sha256,
                "source_row_number": source_row_number,
                "source_timestamp_text": raw_timestamp,
                "timestamp_policy": timestamp_policy,
            },
        }


def canonical_state_to_flat_row(state: Mapping[str, Any]) -> dict[str, Any]:
    """Ratakan state untuk keluaran CSV tanpa menghilangkan quality flags."""

    quality = state["data_quality"]
    provenance = state["provenance"]
    return {
        "schema_version": state["schema_version"],
        "timestamp_utc": state["timestamp_utc"],
        "room_id": state["room_id"],
        "device_id": state["device_id"],
        "temperature_c": state["environment"]["temperature_c"],
        "humidity_percent": state["environment"]["humidity_percent"],
        "voltage_v": state["electrical"]["voltage_v"],
        "current_a": state["electrical"]["current_a"],
        "power_w": state["electrical"]["power_w"],
        "occupancy_count": state["occupancy"]["count"],
        "valid": quality["valid"],
        "staleness_seconds": quality["staleness_seconds"],
        "quality_flags": "|".join(quality["flags"]),
        "source_file_sha256": provenance["source_file_sha256"],
        "source_row_number": provenance["source_row_number"],
        "source_timestamp_text": provenance["source_timestamp_text"],
        "timestamp_policy": provenance["timestamp_policy"],
    }


def validate_canonical_state_schema(state: Mapping[str, Any]) -> list[str]:
    """Validasi struktur dan tipe representasi canonical.

    Nilai ``None`` tetap diperbolehkan pada field telemetry karena transformer
    harus dapat merepresentasikan record sumber yang invalid tanpa mengarang
    nilai pengganti. Ketidaklengkapan isi dinilai terpisah melalui quality flag
    dan evaluasi completeness.
    """

    violations: list[str] = []

    required_top_level = (
        "schema_version",
        "timestamp_utc",
        "room_id",
        "device_id",
        "environment",
        "electrical",
        "occupancy",
        "data_quality",
        "provenance",
    )
    for field in required_top_level:
        if field not in state:
            violations.append(f"missing_canonical_field_{field}")

    def mapping_at(name: str) -> Mapping[str, Any]:
        value = state.get(name)
        if not isinstance(value, Mapping):
            violations.append(f"invalid_mapping_{name}")
            return {}
        return value

    schema_version = state.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        violations.append("invalid_schema_version")

    timestamp = state.get("timestamp_utc")
    if timestamp is not None:
        if not isinstance(timestamp, str):
            violations.append("invalid_type_timestamp_utc")
        else:
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                violations.append("invalid_format_timestamp_utc")
            else:
                if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
                    violations.append("timestamp_utc_not_utc")

    room_id = state.get("room_id")
    if not isinstance(room_id, str) or not room_id.strip():
        violations.append("invalid_room_id")

    device_id = state.get("device_id")
    if device_id is not None and not isinstance(device_id, str):
        violations.append("invalid_type_device_id")

    environment = mapping_at("environment")
    electrical = mapping_at("electrical")
    occupancy = mapping_at("occupancy")
    quality = mapping_at("data_quality")
    provenance = mapping_at("provenance")

    required_nested = {
        "environment": ("temperature_c", "humidity_percent"),
        "electrical": ("voltage_v", "current_a", "power_w"),
        "occupancy": ("count",),
        "data_quality": ("valid", "staleness_seconds", "flags"),
        "provenance": (
            "source_file_sha256",
            "source_row_number",
            "source_timestamp_text",
            "timestamp_policy",
        ),
    }
    nested_mappings = {
        "environment": environment,
        "electrical": electrical,
        "occupancy": occupancy,
        "data_quality": quality,
        "provenance": provenance,
    }
    for group, fields in required_nested.items():
        for field in fields:
            if field not in nested_mappings[group]:
                violations.append(f"missing_canonical_field_{group}.{field}")

    numeric_fields = {
        "environment.temperature_c": environment.get("temperature_c"),
        "environment.humidity_percent": environment.get("humidity_percent"),
        "electrical.voltage_v": electrical.get("voltage_v"),
        "electrical.current_a": electrical.get("current_a"),
        "electrical.power_w": electrical.get("power_w"),
    }
    for field, value in numeric_fields.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, Real)):
            violations.append(f"invalid_type_{field}")
        elif value is not None and not math.isfinite(float(value)):
            violations.append(f"non_finite_{field}")

    occupancy_count = occupancy.get("count")
    if occupancy_count is not None and (
        isinstance(occupancy_count, bool) or not isinstance(occupancy_count, int)
    ):
        violations.append("invalid_type_occupancy.count")

    if not isinstance(quality.get("valid"), bool):
        violations.append("invalid_type_data_quality.valid")
    staleness = quality.get("staleness_seconds")
    if staleness is not None and (
        isinstance(staleness, bool)
        or not isinstance(staleness, Real)
        or not math.isfinite(float(staleness))
        or float(staleness) < 0
    ):
        violations.append("invalid_data_quality.staleness_seconds")
    flags = quality.get("flags")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        violations.append("invalid_type_data_quality.flags")

    if provenance.get("source_file_sha256") is not None and not isinstance(
        provenance.get("source_file_sha256"), str
    ):
        violations.append("invalid_type_provenance.source_file_sha256")
    source_row_number = provenance.get("source_row_number")
    if source_row_number is not None and (
        isinstance(source_row_number, bool) or not isinstance(source_row_number, int)
    ):
        violations.append("invalid_type_provenance.source_row_number")
    if not isinstance(provenance.get("source_timestamp_text"), str):
        violations.append("invalid_type_provenance.source_timestamp_text")
    timestamp_policy = provenance.get("timestamp_policy")
    if timestamp_policy is not None and timestamp_policy not in {
        "localized_naive_as_utc",
        "converted_offset_to_utc",
    }:
        violations.append("invalid_provenance.timestamp_policy")

    return violations
