"""Transformasi satu record CSV menjadi canonical twin state.

Modul ini sengaja tidak melakukan imputasi, penghapusan outlier, atau penentuan
``room_id`` secara implisit. Nilai mentah yang tidak dapat divalidasi tetap
direpresentasikan sebagai ``None`` dan dijelaskan melalui quality flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
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
