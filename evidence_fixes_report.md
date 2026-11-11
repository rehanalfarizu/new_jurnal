# Evidence Fixes Report

Branch: `evidence-fixes`  
Generated: 2026-11-11

## Summary

All verification evidence has been added. No existing results, metrics, configs, or frozen artifacts were modified.

### Test Results

- **Total tests**: 54
- **Passed**: 54
- **Failed**: 0

### Key Findings

| Task | Result |
|------|--------|
| Reproduction max_abs_diff | **1.73e-18** (well within 1e-9 tolerance) |
| Hourly power range | 0.4224 W (1.14% of mean) |
| Hourly occupancy range | 0.1308 persons (4.24% of mean) |
| Raw excerpt SHA-256 | **MATCH** |

---

## Task 1: Reproducibility Check

**Status**: PASS (max_abs_diff = 1.73e-18 ≤ 1e-9)

| File | Location |
|------|----------|
| scripts/verify_reproduction.py | lines 1-163 (new) |
| tests/test_reproduction.py | lines 1-52 (new) |
| results/tables/reproduction_check.csv | generated |
| results/metrics/reproduction_check.json | generated |

Command: `python scripts/verify_reproduction.py`

---

## Task 2: Hourly Profile Table

**Status**: Complete

| File | Location |
|------|----------|
| scripts/build_hourly_profile.py | lines 1-145 (new) |
| results/tables/hourly_profile.csv | generated (24 rows, hours 0-23) |
| results/tables/hourly_profile_summary.csv | generated (11 summary metrics) |

Command: `python scripts/build_hourly_profile.py`

**Results**:
- Power: overall mean 36.93 W, hourly range 36.70–37.12 W (1.14% variation)
- Occupancy: overall mean 3.09 persons, hourly range 3.02–3.15 (4.24% variation)

---

## Task 3: Residual Sign Test

**Status**: Complete

| File | Location |
|------|----------|
| scripts/generate_publication_figures.py | line 6-7 (docstring updated) |
| scripts/generate_publication_figures.py | lines 484-497 (test_residual_sign_convention function added) |

Command: `python scripts/generate_publication_figures.py --test-residual-sign`

Convention: `residual = prediction - actual`. Negative residual means underprediction.

---

## Task 4: Data Availability Check

**Status**: All files present, SHA-256 verified

| Item | Path | Status |
|------|------|--------|
| (a) Frozen predictions | results/metrics/test_predictions.csv | FOUND |
| (a) Frozen predictions | results/metrics/occupancy_ablation_test_predictions.csv | FOUND |
| (b) Metric tables | results/metrics/*.csv | FOUND (5 files) |
| (c) Raw telemetry excerpt | docs/evidence/raw_dataset_sample.csv | FOUND |
| (d) SHA-256 checksum | docs/evidence/raw_dataset_sample_manifest.json | FOUND |
| (e) LICENSE (MIT) | LICENSE | FOUND |
| (f) Tag experiment-v1.0 | git tag | FOUND |

**SHA-256 Verification**:
- Stored: `fc3bb83295cf528e230b30f2e5a89f4dc06ac2df27a48ed11ba7264d90f19462`
- Computed: `fc3bb83295cf528e230b30f2e5a89f4dc06ac2df27a48ed11ba7264d90f19462`
- Result: **MATCH**

---

## Task 5: Registration

| File | Location |
|------|----------|
| results/metrics/evidence_fixes_manifest.json | generated (new, checksums for all new files) |
| README.md | Verification section added at end |

---

## Files Added

| Path | Purpose |
|------|---------|
| scripts/verify_reproduction.py | Reproduction check script |
| scripts/build_hourly_profile.py | Hourly profile builder |
| tests/test_reproduction.py | Reproduction test |
| results/tables/reproduction_check.csv | Reproduction comparison table |
| results/metrics/reproduction_check.json | Reproduction manifest |
| results/tables/hourly_profile.csv | Hourly statistics (24 hours) |
| results/tables/hourly_profile_summary.csv | Profile summary metrics |
| results/metrics/evidence_fixes_manifest.json | New files manifest |
| evidence_fixes_report.md | This report |

## Files Modified

| Path | Change |
|------|--------|
| scripts/generate_publication_figures.py | Docstring + test function added |
| README.md | Verification section added |

---

## Not Pushed

This branch has not been pushed or tagged. To push:

```bash
git add -A
git commit -m "Add verification evidence for reviewer response"
git push -u origin evidence-fixes
```
