"""Eksplorasi dan preprocessing streaming untuk dataset sensor smart-room."""

from __future__ import annotations

from array import array
from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import yaml

from src.twin_state.canonical import (
    RAW_COLUMNS,
    CanonicalStateTransformer,
    canonical_state_to_flat_row,
    parse_timestamp_utc,
)


EXPECTED_COLUMNS = list(RAW_COLUMNS.values())
NUMERIC_FIELDS = {
    "temperature_c": (RAW_COLUMNS["temperature_c"], "°C"),
    "humidity_percent": (RAW_COLUMNS["humidity_percent"], "%"),
    "voltage_v": (RAW_COLUMNS["voltage_v"], "V"),
    "current_a": (RAW_COLUMNS["current_a"], "A"),
    "power_w": (RAW_COLUMNS["power_w"], "W"),
    "occupancy_count": (RAW_COLUMNS["occupancy_count"], "orang"),
}


@dataclass
class NumericProfile:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    frequencies: Counter[float] = field(default_factory=Counter)

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        self.frequencies[value] += 1

    @property
    def sample_std(self) -> float | None:
        return math.sqrt(self.m2 / (self.count - 1)) if self.count > 1 else None

    def quantile(self, probability: float) -> float | None:
        if not self.count:
            return None
        position = (self.count - 1) * probability
        lower_rank = math.floor(position)
        upper_rank = math.ceil(position)
        lower = self._value_at_rank(lower_rank)
        upper = self._value_at_rank(upper_rank)
        return lower + (upper - lower) * (position - lower_rank)

    def _value_at_rank(self, rank: int) -> float:
        cumulative = 0
        for value, count in sorted(self.frequencies.items()):
            cumulative += count
            if rank < cumulative:
                return value
        raise IndexError(rank)


@dataclass
class SimpleProfile:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    @property
    def sample_std(self) -> float | None:
        return math.sqrt(self.m2 / (self.count - 1)) if self.count > 1 else None


def load_stage2_config(path: str | Path) -> dict[str, Any]:
    """Muat konfigurasi YAML dan validasi bagian yang dipakai Tahap 2."""

    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("konfigurasi harus berupa mapping YAML")
    for section in ("data", "canonical_state", "preprocessing"):
        if section not in config:
            raise ValueError(f"bagian konfigurasi wajib tidak ditemukan: {section}")
    return config


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp_to_microseconds(value: datetime) -> int:
    return int(value.timestamp()) * 1_000_000 + value.microsecond


def _microseconds_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _parse_finite_float(value: Any) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _format_number(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return format(value, ".15g")


def _interval_bin(seconds: float) -> str:
    if seconds == 0:
        return "0"
    limits = (1, 2, 5, 10, 30, 60, 300, 900, 1800)
    lower = 0
    for upper in limits:
        if seconds <= upper:
            return f"({lower},{upper}]"
        lower = upper
    return ">1800"


def _prepare_duplicate_database(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA locking_mode=EXCLUSIVE")
    connection.execute(
        "CREATE TABLE record_counts (record_key TEXT PRIMARY KEY, n INTEGER NOT NULL) WITHOUT ROWID"
    )
    connection.execute(
        "CREATE TABLE timestamp_counts (timestamp_utc TEXT PRIMARY KEY, n INTEGER NOT NULL) WITHOUT ROWID"
    )
    return connection


def _flush_duplicate_batches(
    connection: sqlite3.Connection,
    records: list[tuple[str]],
    timestamps: list[tuple[str]],
) -> None:
    if records:
        connection.executemany(
            "INSERT INTO record_counts(record_key,n) VALUES (?,1) "
            "ON CONFLICT(record_key) DO UPDATE SET n=n+1",
            records,
        )
        records.clear()
    if timestamps:
        connection.executemany(
            "INSERT INTO timestamp_counts(timestamp_utc,n) VALUES (?,1) "
            "ON CONFLICT(timestamp_utc) DO UPDATE SET n=n+1",
            timestamps,
        )
        timestamps.clear()
    connection.commit()


def analyze_dataset(
    input_path: str | Path,
    output_dir: str | Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Hitung profil dataset dan tulis seluruh tabel Tahap 2.

    Data mentah dibaca saja. Semua duplikasi dipertahankan dan dihitung secara
    eksak dengan SQLite sementara; hasil akhir tidak bergantung pada database itu.
    """

    source = Path(input_path).expanduser().resolve()
    destination = Path(output_dir)
    if not source.is_file():
        raise FileNotFoundError(source)

    file_sha256 = _sha256(source)
    data_config = config["data"]
    canonical_config = config["canonical_state"]
    preprocessing_config = config["preprocessing"]
    if str(data_config.get("source_timezone", "")).upper() != "UTC":
        raise ValueError("Tahap 2 mensyaratkan source_timezone: UTC")

    ranges = canonical_config["validation_ranges"]
    transformer = CanonicalStateTransformer(
        room_id=canonical_config.get("room_id"),
        schema_version=canonical_config["schema_version"],
        validation_ranges=ranges,
    )
    gap_threshold = float(preprocessing_config["gap_threshold_seconds"])

    total_rows = 0
    malformed_width_rows = 0
    missing = Counter({column: 0 for column in EXPECTED_COLUMNS})
    devices: Counter[str] = Counter()
    numeric_profiles = {field: NumericProfile() for field in NUMERIC_FIELDS}
    quality_flags: Counter[str] = Counter()
    valid_rows = 0
    timestamps = array("q")
    previous_source_timestamp: int | None = None
    non_monotonic_pairs = 0
    localized_naive_count = 0
    aware_timestamp_count = 0

    record_batch: list[tuple[str]] = []
    timestamp_batch: list[tuple[str]] = []

    with tempfile.TemporaryDirectory(prefix="stage2_duplicates_") as temp_dir:
        duplicate_db = _prepare_duplicate_database(str(Path(temp_dir) / "duplicates.sqlite3"))
        with source.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != EXPECTED_COLUMNS:
                raise ValueError(
                    "schema CSV tidak sesuai; diharapkan "
                    f"{EXPECTED_COLUMNS}, ditemukan {reader.fieldnames}"
                )
            for row_number, raw in enumerate(reader, start=2):
                total_rows += 1
                if None in raw or any(column not in raw for column in EXPECTED_COLUMNS):
                    malformed_width_rows += 1

                raw_values = tuple("" if raw.get(column) is None else str(raw[column]) for column in EXPECTED_COLUMNS)
                record_key = json.dumps(raw_values, ensure_ascii=False, separators=(",", ":"))
                record_batch.append((record_key,))

                for column in EXPECTED_COLUMNS:
                    if raw.get(column) is None or not str(raw[column]).strip():
                        missing[column] += 1

                device_text = "" if raw.get(RAW_COLUMNS["device_id"]) is None else str(
                    raw[RAW_COLUMNS["device_id"]]
                ).strip()
                if device_text:
                    devices[device_text] += 1

                state = transformer.transform(
                    raw,
                    source_row_number=row_number,
                    source_file_sha256=file_sha256,
                )
                for flag in state["data_quality"]["flags"]:
                    quality_flags[flag] += 1
                if state["data_quality"]["valid"]:
                    valid_rows += 1

                canonical_timestamp = state["timestamp_utc"]
                if canonical_timestamp is not None:
                    timestamp_batch.append((canonical_timestamp,))
                    parsed_timestamp, policy = parse_timestamp_utc(str(raw[RAW_COLUMNS["timestamp"]]))
                    microseconds = _timestamp_to_microseconds(parsed_timestamp)
                    timestamps.append(microseconds)
                    if previous_source_timestamp is not None and microseconds < previous_source_timestamp:
                        non_monotonic_pairs += 1
                    previous_source_timestamp = microseconds
                    if policy == "localized_naive_as_utc":
                        localized_naive_count += 1
                    else:
                        aware_timestamp_count += 1

                for field, (raw_column, _unit) in NUMERIC_FIELDS.items():
                    value = _parse_finite_float(raw.get(raw_column))
                    if value is not None:
                        numeric_profiles[field].add(value)

                if len(record_batch) >= 20_000:
                    _flush_duplicate_batches(duplicate_db, record_batch, timestamp_batch)

        _flush_duplicate_batches(duplicate_db, record_batch, timestamp_batch)
        exact_duplicate_rows, exact_duplicate_groups = duplicate_db.execute(
            "SELECT COALESCE(SUM(n-1),0), COALESCE(SUM(CASE WHEN n>1 THEN 1 ELSE 0 END),0) "
            "FROM record_counts"
        ).fetchone()
        duplicate_timestamp_rows, duplicate_timestamp_groups = duplicate_db.execute(
            "SELECT COALESCE(SUM(n-1),0), COALESCE(SUM(CASE WHEN n>1 THEN 1 ELSE 0 END),0) "
            "FROM timestamp_counts"
        ).fetchone()
        unique_records = duplicate_db.execute("SELECT COUNT(*) FROM record_counts").fetchone()[0]
        unique_timestamps = duplicate_db.execute("SELECT COUNT(*) FROM timestamp_counts").fetchone()[0]
        duplicate_db.close()

    sorted_timestamps = sorted(timestamps)
    interval_profile = SimpleProfile()
    interval_values = array("d")
    interval_bins: Counter[str] = Counter()
    gaps: list[dict[str, Any]] = []
    for index in range(1, len(sorted_timestamps)):
        interval_seconds = (sorted_timestamps[index] - sorted_timestamps[index - 1]) / 1_000_000
        interval_profile.add(interval_seconds)
        interval_values.append(interval_seconds)
        interval_bins[_interval_bin(interval_seconds)] += 1
        if interval_seconds > gap_threshold:
            gaps.append(
                {
                    "gap_index": len(gaps) + 1,
                    "start_timestamp_utc": _microseconds_to_iso(sorted_timestamps[index - 1]),
                    "end_timestamp_utc": _microseconds_to_iso(sorted_timestamps[index]),
                    "gap_seconds": _format_number(interval_seconds),
                    "threshold_seconds": _format_number(gap_threshold),
                }
            )

    sorted_intervals = sorted(interval_values)

    def interval_quantile(probability: float) -> float | None:
        if not sorted_intervals:
            return None
        position = (len(sorted_intervals) - 1) * probability
        lower = math.floor(position)
        upper = math.ceil(position)
        return sorted_intervals[lower] + (sorted_intervals[upper] - sorted_intervals[lower]) * (
            position - lower
        )

    start_timestamp = _microseconds_to_iso(sorted_timestamps[0]) if sorted_timestamps else ""
    end_timestamp = _microseconds_to_iso(sorted_timestamps[-1]) if sorted_timestamps else ""
    duration_seconds = (
        (sorted_timestamps[-1] - sorted_timestamps[0]) / 1_000_000
        if len(sorted_timestamps) >= 2
        else 0.0
    )
    total_missing = sum(missing.values())
    invalid_rows = total_rows - valid_rows
    timestamp_parse_failures = quality_flags["invalid_timestamp"]
    numeric_issue_count = sum(
        count
        for flag, count in quality_flags.items()
        if flag.startswith(("invalid_numeric_", "non_finite_", "non_integer_"))
    )
    out_of_range_count = sum(
        count for flag, count in quality_flags.items() if flag.startswith("out_of_range_")
    )

    dataset_rows = [
        ("nama_file", source.name, "", "Nama file sumber; path lokal tidak dipublikasikan"),
        ("sha256", file_sha256, "", "Checksum file sumber"),
        ("jumlah_record", total_rows, "baris", "Tidak termasuk header"),
        ("jumlah_kolom", len(EXPECTED_COLUMNS), "kolom", "Schema CSV yang divalidasi"),
        ("waktu_awal_utc", start_timestamp, "UTC", "Minimum timestamp setelah interpretasi UTC"),
        ("waktu_akhir_utc", end_timestamp, "UTC", "Maksimum timestamp setelah interpretasi UTC"),
        ("durasi_observasi_detik", _format_number(duration_seconds), "detik", "Waktu akhir dikurangi waktu awal"),
        ("durasi_observasi_hari", _format_number(duration_seconds / 86400), "hari", "Durasi detik dibagi 86.400"),
        ("jumlah_device", len(devices), "device", "DeviceID unik non-kosong"),
        ("jumlah_timestamp_valid", len(timestamps), "baris", "Timestamp yang dapat diparse"),
        ("jumlah_timestamp_unik", unique_timestamps, "timestamp", "Setelah normalisasi UTC"),
        ("interval_minimum_detik", _format_number(interval_profile.minimum), "detik", "Interval berurutan setelah pengurutan"),
        ("interval_p25_detik", _format_number(interval_quantile(0.25)), "detik", "Kuantil linear"),
        ("interval_median_detik", _format_number(interval_quantile(0.50)), "detik", "Kuantil linear"),
        ("interval_p75_detik", _format_number(interval_quantile(0.75)), "detik", "Kuantil linear"),
        ("interval_maksimum_detik", _format_number(interval_profile.maximum), "detik", "Interval berurutan setelah pengurutan"),
        ("ambang_gap_detik", _format_number(gap_threshold), "detik", "Dari konfigurasi Tahap 2"),
        ("jumlah_gap", len(gaps), "gap", "Interval yang lebih besar dari ambang"),
    ]
    _write_csv(
        destination / "dataset_summary.csv",
        ["metrik", "nilai", "satuan", "keterangan"],
        (
            {"metrik": metric, "nilai": value, "satuan": unit, "keterangan": note}
            for metric, value, unit, note in dataset_rows
        ),
    )

    schema_rows = [
        {"urutan": 1, "kolom_raw": "Timestamp", "tipe_raw": "string", "tipe_tervalidasi": "datetime UTC", "field_canonical": "timestamp_utc", "unit": "UTC"},
        {"urutan": 2, "kolom_raw": "DeviceID", "tipe_raw": "string", "tipe_tervalidasi": "string", "field_canonical": "device_id", "unit": "identifier"},
        {"urutan": 3, "kolom_raw": "Suhu (C)", "tipe_raw": "string", "tipe_tervalidasi": "float", "field_canonical": "environment.temperature_c", "unit": "°C"},
        {"urutan": 4, "kolom_raw": "Kelembaban (%)", "tipe_raw": "string", "tipe_tervalidasi": "float", "field_canonical": "environment.humidity_percent", "unit": "%"},
        {"urutan": 5, "kolom_raw": "Tegangan (V)", "tipe_raw": "string", "tipe_tervalidasi": "float", "field_canonical": "electrical.voltage_v", "unit": "V"},
        {"urutan": 6, "kolom_raw": "Arus (A)", "tipe_raw": "string", "tipe_tervalidasi": "float", "field_canonical": "electrical.current_a", "unit": "A"},
        {"urutan": 7, "kolom_raw": "Daya (W)", "tipe_raw": "string", "tipe_tervalidasi": "float", "field_canonical": "electrical.power_w", "unit": "W"},
        {"urutan": 8, "kolom_raw": "Jumlah Orang", "tipe_raw": "string", "tipe_tervalidasi": "integer", "field_canonical": "occupancy.count", "unit": "orang"},
    ]
    _write_csv(destination / "column_schema.csv", list(schema_rows[0]), schema_rows)

    _write_csv(
        destination / "device_summary.csv",
        ["device_id", "jumlah_record", "proporsi"],
        (
            {
                "device_id": device,
                "jumlah_record": count,
                "proporsi": _format_number(count / total_rows if total_rows else 0),
            }
            for device, count in sorted(devices.items())
        ),
    )
    _write_csv(
        destination / "missing_values.csv",
        ["kolom_raw", "jumlah_missing", "proporsi"],
        (
            {
                "kolom_raw": column,
                "jumlah_missing": missing[column],
                "proporsi": _format_number(missing[column] / total_rows if total_rows else 0),
            }
            for column in EXPECTED_COLUMNS
        ),
    )

    duplicate_rows = [
        {"jenis": "exact_duplicate", "jumlah_baris_berlebih": exact_duplicate_rows, "jumlah_grup_duplikat": exact_duplicate_groups, "jumlah_unik": unique_records, "kebijakan": "dipertahankan_dan_dilaporkan"},
        {"jenis": "duplicate_timestamp_utc", "jumlah_baris_berlebih": duplicate_timestamp_rows, "jumlah_grup_duplikat": duplicate_timestamp_groups, "jumlah_unik": unique_timestamps, "kebijakan": "dipertahankan_dan_dilaporkan"},
    ]
    _write_csv(destination / "duplicate_summary.csv", list(duplicate_rows[0]), duplicate_rows)

    bin_order = ["0", "(0,1]", "(1,2]", "(2,5]", "(5,10]", "(10,30]", "(30,60]", "(60,300]", "(300,900]", "(900,1800]", ">1800"]
    _write_csv(
        destination / "sampling_interval_distribution.csv",
        ["interval_bin_detik", "jumlah", "proporsi"],
        (
            {
                "interval_bin_detik": label,
                "jumlah": interval_bins[label],
                "proporsi": _format_number(
                    interval_bins[label] / interval_profile.count if interval_profile.count else 0
                ),
            }
            for label in bin_order
        ),
    )
    _write_csv(
        destination / "temporal_gaps.csv",
        ["gap_index", "start_timestamp_utc", "end_timestamp_utc", "gap_seconds", "threshold_seconds"],
        gaps,
    )

    descriptive_rows = []
    distribution_rows = []
    range_rows = []
    outlier_rows = []
    for field, (raw_column, unit) in NUMERIC_FIELDS.items():
        profile = numeric_profiles[field]
        q1 = profile.quantile(0.25)
        q3 = profile.quantile(0.75)
        descriptive_rows.append(
            {
                "variable": field,
                "kolom_raw": raw_column,
                "unit": unit,
                "count": profile.count,
                "missing": missing[raw_column],
                "mean": _format_number(profile.mean if profile.count else None),
                "sample_std": _format_number(profile.sample_std),
                "min": _format_number(profile.minimum),
                "p25": _format_number(q1),
                "median": _format_number(profile.quantile(0.50)),
                "p75": _format_number(q3),
                "max": _format_number(profile.maximum),
            }
        )
        for value, count in sorted(profile.frequencies.items()):
            distribution_rows.append(
                {
                    "variable": field,
                    "unit": unit,
                    "nilai": _format_number(value),
                    "jumlah": count,
                    "proporsi": _format_number(count / profile.count if profile.count else 0),
                }
            )
        rule = ranges[field]
        below = sum(count for value, count in profile.frequencies.items() if value < float(rule["min"]))
        above = sum(count for value, count in profile.frequencies.items() if value > float(rule["max"]))
        range_rows.append(
            {
                "variable": field,
                "minimum_valid": rule["min"],
                "maximum_valid": rule["max"],
                "di_bawah_batas": below,
                "di_atas_batas": above,
                "total_di_luar_batas": below + above,
                "sumber_batas": rule.get("source", "konfigurasi"),
                "tindakan": "dipertahankan_dan_diberi_flag",
            }
        )
        if q1 is None or q3 is None:
            lower_fence = upper_fence = None
            below_fence = above_fence = 0
        else:
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr
            below_fence = sum(
                count for value, count in profile.frequencies.items() if value < lower_fence
            )
            above_fence = sum(
                count for value, count in profile.frequencies.items() if value > upper_fence
            )
        outlier_rows.append(
            {
                "variable": field,
                "q1": _format_number(q1),
                "q3": _format_number(q3),
                "iqr_lower_fence": _format_number(lower_fence),
                "iqr_upper_fence": _format_number(upper_fence),
                "di_bawah_fence": below_fence,
                "di_atas_fence": above_fence,
                "total_outlier_iqr": below_fence + above_fence,
                "interpretasi": "indikator_eksploratif_bukan_error_otomatis",
                "tindakan": "dipertahankan_dan_dilaporkan",
            }
        )

    _write_csv(destination / "descriptive_statistics.csv", list(descriptive_rows[0]), descriptive_rows)
    _write_csv(
        destination / "variable_distributions.csv",
        ["variable", "unit", "nilai", "jumlah", "proporsi"],
        distribution_rows,
    )
    _write_csv(destination / "range_validation.csv", list(range_rows[0]), range_rows)
    _write_csv(destination / "outlier_summary.csv", list(outlier_rows[0]), outlier_rows)
    total_iqr_outliers = sum(int(row["total_outlier_iqr"]) for row in outlier_rows)

    quality_rows = [
        ("jumlah_record", total_rows, "Jumlah record sumber"),
        ("record_valid", valid_rows, "Valid menurut pemeriksaan timestamp, identitas, tipe, dan range"),
        ("record_memiliki_masalah_validasi", invalid_rows, "Record tidak dihapus"),
        ("malformed_width_rows", malformed_width_rows, "Jumlah field tidak sesuai schema"),
        ("missing_cells", total_missing, "Akumulasi sel kosong pada delapan kolom"),
        ("timestamp_parse_failures", timestamp_parse_failures, "Timestamp tidak dapat diparse"),
        ("timestamp_naive_dilokalisasi_utc", localized_naive_count, "Nilai jam tidak diubah"),
        ("timestamp_aware_dikonversi_utc", aware_timestamp_count, "Hanya berlaku bila suffix tersedia"),
        ("pasangan_tidak_monotonik", non_monotonic_pairs, "Perbandingan berurutan dalam file sumber"),
        ("exact_duplicate_rows", exact_duplicate_rows, "Baris berlebih identik secara eksak"),
        ("duplicate_timestamp_rows", duplicate_timestamp_rows, "Baris berlebih dengan timestamp UTC yang sama"),
        ("numeric_type_issues", numeric_issue_count, "Nilai numerik invalid/non-finite/non-integer"),
        ("out_of_range_values", out_of_range_count, "Akumulasi pelanggaran batas konfigurasi"),
        ("iqr_outlier_values", total_iqr_outliers, "Indikator eksploratif; bukan error otomatis dan tidak dihapus"),
        ("temporal_gaps", len(gaps), f"Interval > {gap_threshold:g} detik"),
        ("room_id_unresolved_rows", quality_flags["room_id_unresolved"], "Room ID tidak tersedia pada CSV"),
        ("occupancy_staleness_calculable", "false", "Tidak ada timestamp kamera independen"),
    ]
    _write_csv(
        destination / "data_quality_summary.csv",
        ["metrik", "nilai", "keterangan"],
        ({"metrik": metric, "nilai": value, "keterangan": note} for metric, value, note in quality_rows),
    )

    duplicate_affected = int(exact_duplicate_rows) + int(duplicate_timestamp_rows)
    preprocessing_rows = [
        (1, "baca_data_mentah", total_rows, total_rows, malformed_width_rows, "Membaca CSV tanpa mengubah sumber", "retain"),
        (2, "parse_timestamp", total_rows, total_rows, timestamp_parse_failures, "Memvalidasi timestamp; kegagalan tetap dilaporkan", "retain_and_flag"),
        (3, "normalisasi_utc", len(timestamps), len(timestamps), localized_naive_count, "Timestamp tanpa suffix diinterpretasikan sebagai UTC tanpa mengubah clock value", "localize_only"),
        (4, "urut_kronologis", total_rows, total_rows, non_monotonic_pairs, "Urutan kronologis diverifikasi; transformasi output akan mengurutkan bila diperlukan", "sort_if_needed"),
        (5, "validasi_tipe", total_rows, total_rows, numeric_issue_count, "Nilai invalid tidak diimputasi atau dihapus", "retain_and_flag"),
        (6, "deteksi_missing", total_rows, total_rows, total_missing, "Missing dibedakan dari angka nol", "retain_and_flag"),
        (7, "deteksi_duplikasi", total_rows, total_rows, duplicate_affected, "Duplikasi tidak dihapus pada Tahap 2", "retain_and_report"),
        (8, "deteksi_gap", total_rows, total_rows, len(gaps), "Gap ditentukan dari ambang konfigurasi", "retain_and_report"),
        (9, "validasi_range", total_rows, total_rows, out_of_range_count, "Outlier operasional dipertahankan dan diberi flag", "retain_and_flag"),
    ]
    _write_csv(
        destination / "preprocessing_report.csv",
        ["urutan", "transformasi", "record_sebelum", "record_setelah", "jumlah_terdampak", "alasan", "tindakan"],
        (
            {
                "urutan": order,
                "transformasi": step,
                "record_sebelum": before,
                "record_setelah": after,
                "jumlah_terdampak": affected,
                "alasan": reason,
                "tindakan": action,
            }
            for order, step, before, after, affected, reason, action in preprocessing_rows
        ),
    )

    return {
        "input_path": str(source),
        "file_sha256": file_sha256,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "chronological": non_monotonic_pairs == 0,
        "non_monotonic_pairs": non_monotonic_pairs,
        "start_timestamp_utc": start_timestamp,
        "end_timestamp_utc": end_timestamp,
        "gap_count": len(gaps),
        "exact_duplicate_rows": int(exact_duplicate_rows),
        "duplicate_timestamp_rows": int(duplicate_timestamp_rows),
        "output_dir": str(destination.resolve()),
    }


def write_canonical_dataset(
    input_path: str | Path,
    output_path: str | Path,
    config: Mapping[str, Any],
    *,
    file_sha256: str | None = None,
) -> dict[str, Any]:
    """Tulis dataset canonical terurut tanpa membuang satu pun record.

    SQLite sementara dipakai sebagai external sort agar pipeline tetap dapat
    menangani input besar dan input yang belum terurut secara kronologis.
    """

    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    checksum = file_sha256 or _sha256(source)
    canonical_config = config["canonical_state"]
    transformer = CanonicalStateTransformer(
        room_id=canonical_config.get("room_id"),
        schema_version=canonical_config["schema_version"],
        validation_ranges=canonical_config["validation_ranges"],
    )
    fieldnames = [
        "schema_version", "timestamp_utc", "room_id", "device_id",
        "temperature_c", "humidity_percent", "voltage_v", "current_a",
        "power_w", "occupancy_count", "valid", "staleness_seconds",
        "quality_flags", "source_file_sha256", "source_row_number",
        "source_timestamp_text", "timestamp_policy",
    ]

    with tempfile.TemporaryDirectory(prefix="stage2_sort_") as temp_dir:
        database = sqlite3.connect(str(Path(temp_dir) / "canonical_sort.sqlite3"))
        database.execute("PRAGMA journal_mode=OFF")
        database.execute("PRAGMA synchronous=OFF")
        database.execute("PRAGMA temp_store=FILE")
        database.execute(
            "CREATE TABLE canonical_rows ("
            "source_row_number INTEGER PRIMARY KEY, timestamp_utc TEXT, payload TEXT NOT NULL)"
        )
        batch: list[tuple[int, str | None, str]] = []
        with source.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != EXPECTED_COLUMNS:
                raise ValueError("schema CSV tidak sesuai dengan konfigurasi Tahap 2")
            for row_number, raw in enumerate(reader, start=2):
                state = transformer.transform(
                    raw,
                    source_row_number=row_number,
                    source_file_sha256=checksum,
                )
                flat = canonical_state_to_flat_row(state)
                batch.append(
                    (
                        row_number,
                        state["timestamp_utc"],
                        json.dumps(flat, ensure_ascii=False, separators=(",", ":")),
                    )
                )
                if len(batch) >= 20_000:
                    database.executemany("INSERT INTO canonical_rows VALUES (?,?,?)", batch)
                    database.commit()
                    batch.clear()
            if batch:
                database.executemany("INSERT INTO canonical_rows VALUES (?,?,?)", batch)
                database.commit()

        temporary = destination.with_suffix(destination.suffix + ".tmp")
        written = 0
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            cursor = database.execute(
                "SELECT payload FROM canonical_rows "
                "ORDER BY timestamp_utc IS NULL, timestamp_utc, source_row_number"
            )
            for (payload,) in cursor:
                writer.writerow(json.loads(payload))
                written += 1
        database.close()
        os.replace(temporary, destination)

    return {"rows_written": written, "output_path": str(destination.resolve()), "sha256_source": checksum}
