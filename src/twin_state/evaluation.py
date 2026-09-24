"""Evaluasi empiris Canonical Twin State terhadap telemetry CSV.

Modul ini tidak mengimplementasikan transformasi alternatif. Seluruh record
ditransformasikan dengan :class:`CanonicalStateTransformer`, lalu hasilnya
dinilai untuk schema, completeness, kualitas, temporal integrity, preservasi
nilai, dan determinisme.
"""

from __future__ import annotations

from array import array
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .canonical import (
    RAW_COLUMNS,
    UNRESOLVED_ROOM_ID,
    CanonicalStateTransformer,
    parse_timestamp_utc,
    validate_canonical_state_schema,
)


EXPECTED_RAW_COLUMNS = list(RAW_COLUMNS.values())
EXPECTED_TELEMETRY_FIELDS = (
    "timestamp_utc",
    "device_id",
    "environment.temperature_c",
    "environment.humidity_percent",
    "electrical.voltage_v",
    "electrical.current_a",
    "electrical.power_w",
    "occupancy.count",
)
DETERMINISM_STRIDE_RECORDS = 10_000

FIELD_MAPPING_ROWS = (
    {
        "source_field": RAW_COLUMNS["timestamp"],
        "canonical_field": "timestamp_utc",
        "source_type": "string",
        "canonical_type": "ISO 8601 UTC string",
        "unit": "UTC",
        "transformation": "Parse ISO 8601; timestamp tanpa suffix dilokalisasikan sebagai UTC tanpa mengubah clock value",
        "validation_rule": "Wajib tersedia, dapat diparse, dan hasil canonical harus UTC",
        "value_preservation": "Instant dan presisi mikrodetik dipertahankan; format dinormalisasi ke T dan Z",
    },
    {
        "source_field": RAW_COLUMNS["device_id"],
        "canonical_field": "device_id",
        "source_type": "string",
        "canonical_type": "string",
        "unit": "identifier",
        "transformation": "Trim whitespace; tanpa pemetaan identitas baru",
        "validation_rule": "Wajib tersedia dan non-kosong",
        "value_preservation": "Isi identifier dipertahankan setelah trim whitespace",
    },
    {
        "source_field": RAW_COLUMNS["temperature_c"],
        "canonical_field": "environment.temperature_c",
        "source_type": "numeric string",
        "canonical_type": "float",
        "unit": "°C",
        "transformation": "Parse float tanpa scaling atau konversi unit",
        "validation_rule": "Finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai numerik dipertahankan",
    },
    {
        "source_field": RAW_COLUMNS["humidity_percent"],
        "canonical_field": "environment.humidity_percent",
        "source_type": "numeric string",
        "canonical_type": "float",
        "unit": "%",
        "transformation": "Parse float tanpa scaling atau konversi unit",
        "validation_rule": "Finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai numerik dipertahankan",
    },
    {
        "source_field": RAW_COLUMNS["voltage_v"],
        "canonical_field": "electrical.voltage_v",
        "source_type": "numeric string",
        "canonical_type": "float",
        "unit": "V",
        "transformation": "Parse float tanpa scaling atau konversi unit",
        "validation_rule": "Finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai numerik dipertahankan",
    },
    {
        "source_field": RAW_COLUMNS["current_a"],
        "canonical_field": "electrical.current_a",
        "source_type": "numeric string",
        "canonical_type": "float",
        "unit": "A",
        "transformation": "Parse float tanpa scaling atau konversi unit",
        "validation_rule": "Finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai numerik dipertahankan",
    },
    {
        "source_field": RAW_COLUMNS["power_w"],
        "canonical_field": "electrical.power_w",
        "source_type": "numeric string",
        "canonical_type": "float",
        "unit": "W",
        "transformation": "Parse float tanpa scaling atau konversi unit",
        "validation_rule": "Finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai numerik dipertahankan",
    },
    {
        "source_field": RAW_COLUMNS["occupancy_count"],
        "canonical_field": "occupancy.count",
        "source_type": "numeric string",
        "canonical_type": "integer",
        "unit": "orang",
        "transformation": "Parse numeric lalu validasi integer; tanpa scaling",
        "validation_rule": "Integer finite dan berada pada range konfigurasi",
        "value_preservation": "Nilai hitungan integer dipertahankan",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _state_values(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "timestamp_utc": state["timestamp_utc"],
        "device_id": state["device_id"],
        "environment.temperature_c": state["environment"]["temperature_c"],
        "environment.humidity_percent": state["environment"]["humidity_percent"],
        "electrical.voltage_v": state["electrical"]["voltage_v"],
        "electrical.current_a": state["electrical"]["current_a"],
        "electrical.power_w": state["electrical"]["power_w"],
        "occupancy.count": state["occupancy"]["count"],
    }


def _expected_source_values(raw: Mapping[str, Any]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    try:
        timestamp, _policy = parse_timestamp_utc(str(raw.get(RAW_COLUMNS["timestamp"], "")))
    except (TypeError, ValueError):
        pass
    else:
        expected["timestamp_utc"] = timestamp.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    device = "" if raw.get(RAW_COLUMNS["device_id"]) is None else str(
        raw.get(RAW_COLUMNS["device_id"])
    ).strip()
    if device:
        expected["device_id"] = device

    numeric_mapping = {
        "environment.temperature_c": RAW_COLUMNS["temperature_c"],
        "environment.humidity_percent": RAW_COLUMNS["humidity_percent"],
        "electrical.voltage_v": RAW_COLUMNS["voltage_v"],
        "electrical.current_a": RAW_COLUMNS["current_a"],
        "electrical.power_w": RAW_COLUMNS["power_w"],
    }
    for canonical_field, raw_field in numeric_mapping.items():
        text = "" if raw.get(raw_field) is None else str(raw.get(raw_field)).strip()
        try:
            value = float(text)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            expected[canonical_field] = value

    occupancy_text = "" if raw.get(RAW_COLUMNS["occupancy_count"]) is None else str(
        raw.get(RAW_COLUMNS["occupancy_count"])
    ).strip()
    try:
        occupancy = float(occupancy_text)
    except (TypeError, ValueError):
        pass
    else:
        if math.isfinite(occupancy) and occupancy.is_integer():
            expected["occupancy.count"] = int(occupancy)
    return expected


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=0.0)
    return left == right


def _timestamp_microseconds(timestamp_utc: str) -> int:
    parsed = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    return int(parsed.timestamp()) * 1_000_000 + parsed.microsecond


def _git_metadata(repository_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {"git_commit": commit, "working_tree_dirty": dirty}


def evaluate_canonical_state(
    *,
    input_path: str | Path,
    config_path: str | Path = "configs/experiment.yaml",
    tables_dir: str | Path = "results/tables",
    metrics_dir: str | Path = "results/metrics",
) -> dict[str, Any]:
    """Evaluasi seluruh raw record terhadap implementasi canonical existing."""

    source = Path(input_path).expanduser().resolve()
    config_file = Path(config_path).resolve()
    table_path = Path(tables_dir)
    metric_path = Path(metrics_dir)
    if not source.is_file():
        raise FileNotFoundError(source)
    with config_file.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if str(config["data"]["source_timezone"]).upper() != "UTC":
        raise ValueError("Evaluasi canonical mensyaratkan source_timezone UTC")

    checksum = _sha256(source)
    canonical_config = config["canonical_state"]
    transformer = CanonicalStateTransformer(
        room_id=canonical_config.get("room_id"),
        schema_version=canonical_config["schema_version"],
        validation_ranges=canonical_config["validation_ranges"],
    )
    gap_threshold_seconds = float(config["preprocessing"]["gap_threshold_seconds"])

    total_records = 0
    successful_transformations = 0
    failed_transformations = 0
    schema_conforming_records = 0
    required_complete_records = 0
    data_type_valid_records = 0
    timestamp_valid_records = 0
    canonical_valid_records = 0
    localized_naive_records = 0
    converted_aware_records = 0
    non_monotonic_pairs = 0
    value_comparisons = 0
    value_mismatches = 0
    determinism_checks = 0
    determinism_failures = 0
    staleness_unavailable_records = 0
    room_id_unresolved_records = 0
    records_with_missing = 0
    records_with_type_issue = 0
    records_with_range_violation = 0
    previous_timestamp: int | None = None
    timestamps = array("q")
    field_complete_counts = Counter({field: 0 for field in EXPECTED_TELEMETRY_FIELDS})
    field_mismatch_counts = Counter({field: 0 for field in EXPECTED_TELEMETRY_FIELDS})
    quality_flags: Counter[str] = Counter()
    schema_violations: Counter[str] = Counter()
    transformation_errors: Counter[str] = Counter()
    determinism_row_numbers: set[int] = set()
    last_raw: dict[str, Any] | None = None
    last_row_number: int | None = None

    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_RAW_COLUMNS:
            raise ValueError(
                "schema CSV tidak sesuai; diharapkan "
                f"{EXPECTED_RAW_COLUMNS}, ditemukan {reader.fieldnames}"
            )
        for row_number, raw in enumerate(reader, start=2):
            total_records += 1
            last_raw = dict(raw)
            last_row_number = row_number
            try:
                state = transformer.transform(
                    raw,
                    source_row_number=row_number,
                    source_file_sha256=checksum,
                )
            except Exception as exc:  # pragma: no cover - defensive audit boundary
                failed_transformations += 1
                transformation_errors[type(exc).__name__] += 1
                continue
            successful_transformations += 1

            violations = validate_canonical_state_schema(state)
            if violations:
                schema_violations.update(violations)
            else:
                schema_conforming_records += 1

            values = _state_values(state)
            for field, value in values.items():
                if value is not None:
                    field_complete_counts[field] += 1
            if all(values[field] is not None for field in EXPECTED_TELEMETRY_FIELDS):
                required_complete_records += 1

            flags = state["data_quality"]["flags"]
            quality_flags.update(flags)
            missing_issue = any(flag.startswith("missing_") for flag in flags)
            type_issue = any(
                flag.startswith(("invalid_numeric_", "non_finite_", "non_integer_"))
                for flag in flags
            )
            range_issue = any(flag.startswith("out_of_range_") for flag in flags)
            records_with_missing += int(missing_issue)
            records_with_type_issue += int(type_issue)
            records_with_range_violation += int(range_issue)
            data_type_valid_records += int(not type_issue)
            canonical_valid_records += int(state["data_quality"]["valid"])
            staleness_unavailable_records += int(
                state["data_quality"]["staleness_seconds"] is None
            )
            room_id_unresolved_records += int(state["room_id"] == UNRESOLVED_ROOM_ID)

            timestamp_utc = state["timestamp_utc"]
            if timestamp_utc is not None:
                timestamp_valid_records += 1
                timestamp_value = _timestamp_microseconds(timestamp_utc)
                timestamps.append(timestamp_value)
                if previous_timestamp is not None and timestamp_value < previous_timestamp:
                    non_monotonic_pairs += 1
                previous_timestamp = timestamp_value
                policy = state["provenance"]["timestamp_policy"]
                localized_naive_records += int(policy == "localized_naive_as_utc")
                converted_aware_records += int(policy == "converted_offset_to_utc")

            expected = _expected_source_values(raw)
            for field, expected_value in expected.items():
                value_comparisons += 1
                if not _values_equal(values[field], expected_value):
                    value_mismatches += 1
                    field_mismatch_counts[field] += 1

            if (row_number - 2) % DETERMINISM_STRIDE_RECORDS == 0:
                repeated = transformer.transform(
                    raw,
                    source_row_number=row_number,
                    source_file_sha256=checksum,
                )
                determinism_checks += 1
                determinism_row_numbers.add(row_number)
                determinism_failures += int(repeated != state)

    if last_raw is not None and last_row_number not in determinism_row_numbers:
        first = transformer.transform(
            last_raw,
            source_row_number=last_row_number,
            source_file_sha256=checksum,
        )
        second = transformer.transform(
            last_raw,
            source_row_number=last_row_number,
            source_file_sha256=checksum,
        )
        determinism_checks += 1
        determinism_failures += int(first != second)

    sorted_timestamps = sorted(timestamps)
    duplicate_timestamp_rows = 0
    duplicate_timestamp_groups = 0
    gap_count = 0
    in_duplicate_group = False
    for index in range(1, len(sorted_timestamps)):
        difference = sorted_timestamps[index] - sorted_timestamps[index - 1]
        if difference == 0:
            duplicate_timestamp_rows += 1
            if not in_duplicate_group:
                duplicate_timestamp_groups += 1
                in_duplicate_group = True
        else:
            in_duplicate_group = False
            if difference / 1_000_000 > gap_threshold_seconds:
                gap_count += 1

    expected_cell_count = total_records * len(EXPECTED_TELEMETRY_FIELDS)
    complete_expected_cells = sum(field_complete_counts.values())
    transformation_rate = successful_transformations / total_records if total_records else 0.0
    conformity_rate = schema_conforming_records / total_records if total_records else 0.0
    completeness_rate = complete_expected_cells / expected_cell_count if expected_cell_count else 0.0
    type_validity_rate = data_type_valid_records / total_records if total_records else 0.0
    timestamp_validity_rate = timestamp_valid_records / total_records if total_records else 0.0
    preservation_rate = (
        (value_comparisons - value_mismatches) / value_comparisons
        if value_comparisons
        else 0.0
    )
    deterministic_ordering_verified = (
        successful_transformations == total_records
        and len(timestamps) == timestamp_valid_records
    )

    def evaluation_row(
        category: str,
        metric: str,
        value: Any,
        *,
        denominator: int | None = None,
        unit: str = "record",
        status: str,
        definition: str,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "metric": metric,
            "value": value,
            "denominator": "" if denominator is None else denominator,
            "rate": "" if denominator in (None, 0) else float(value) / denominator,
            "unit": unit,
            "status": status,
            "definition": definition,
        }

    evaluation_rows = [
        evaluation_row("transformation", "total_raw_records_evaluated", total_records, status="observed", definition="Seluruh baris data selain header"),
        evaluation_row("transformation", "successful_canonical_transformations", successful_transformations, denominator=total_records, status="pass" if failed_transformations == 0 else "review", definition="Transformer mengembalikan canonical state tanpa exception"),
        evaluation_row("transformation", "failed_canonical_transformations", failed_transformations, denominator=total_records, status="pass" if failed_transformations == 0 else "fail", definition="Transformer menimbulkan exception"),
        evaluation_row("schema", "schema_conforming_records", schema_conforming_records, denominator=total_records, status="pass" if schema_conforming_records == total_records else "fail", definition="Struktur, field wajib, tipe nullable, dan metadata sesuai schema canonical"),
        evaluation_row("schema", "schema_conformity_rate", conformity_rate, unit="ratio", status="pass" if conformity_rate == 1.0 else "fail", definition="schema_conforming_records / total_raw_records_evaluated"),
        evaluation_row("completeness", "complete_expected_telemetry_cells", complete_expected_cells, denominator=expected_cell_count, unit="field", status="pass" if complete_expected_cells == expected_cell_count else "review", definition="Field canonical yang bersumber langsung dari delapan field telemetry dan bernilai non-null"),
        evaluation_row("completeness", "required_field_completeness_rate", completeness_rate, unit="ratio", status="pass" if completeness_rate == 1.0 else "review", definition="Complete expected telemetry cells / seluruh expected telemetry cells; room_id tidak masuk denominator"),
        evaluation_row("type", "data_type_valid_records", data_type_valid_records, denominator=total_records, status="pass" if data_type_valid_records == total_records else "review", definition="Tidak memiliki invalid numeric, non-finite, atau non-integer flag; missing dinilai terpisah"),
        evaluation_row("timestamp", "timestamp_valid_records", timestamp_valid_records, denominator=total_records, status="pass" if timestamp_valid_records == total_records else "fail", definition="Timestamp dapat diparse dan direpresentasikan sebagai UTC"),
        evaluation_row("timestamp", "timestamp_naive_localized_as_utc", localized_naive_records, denominator=timestamp_valid_records, status="observed", definition="Clock value naive diinterpretasikan sebagai UTC tanpa pergeseran"),
        evaluation_row("timestamp", "timestamp_aware_converted_to_utc", converted_aware_records, denominator=timestamp_valid_records, status="observed", definition="Timestamp dengan offset dikonversi ke UTC"),
        evaluation_row("temporal", "non_monotonic_source_pairs", non_monotonic_pairs, status="pass" if non_monotonic_pairs == 0 else "review", definition="Pasangan timestamp berurutan dalam file dengan waktu menurun"),
        evaluation_row("temporal", "duplicate_timestamp_rows", duplicate_timestamp_rows, status="pass" if duplicate_timestamp_rows == 0 else "review", definition="Baris berlebih dengan timestamp UTC yang sama"),
        evaluation_row("temporal", "duplicate_timestamp_groups", duplicate_timestamp_groups, status="pass" if duplicate_timestamp_groups == 0 else "review", definition="Kelompok timestamp UTC dengan lebih dari satu record"),
        evaluation_row("temporal", "temporal_gaps", gap_count, status="observed", definition=f"Interval setelah pengurutan yang lebih besar dari {gap_threshold_seconds:g} detik"),
        evaluation_row("temporal", "deterministic_ordering_verified", int(deterministic_ordering_verified), unit="boolean", status="pass" if deterministic_ordering_verified else "fail", definition="Urutan canonical ditentukan oleh timestamp_utc dan source_row_number sebagai tie-breaker unik"),
        evaluation_row("quality", "canonical_valid_records", canonical_valid_records, denominator=total_records, status="pass" if canonical_valid_records == total_records else "review", definition="Record tanpa missing, invalid timestamp/type, non-finite, non-integer, atau range violation"),
        evaluation_row("correctness", "value_preservation_comparisons", value_comparisons, unit="field", status="observed", definition="Perbandingan source-to-state pada nilai sumber yang dapat diparse"),
        evaluation_row("correctness", "value_preservation_mismatches", value_mismatches, denominator=value_comparisons, unit="field", status="pass" if value_mismatches == 0 else "fail", definition="Nilai canonical berbeda dari nilai sumber setelah transformasi yang terdokumentasi"),
        evaluation_row("correctness", "value_preservation_rate", preservation_rate, unit="ratio", status="pass" if preservation_rate == 1.0 else "fail", definition="Perbandingan source-to-state yang mempertahankan nilai / seluruh perbandingan"),
        evaluation_row("determinism", "records_rechecked", determinism_checks, status="observed", definition=f"Record pertama, terakhir, dan setiap {DETERMINISM_STRIDE_RECORDS:,} record ditransformasikan ulang"),
        evaluation_row("determinism", "determinism_failures", determinism_failures, denominator=determinism_checks, status="pass" if determinism_failures == 0 else "fail", definition="Transformasi ulang raw record yang sama menghasilkan representasi berbeda"),
    ]

    mapping_rows = []
    for row in FIELD_MAPPING_ROWS:
        enriched = dict(row)
        field = row["canonical_field"]
        enriched.update(
            {
                "evaluated_records": total_records,
                "non_null_canonical_values": field_complete_counts[field],
                "completeness_rate": (
                    field_complete_counts[field] / total_records if total_records else 0.0
                ),
                "value_mismatches": field_mismatch_counts[field],
                "mapping_status": "pass" if field_mismatch_counts[field] == 0 else "fail",
            }
        )
        mapping_rows.append(enriched)

    quality_rows: list[dict[str, Any]] = []

    def quality_row(
        category: str,
        item: str,
        count: int,
        denominator: int | None,
        status: str,
        interpretation: str,
    ) -> None:
        quality_rows.append(
            {
                "category": category,
                "item": item,
                "count": count,
                "denominator": "" if denominator is None else denominator,
                "rate": "" if denominator in (None, 0) else count / denominator,
                "status": status,
                "interpretation": interpretation,
            }
        )

    for field in EXPECTED_TELEMETRY_FIELDS:
        quality_row(
            "expected_from_telemetry",
            field,
            field_complete_counts[field],
            total_records,
            "complete" if field_complete_counts[field] == total_records else "incomplete",
            "Masuk denominator required-field completeness",
        )
    quality_row("metadata", "room_id_resolved", total_records - room_id_unresolved_records, total_records, "unresolved_by_source" if room_id_unresolved_records else "resolved", "Tidak masuk denominator telemetry; CSV tidak menyediakan identitas ruang")
    quality_row("derived_quality", "data_quality.valid_available", successful_transformations, total_records, "available", "Boolean diturunkan dari rule missing, timestamp, tipe, finite, integer, dan range")
    quality_row("derived_quality", "staleness_seconds_available", total_records - staleness_unavailable_records, None, "unavailable_by_design", "Tidak dinilai sebagai incomplete karena timestamp kamera independen tidak tersedia")
    quality_row("validation_behavior", "records_with_missing_required_field", records_with_missing, total_records, "pass" if records_with_missing == 0 else "flagged", "Missing dipertahankan sebagai null dan menghasilkan missing_* flag")
    quality_row("validation_behavior", "records_with_invalid_type", records_with_type_issue, total_records, "pass" if records_with_type_issue == 0 else "flagged", "Invalid numeric, non-finite, dan non-integer menghasilkan flag dan valid=false")
    quality_row("validation_behavior", "records_with_invalid_timestamp", quality_flags["invalid_timestamp"], total_records, "pass" if quality_flags["invalid_timestamp"] == 0 else "flagged", "Timestamp invalid menjadi null dan valid=false")
    quality_row("validation_behavior", "records_with_range_violation", records_with_range_violation, total_records, "pass" if records_with_range_violation == 0 else "flagged", "Nilai dipertahankan tetapi valid=false sesuai range konfigurasi")
    quality_row("limitation", "occupancy_staleness_calculable", 0, None, "not_evaluable", "Tidak ada timestamp kamera independen; staleness_seconds tetap null")

    evaluation_output = table_path / "canonical_state_evaluation.csv"
    mapping_output = table_path / "canonical_field_mapping.csv"
    quality_output = table_path / "digital_twin_data_quality.csv"
    _write_csv(evaluation_output, list(evaluation_rows[0]), evaluation_rows)
    _write_csv(mapping_output, list(mapping_rows[0]), mapping_rows)
    _write_csv(quality_output, list(quality_rows[0]), quality_rows)

    repository_root = Path.cwd().resolve()
    code_paths = [Path(__file__), Path(__file__).with_name("canonical.py")]
    manifest = {
        "stage": 5,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": source.name,
        "input_sha256": checksum,
        "config_sha256": _sha256(config_file),
        "code_sha256": {
            str(path.relative_to(repository_root)): _sha256(path) for path in code_paths
        },
        **_git_metadata(repository_root),
        "schema_version": canonical_config["schema_version"],
        "summary": {
            "total_raw_records_evaluated": total_records,
            "successful_canonical_transformations": successful_transformations,
            "failed_canonical_transformations": failed_transformations,
            "schema_conforming_records": schema_conforming_records,
            "schema_conformity_rate": conformity_rate,
            "required_field_completeness_rate": completeness_rate,
            "data_type_validity_rate": type_validity_rate,
            "timestamp_validity_rate": timestamp_validity_rate,
            "value_preservation_rate": preservation_rate,
            "determinism_checks": determinism_checks,
            "determinism_failures": determinism_failures,
            "non_monotonic_source_pairs": non_monotonic_pairs,
            "duplicate_timestamp_rows": duplicate_timestamp_rows,
            "temporal_gaps": gap_count,
            "room_id_unresolved_records": room_id_unresolved_records,
            "staleness_unavailable_records": staleness_unavailable_records,
        },
        "validation_counters": {
            "quality_flags": dict(sorted(quality_flags.items())),
            "schema_violations": dict(sorted(schema_violations.items())),
            "transformation_errors": dict(sorted(transformation_errors.items())),
        },
        "limitations": [
            "Tidak tersedia timestamp independen camera capture.",
            "Tidak tersedia timestamp independen sensor measurement.",
            "Tidak tersedia timestamp independen gateway arrival.",
            "Tidak tersedia timestamp independen cloud ingestion.",
            "Physical-to-digital latency, occupancy staleness, exact camera-sensor synchronization, dan end-to-end synchronization performance tidak dapat dihitung.",
        ],
        "official_outputs": {
            "canonical_state_evaluation": str(evaluation_output),
            "canonical_field_mapping": str(mapping_output),
            "digital_twin_data_quality": str(quality_output),
        },
    }
    metric_path.mkdir(parents=True, exist_ok=True)
    manifest_output = metric_path / "canonical_state_evaluation_manifest.json"
    temporary_manifest = manifest_output.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary_manifest, manifest_output)

    return {
        "dataset_sha256": checksum,
        **manifest["summary"],
        "output_paths": {**manifest["official_outputs"], "manifest": str(manifest_output)},
    }
