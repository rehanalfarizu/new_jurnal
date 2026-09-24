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

Tahap 4 menambahkan:

| File | Isi |
| --- | --- |
| `occupancy_ablation_comparison.csv` | Perbandingan control dan treatment beserta delta |
| `occupancy_level_error.csv` | Test MAE control/treatment untuk occupancy 0–5 |
| `fair_ablation_check.csv` | Verifikasi timestamp, target, split, model family, tuning, dan preprocessing |
| `occupancy_ablation_validation_tuning.csv` | Candidate `alpha` control dan treatment |
| `occupancy_ablation_feature_definition.csv` | Definisi feature control dan treatment |

Definisi terminologi Tahap 4: `delta_mae = MAE_treatment - MAE_control`, sedangkan `mae_improvement = MAE_control - MAE_treatment`. Treatment menggunakan tepat 11 occupancy features yang tercatat pada `occupancy_ablation_feature_definition.csv`.

Tahap 5 menambahkan:

| File | Isi |
| --- | --- |
| `canonical_state_evaluation.csv` | Metrik transformasi, schema conformity, completeness, validitas tipe/timestamp, temporal integrity, preservasi nilai, dan determinisme |
| `canonical_field_mapping.csv` | Mapping delapan field sumber ke canonical field, tipe, unit, transformasi, rule, completeness, dan mismatch aktual |
| `digital_twin_data_quality.csv` | Completeness per kategori, metadata unresolved, derived quality fields, dan behavior quality flags |

`room_id` dan `staleness_seconds` dipisahkan dari denominator completeness telemetry agar keterbatasan sumber tidak disamarkan sebagai kehilangan field sensor.
