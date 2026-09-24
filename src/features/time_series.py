"""Resampling satu menit, target 30 menit, dan feature engineering."""

from __future__ import annotations

from array import array
import csv
from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.twin_state.canonical import RAW_COLUMNS, parse_timestamp_utc


MEASUREMENT_COLUMNS = [
    "temperature_c",
    "humidity_percent",
    "voltage_v",
    "current_a",
    "power_w",
    "occupancy_count",
]

POWER_LAGS_MINUTES = (1, 5, 15, 30)
POWER_ROLLING_WINDOWS_MINUTES = (5, 15, 30)
OCCUPANCY_LAGS_MINUTES = (1, 5, 15, 30)
OCCUPANCY_ROLLING_WINDOWS_MINUTES = (5, 15, 30)

BASELINE2_FEATURES = [
    "power_w",
    "power_lag_1m",
    "power_lag_5m",
    "power_lag_15m",
    "power_lag_30m",
    "power_rolling_mean_5m",
    "power_rolling_std_5m",
    "power_rolling_mean_15m",
    "power_rolling_std_15m",
    "power_rolling_mean_30m",
    "power_rolling_std_30m",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "is_weekend",
]

BASELINE3_FEATURES = BASELINE2_FEATURES + [
    "temperature_c",
    "humidity_percent",
    "voltage_v",
    "current_a",
]

OCCUPANCY_FEATURES = [
    "occupancy_count",
    "occupancy_lag_1m",
    "occupancy_lag_5m",
    "occupancy_lag_15m",
    "occupancy_lag_30m",
    "occupancy_rolling_mean_5m",
    "occupancy_rolling_max_5m",
    "occupancy_rolling_mean_15m",
    "occupancy_rolling_max_15m",
    "occupancy_rolling_mean_30m",
    "occupancy_rolling_max_30m",
]

OCCUPANCY_TREATMENT_FEATURES = BASELINE3_FEATURES + OCCUPANCY_FEATURES

FEATURE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "power_w": {
        "group": "historical_power",
        "description": "Mean power pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "W",
    },
    **{
        f"power_lag_{lag}m": {
            "group": "historical_power",
            "description": f"Power pada t-{lag} menit.",
            "source_offset_min": -lag,
            "source_offset_max": -lag,
            "unit": "W",
        }
        for lag in POWER_LAGS_MINUTES
    },
    **{
        f"power_rolling_mean_{window}m": {
            "group": "historical_power",
            "description": f"Mean power backward-looking dari t-{window - 1} sampai t.",
            "source_offset_min": -(window - 1),
            "source_offset_max": 0,
            "unit": "W",
        }
        for window in POWER_ROLLING_WINDOWS_MINUTES
    },
    **{
        f"power_rolling_std_{window}m": {
            "group": "historical_power",
            "description": f"Sample standard deviation power backward-looking dari t-{window - 1} sampai t.",
            "source_offset_min": -(window - 1),
            "source_offset_max": 0,
            "unit": "W",
        }
        for window in POWER_ROLLING_WINDOWS_MINUTES
    },
    "hour_of_day_sin": {
        "group": "time",
        "description": "Komponen sinus waktu dalam hari pada timestamp t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "dimensionless",
    },
    "hour_of_day_cos": {
        "group": "time",
        "description": "Komponen kosinus waktu dalam hari pada timestamp t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "dimensionless",
    },
    "day_of_week_sin": {
        "group": "time",
        "description": "Komponen sinus hari dalam minggu pada timestamp t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "dimensionless",
    },
    "day_of_week_cos": {
        "group": "time",
        "description": "Komponen kosinus hari dalam minggu pada timestamp t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "dimensionless",
    },
    "is_weekend": {
        "group": "time",
        "description": "Indikator Sabtu atau Minggu pada timestamp t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "boolean",
    },
    "temperature_c": {
        "group": "environment",
        "description": "Mean temperature pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "°C",
    },
    "humidity_percent": {
        "group": "environment",
        "description": "Mean humidity pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "%",
    },
    "voltage_v": {
        "group": "electrical",
        "description": "Mean voltage pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "V",
    },
    "current_a": {
        "group": "electrical",
        "description": "Mean current pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "A",
    },
    "occupancy_count": {
        "group": "occupancy",
        "description": "Last valid occupancy observation pada minute-bin t.",
        "source_offset_min": 0,
        "source_offset_max": 0,
        "unit": "orang",
    },
    **{
        f"occupancy_lag_{lag}m": {
            "group": "occupancy",
            "description": f"Occupancy pada t-{lag} menit.",
            "source_offset_min": -lag,
            "source_offset_max": -lag,
            "unit": "orang",
        }
        for lag in OCCUPANCY_LAGS_MINUTES
    },
    **{
        f"occupancy_rolling_mean_{window}m": {
            "group": "occupancy",
            "description": f"Mean occupancy backward-looking dari t-{window - 1} sampai t.",
            "source_offset_min": -(window - 1),
            "source_offset_max": 0,
            "unit": "orang",
        }
        for window in OCCUPANCY_ROLLING_WINDOWS_MINUTES
    },
    **{
        f"occupancy_rolling_max_{window}m": {
            "group": "occupancy",
            "description": f"Maximum occupancy backward-looking dari t-{window - 1} sampai t.",
            "source_offset_min": -(window - 1),
            "source_offset_max": 0,
            "unit": "orang",
        }
        for window in OCCUPANCY_ROLLING_WINDOWS_MINUTES
    },
}


@dataclass
class MinuteAccumulator:
    minute: datetime
    sums: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    occupancy_last: int | None = None
    raw_record_count: int = 0

    def add(self, values: Mapping[str, float | int | None]) -> None:
        self.raw_record_count += 1
        for name in ("temperature_c", "humidity_percent", "voltage_v", "current_a", "power_w"):
            value = values[name]
            if value is not None:
                self.sums[name] = self.sums.get(name, 0.0) + float(value)
                self.counts[name] = self.counts.get(name, 0) + 1
        if values["occupancy_count"] is not None:
            self.occupancy_last = int(values["occupancy_count"])

    def finish(self) -> dict[str, Any]:
        result: dict[str, Any] = {"timestamp_utc": self.minute}
        for name in ("temperature_c", "humidity_percent", "voltage_v", "current_a", "power_w"):
            count = self.counts.get(name, 0)
            result[name] = self.sums.get(name, 0.0) / count if count else np.nan
        result["occupancy_count"] = (
            float(self.occupancy_last) if self.occupancy_last is not None else np.nan
        )
        result["raw_record_count"] = self.raw_record_count
        return result


def _finite_float(value: Any) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _raw_values(row: Mapping[str, Any]) -> dict[str, float | int | None]:
    occupancy = _finite_float(row.get(RAW_COLUMNS["occupancy_count"]))
    return {
        "temperature_c": _finite_float(row.get(RAW_COLUMNS["temperature_c"])),
        "humidity_percent": _finite_float(row.get(RAW_COLUMNS["humidity_percent"])),
        "voltage_v": _finite_float(row.get(RAW_COLUMNS["voltage_v"])),
        "current_a": _finite_float(row.get(RAW_COLUMNS["current_a"])),
        "power_w": _finite_float(row.get(RAW_COLUMNS["power_w"])),
        "occupancy_count": (
            int(occupancy) if occupancy is not None and occupancy.is_integer() else None
        ),
    }


def resample_sensor_csv(input_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Agregasikan raw CSV ke cadence satu menit tanpa mengisi bin kosong."""

    source = Path(input_path).expanduser().resolve()
    completed: list[dict[str, Any]] = []
    raw_power = array("d")
    raw_records = 0
    accumulator: MinuteAccumulator | None = None
    previous_timestamp: datetime | None = None

    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = list(RAW_COLUMNS.values())
        if reader.fieldnames != expected:
            raise ValueError(f"schema CSV tidak sesuai: {reader.fieldnames}")
        for row in reader:
            raw_records += 1
            timestamp, _policy = parse_timestamp_utc(str(row[RAW_COLUMNS["timestamp"]]))
            if previous_timestamp is not None and timestamp < previous_timestamp:
                raise ValueError("raw CSV tidak terurut kronologis; jalankan validasi Tahap 2")
            previous_timestamp = timestamp
            minute = timestamp.replace(second=0, microsecond=0)
            if accumulator is None:
                accumulator = MinuteAccumulator(minute)
            elif minute != accumulator.minute:
                completed.append(accumulator.finish())
                accumulator = MinuteAccumulator(minute)
            values = _raw_values(row)
            accumulator.add(values)
            if values["power_w"] is not None:
                raw_power.append(float(values["power_w"]))
    if accumulator is not None:
        completed.append(accumulator.finish())
    if not completed:
        raise ValueError("dataset tidak memiliki record")

    frame = pd.DataFrame.from_records(completed).set_index("timestamp_utc")
    frame.index = pd.DatetimeIndex(frame.index, name="timestamp_utc")
    full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="1min", tz="UTC")
    frame = frame.reindex(full_index)
    frame.index.name = "timestamp_utc"
    frame["raw_record_count"] = frame["raw_record_count"].fillna(0).astype("int64")
    frame["has_telemetry"] = frame["raw_record_count"] > 0
    frame["complete_bin"] = frame[MEASUREMENT_COLUMNS].notna().all(axis=1)

    raw_power_array = np.frombuffer(raw_power, dtype=np.float64).copy()
    metadata = {
        "raw_records": raw_records,
        "minute_bins_total": len(frame),
        "minute_bins_with_telemetry": int(frame["has_telemetry"].sum()),
        "minute_bins_complete": int(frame["complete_bin"].sum()),
        "minute_bins_missing": int((~frame["has_telemetry"]).sum()),
        "minute_bins_partial": int((frame["has_telemetry"] & ~frame["complete_bin"]).sum()),
        "start_timestamp_utc": frame.index.min(),
        "end_timestamp_utc": frame.index.max(),
        "raw_power_values": raw_power_array,
    }
    return frame, metadata


def add_power_target(frame: pd.DataFrame, horizon_minutes: int = 30) -> pd.DataFrame:
    """Tambahkan target power tepat pada t + horizon di grid satu menit."""

    if horizon_minutes <= 0:
        raise ValueError("horizon_minutes harus positif")
    result = frame.copy()
    result["target_timestamp_utc"] = result.index + pd.Timedelta(minutes=horizon_minutes)
    result["target_power_30m"] = result["power_w"].shift(-horizon_minutes)
    future_availability = result["has_telemetry"].shift(-1)
    result["forecast_horizon_complete"] = (
        future_availability.iloc[::-1]
        .rolling(window=horizon_minutes, min_periods=horizon_minutes)
        .min()
        .iloc[::-1]
        .fillna(False)
        .astype(bool)
    )
    return result


def add_forecasting_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan feature yang hanya memakai informasi pada atau sebelum t."""

    result = frame.copy()
    for lag in POWER_LAGS_MINUTES:
        result[f"power_lag_{lag}m"] = result["power_w"].shift(lag)
    for window in POWER_ROLLING_WINDOWS_MINUTES:
        rolling = result["power_w"].rolling(window=window, min_periods=window)
        result[f"power_rolling_mean_{window}m"] = rolling.mean()
        result[f"power_rolling_std_{window}m"] = rolling.std(ddof=1)
    for lag in OCCUPANCY_LAGS_MINUTES:
        result[f"occupancy_lag_{lag}m"] = result["occupancy_count"].shift(lag)
    for window in OCCUPANCY_ROLLING_WINDOWS_MINUTES:
        rolling = result["occupancy_count"].rolling(window=window, min_periods=window)
        result[f"occupancy_rolling_mean_{window}m"] = rolling.mean()
        result[f"occupancy_rolling_max_{window}m"] = rolling.max()

    minute_of_day = result.index.hour * 60 + result.index.minute
    day_angle = 2 * np.pi * minute_of_day / (24 * 60)
    week_angle = 2 * np.pi * result.index.dayofweek / 7
    result["hour_of_day_sin"] = np.sin(day_angle)
    result["hour_of_day_cos"] = np.cos(day_angle)
    result["day_of_week_sin"] = np.sin(week_angle)
    result["day_of_week_cos"] = np.cos(week_angle)
    result["is_weekend"] = (result.index.dayofweek >= 5).astype("int8")
    return result
