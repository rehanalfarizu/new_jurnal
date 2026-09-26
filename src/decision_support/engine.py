"""Rule engine decision support yang transparan dan deterministik.

Threshold tidak disembunyikan di modul ini. Seluruh nilai numerik rule dibaca
dari ``configs/decision_support.yaml`` dan disertakan kembali pada trace hasil.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.twin_state.canonical import UNRESOLVED_ROOM_ID, parse_timestamp_utc


REQUIRED_NUMERIC_FIELDS = (
    "occupancy_count",
    "current_power_w",
    "forecast_power_30m_w",
    "temperature_c",
    "humidity_percent",
)


@dataclass(frozen=True)
class DecisionSupportInput:
    """Input minimum satu sample evaluasi decision support."""

    timestamp_utc: str | None
    occupancy_count: int | float | None
    current_power_w: float | None
    forecast_power_30m_w: float | None
    temperature_c: float | None
    humidity_percent: float | None
    device_id: str | None = None
    room_id: str = UNRESOLVED_ROOM_ID
    schema_version: str = "1.0.0-research"


def load_decision_support_config(path: str | Path) -> dict[str, Any]:
    """Muat konfigurasi dan validasi struktur minimum rule."""

    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    required_rules = {
        "invalid_input",
        "unoccupied_elevated_power",
        "forecasted_power_increase",
        "occupied_high_environment",
        "normal_monitoring",
    }
    if not isinstance(config, dict) or not isinstance(config.get("rules"), dict):
        raise ValueError("konfigurasi decision support tidak memiliki bagian rules")
    missing = required_rules - set(config["rules"])
    if missing:
        raise ValueError(f"rule wajib tidak tersedia: {sorted(missing)}")
    rule_ids = [rule.get("rule_id") for rule in config["rules"].values()]
    if any(not rule_id for rule_id in rule_ids) or len(rule_ids) != len(set(rule_ids)):
        raise ValueError("setiap rule harus memiliki rule_id unik")
    return config


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _normalize_timestamp(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, "timestamp_utc_missing"
    try:
        parsed, _policy = parse_timestamp_utc(str(value))
    except (TypeError, ValueError):
        return None, "timestamp_utc_invalid"
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z"), None


def validate_input(state: DecisionSupportInput) -> tuple[dict[str, Any], list[str]]:
    """Normalisasi input dan kembalikan error tanpa melakukan imputasi."""

    normalized = asdict(state)
    normalized_timestamp, timestamp_error = _normalize_timestamp(state.timestamp_utc)
    normalized["timestamp_utc"] = normalized_timestamp
    errors: list[str] = []
    if timestamp_error:
        errors.append(timestamp_error)

    for field in REQUIRED_NUMERIC_FIELDS:
        value = getattr(state, field)
        if value is None:
            errors.append(f"{field}_missing")
        elif not _finite_number(value):
            errors.append(f"{field}_invalid")
        else:
            normalized[field] = float(value)

    occupancy = state.occupancy_count
    if _finite_number(occupancy):
        occupancy_float = float(occupancy)
        if not occupancy_float.is_integer() or occupancy_float < 0:
            errors.append("occupancy_count_invalid")
        else:
            normalized["occupancy_count"] = int(occupancy_float)

    for field in ("current_power_w", "forecast_power_30m_w"):
        value = normalized.get(field)
        if _finite_number(value) and float(value) < 0:
            errors.append(f"{field}_negative")
    humidity = normalized.get("humidity_percent")
    if _finite_number(humidity) and not 0 <= float(humidity) <= 100:
        errors.append("humidity_percent_out_of_range")

    normalized["room_id"] = state.room_id or UNRESOLVED_ROOM_ID
    normalized["device_id"] = state.device_id or None
    return normalized, sorted(set(errors))


def _trace_thresholds(rule: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {"recommendation_text", "severity", "priority", "action_class", "name"}
    return {key: value for key, value in rule.items() if key not in ignored}


def _recommendation_id(input_state: Mapping[str, Any], rule_id: str) -> str:
    payload = json.dumps(
        {"input_state": input_state, "rule_id": rule_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "DS-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


def _recommendation(
    input_state: Mapping[str, Any],
    rule: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "recommendation_id": _recommendation_id(input_state, str(rule["rule_id"])),
        "timestamp_utc": input_state.get("timestamp_utc"),
        "input_state": dict(input_state),
        "rule_id": rule["rule_id"],
        "rule_name": rule["name"],
        "threshold_configuration": _trace_thresholds(rule),
        "recommendation_text": rule["recommendation_text"],
        "reason": reason,
        "severity": rule["severity"],
        "priority": int(rule["priority"]),
        "action_class": rule["action_class"],
    }


def detect_contradictions(recommendations: Sequence[Mapping[str, Any]]) -> list[str]:
    """Deteksi konflik rule yang dapat diaudit.

    Saat ini konflik didefinisikan sebagai keluarnya fallback ``no_action``
    bersamaan dengan rekomendasi tindakan/review. Rule tindakan yang berbeda
    boleh muncul bersamaan karena semuanya meminta pemeriksaan, bukan memberi
    perintah kontrol yang saling berlawanan.
    """

    classes = [str(item.get("action_class", "")) for item in recommendations]
    conflicts: list[str] = []
    if "no_action" in classes and any(value != "no_action" for value in classes):
        conflicts.append("no_action_with_active_recommendation")
    rule_ids = [str(item.get("rule_id", "")) for item in recommendations]
    if len(rule_ids) != len(set(rule_ids)):
        conflicts.append("duplicate_rule_id_for_same_sample")
    return conflicts


class DecisionSupportEngine:
    """Evaluasi rule secara berurutan dan hasilkan trace deterministik."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = dict(config)
        self.rules = self.config["rules"]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DecisionSupportEngine":
        return cls(load_decision_support_config(path))

    def evaluate(self, state: DecisionSupportInput) -> list[dict[str, Any]]:
        input_state, errors = validate_input(state)
        recommendations: list[dict[str, Any]] = []

        if errors:
            rule = self.rules["invalid_input"]
            input_state["forecast_delta_w"] = None
            trace_rule = dict(rule)
            trace_rule["required_numeric_fields"] = list(REQUIRED_NUMERIC_FIELDS)
            recommendations.append(
                _recommendation(
                    input_state,
                    trace_rule,
                    "Input tidak dapat dievaluasi: " + ", ".join(errors) + ".",
                )
            )
            return self._attach_conflict_trace(recommendations)

        occupancy = int(input_state["occupancy_count"])
        current = float(input_state["current_power_w"])
        forecast = float(input_state["forecast_power_30m_w"])
        temperature = float(input_state["temperature_c"])
        humidity = float(input_state["humidity_percent"])
        forecast_delta = forecast - current
        input_state["forecast_delta_w"] = forecast_delta

        rule = self.rules["unoccupied_elevated_power"]
        power_threshold = float(rule["power_threshold_w"])
        if occupancy == int(rule["occupancy_equals"]) and (
            current > power_threshold or forecast > power_threshold
        ):
            recommendations.append(
                _recommendation(
                    input_state,
                    rule,
                    f"occupancy_count={occupancy}; current_power_w={current:.6f} W dan "
                    f"forecast_power_30m_w={forecast:.6f} W dibandingkan threshold "
                    f"> {power_threshold:.6f} W; sedikitnya satu nilai melewati threshold.",
                )
            )

        rule = self.rules["forecasted_power_increase"]
        delta_threshold = float(rule["forecast_delta_threshold_w"])
        if forecast_delta > delta_threshold:
            recommendations.append(
                _recommendation(
                    input_state,
                    rule,
                    f"forecast_delta_w={forecast_delta:.6f} W, dihitung sebagai "
                    f"{forecast:.6f} - {current:.6f}, melewati threshold > "
                    f"{delta_threshold:.6f} W.",
                )
            )

        rule = self.rules["occupied_high_environment"]
        temperature_threshold = float(rule["temperature_threshold_c"])
        humidity_threshold = float(rule["humidity_threshold_percent"])
        if occupancy > int(rule["occupancy_min_exclusive"]) and (
            temperature > temperature_threshold or humidity > humidity_threshold
        ):
            recommendations.append(
                _recommendation(
                    input_state,
                    rule,
                    f"occupancy_count={occupancy}; temperature_c={temperature:.6f} °C "
                    f"(threshold > {temperature_threshold:.6f} °C) dan humidity_percent="
                    f"{humidity:.6f}% (threshold > {humidity_threshold:.6f}%); sedikitnya "
                    "satu kondisi lingkungan melewati threshold skenario.",
                )
            )

        if not recommendations:
            rule = self.rules["normal_monitoring"]
            recommendations.append(
                _recommendation(
                    input_state,
                    rule,
                    "Tidak ada DS-RULE-001, DS-RULE-002, atau DS-RULE-003 yang terpenuhi.",
                )
            )
        return self._attach_conflict_trace(recommendations)

    @staticmethod
    def _attach_conflict_trace(
        recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        conflicts = detect_contradictions(recommendations)
        for recommendation in recommendations:
            recommendation["contradiction_detected"] = bool(conflicts)
            recommendation["contradiction_reasons"] = conflicts
        return recommendations
