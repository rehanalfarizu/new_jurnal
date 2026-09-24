# Tabel hasil

Tabel Tahap 2 tetap dipertahankan. Tahap 3 menambahkan:

| File | Isi |
| --- | --- |
| `modeling_dataset_summary.csv` | Raw record, minute-bin, missing bin, dan sample usable |
| `sample_exclusion_summary.csv` | Alasan eksklusif setiap sample tidak digunakan |
| `power_resampling_comparison.csv` | Dampak agregasi satu menit terhadap distribusi power |
| `feature_definition.csv` | Feature, unit, grup, dan source time offset |
| `temporal_split.csv` | Boundary UTC serta jumlah bin/sample per split |
| `validation_tuning.csv` | Candidate `alpha` dan metrik validation |
| `baseline_model_comparison.csv` | Metrik validation/test untuk seluruh baseline |

Seluruh tabel dibuat oleh `src.forecasting.pipeline`. Model dibandingkan pada common usable timestamps dan occupancy tidak digunakan sebagai feature.
