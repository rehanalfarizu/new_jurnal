"""Chronological split dan perlindungan boundary terhadap target leakage."""

from __future__ import annotations

from typing import Sequence

import pandas as pd


def build_temporal_split(
    index: pd.DatetimeIndex,
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.15,
) -> tuple[pd.Series, pd.DataFrame]:
    """Tetapkan split berdasarkan urutan waktu pada seluruh minute-bin."""

    if not index.is_monotonic_increasing or not index.is_unique:
        raise ValueError("index harus unik dan terurut kronologis")
    if abs(train_fraction + validation_fraction + test_fraction - 1.0) > 1e-12:
        raise ValueError("jumlah fraction split harus 1")
    count = len(index)
    train_count = int(count * train_fraction)
    validation_count = int(count * validation_fraction)
    test_count = count - train_count - validation_count
    if min(train_count, validation_count, test_count) <= 0:
        raise ValueError("setiap split harus memiliki minimal satu minute-bin")

    labels = pd.Series(index=index, dtype="object", name="split")
    labels.iloc[:train_count] = "train"
    labels.iloc[train_count : train_count + validation_count] = "validation"
    labels.iloc[train_count + validation_count :] = "test"

    rows = []
    for split_name in ("train", "validation", "test"):
        selected = labels.index[labels == split_name]
        rows.append(
            {
                "split": split_name,
                "start_timestamp_utc": selected.min(),
                "end_timestamp_utc": selected.max(),
                "minute_bins": len(selected),
            }
        )
    return labels, pd.DataFrame(rows)


def classify_modeling_samples(
    frame: pd.DataFrame,
    split_labels: pd.Series,
    required_features: Sequence[str],
) -> pd.DataFrame:
    """Tandai sample usable dan alasan eksklusif ketika sample dikeluarkan."""

    result = frame.copy()
    result["split"] = split_labels
    target_split = pd.Series(index=result.index, dtype="object")
    target_times = pd.DatetimeIndex(result["target_timestamp_utc"])
    bounds = {
        name: (split_labels.index[split_labels == name].min(), split_labels.index[split_labels == name].max())
        for name in ("train", "validation", "test")
    }
    for name, (start, end) in bounds.items():
        mask = (target_times >= start) & (target_times <= end)
        target_split.loc[mask] = name
    result["target_split"] = target_split

    feature_complete = result[list(required_features)].notna().all(axis=1)
    target_available = result["target_power_30m"].notna()
    horizon_complete = result["forecast_horizon_complete"]
    same_split = result["split"] == result["target_split"]

    reason = pd.Series("usable", index=result.index, dtype="object")
    no_telemetry = ~result["has_telemetry"]
    partial_bin = result["has_telemetry"] & ~result["complete_bin"]
    incomplete_window = ~no_telemetry & ~partial_bin & ~feature_complete
    target_missing = feature_complete & ~target_available
    horizon_crosses_gap = feature_complete & target_available & ~horizon_complete
    crosses_boundary = feature_complete & target_available & horizon_complete & ~same_split

    reason.loc[no_telemetry] = "minute_bin_tanpa_telemetry"
    reason.loc[partial_bin] = "minute_bin_tidak_lengkap"
    reason.loc[incomplete_window] = "feature_window_tidak_lengkap"
    reason.loc[target_missing] = "target_t_plus_30_tidak_tersedia"
    reason.loc[horizon_crosses_gap] = "forecast_horizon_melintasi_gap"
    reason.loc[crosses_boundary] = "target_melintasi_split_boundary"
    result["exclusion_reason"] = reason
    result["usable_for_modeling"] = reason == "usable"
    return result
