#!/usr/bin/env python3
"""Build hourly profile table from raw sensor data.

Computes per UTC hour (0-23): mean power, std power, mean occupancy, record count.
Also reports the range (max-min) of hourly means as absolute and percent of overall mean.

Uses the same UTC handling as the main pipeline: naive timestamps are interpreted
as UTC without clock shift.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def parse_timestamp_utc(ts_str: str) -> datetime:
    """Parse timestamp string as UTC, same as main pipeline.

    Naive timestamps (no timezone suffix) are interpreted as UTC.
    """
    ts_str = ts_str.strip()
    # Try ISO format with Z suffix
    if ts_str.endswith("Z"):
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    # Try ISO format with offset
    if "+" in ts_str or ts_str.count("-") > 2:
        try:
            return datetime.fromisoformat(ts_str).astimezone(timezone.utc)
        except ValueError:
            pass
    # Naive timestamp - interpret as UTC
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        # Try with space separator
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        return dt.replace(tzinfo=timezone.utc)


def load_raw_data(path: Path) -> list[dict[str, Any]]:
    """Load raw CSV and parse relevant columns."""
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = parse_timestamp_utc(row["Timestamp"])
                power = float(row["Daya (W)"])
                occupancy = int(row["Jumlah Orang"])
                records.append({
                    "hour_utc": ts.hour,
                    "power_w": power,
                    "occupancy_count": occupancy,
                })
            except (KeyError, ValueError) as e:
                print(f"Skipping row: {e}", file=sys.stderr)
                continue
    return records


def main() -> int:
    root = Path(__file__).resolve().parent.parent

    # Try to find raw data
    raw_path = root / "data" / "raw" / "sensor_data.csv"
    if not raw_path.exists():
        raw_path = root / "sensor_data.csv"
    if not raw_path.exists():
        print(f"ERROR: Raw data file not found at {raw_path}", file=sys.stderr)
        print("Place sensor_data.csv at data/raw/sensor_data.csv", file=sys.stderr)
        return 1

    print(f"Loading raw data from: {raw_path}")
    records = load_raw_data(raw_path)
    print(f"Loaded {len(records):,} records")

    # Group by hour
    hourly_power: dict[int, list[float]] = {h: [] for h in range(24)}
    hourly_occ: dict[int, list[int]] = {h: [] for h in range(24)}

    for r in records:
        h = r["hour_utc"]
        hourly_power[h].append(r["power_w"])
        hourly_occ[h].append(r["occupancy_count"])

    # Compute statistics per hour
    hourly_stats = []
    for hour in range(24):
        power_arr = np.array(hourly_power[hour])
        occ_arr = np.array(hourly_occ[hour])
        hourly_stats.append({
            "hour_utc": hour,
            "record_count": len(power_arr),
            "power_mean_w": float(np.mean(power_arr)) if len(power_arr) > 0 else None,
            "power_std_w": float(np.std(power_arr, ddof=1)) if len(power_arr) > 1 else None,
            "occupancy_mean": float(np.mean(occ_arr)) if len(occ_arr) > 0 else None,
        })

    # Compute overall statistics
    all_power = np.array([r["power_w"] for r in records])
    all_occ = np.array([r["occupancy_count"] for r in records])

    overall_power_mean = float(np.mean(all_power))
    overall_occ_mean = float(np.mean(all_occ))

    hourly_power_means = [s["power_mean_w"] for s in hourly_stats if s["power_mean_w"] is not None]
    hourly_occ_means = [s["occupancy_mean"] for s in hourly_stats if s["occupancy_mean"] is not None]

    power_range = max(hourly_power_means) - min(hourly_power_means)
    occ_range = max(hourly_occ_means) - min(hourly_occ_means)

    power_range_pct = (power_range / overall_power_mean) * 100 if overall_power_mean != 0 else 0
    occ_range_pct = (occ_range / overall_occ_mean) * 100 if overall_occ_mean != 0 else 0

    # Write hourly profile CSV
    output_csv = root / "results" / "tables" / "hourly_profile.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["hour_utc", "record_count",
                                                "power_mean_w", "power_std_w", "occupancy_mean"])
        writer.writeheader()
        writer.writerows(hourly_stats)
    print(f"Wrote: {output_csv}")

    # Write summary CSV
    summary_csv = root / "results" / "tables" / "hourly_profile_summary.csv"
    summary_rows = [
        {"metric": "total_records", "value": len(records), "unit": "records"},
        {"metric": "overall_power_mean", "value": overall_power_mean, "unit": "W"},
        {"metric": "overall_occupancy_mean", "value": overall_occ_mean, "unit": "persons"},
        {"metric": "hourly_power_mean_min", "value": min(hourly_power_means), "unit": "W"},
        {"metric": "hourly_power_mean_max", "value": max(hourly_power_means), "unit": "W"},
        {"metric": "hourly_power_range", "value": power_range, "unit": "W"},
        {"metric": "hourly_power_range_pct", "value": power_range_pct, "unit": "%"},
        {"metric": "hourly_occupancy_mean_min", "value": min(hourly_occ_means), "unit": "persons"},
        {"metric": "hourly_occupancy_mean_max", "value": max(hourly_occ_means), "unit": "persons"},
        {"metric": "hourly_occupancy_range", "value": occ_range, "unit": "persons"},
        {"metric": "hourly_occupancy_range_pct", "value": occ_range_pct, "unit": "%"},
    ]
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value", "unit"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote: {summary_csv}")

    # Print summary
    print("\n" + "=" * 60)
    print("HOURLY PROFILE SUMMARY")
    print("=" * 60)
    print(f"Total records: {len(records):,}")
    print(f"\nPower (W):")
    print(f"  Overall mean: {overall_power_mean:.4f}")
    print(f"  Hourly means range: {min(hourly_power_means):.4f} to {max(hourly_power_means):.4f}")
    print(f"  Range (max-min): {power_range:.4f} W ({power_range_pct:.2f}% of overall mean)")
    print(f"\nOccupancy:")
    print(f"  Overall mean: {overall_occ_mean:.4f}")
    print(f"  Hourly means range: {min(hourly_occ_means):.4f} to {max(hourly_occ_means):.4f}")
    print(f"  Range (max-min): {occ_range:.4f} persons ({occ_range_pct:.2f}% of overall mean)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
