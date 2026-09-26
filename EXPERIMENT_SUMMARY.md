# Ringkasan eksperimen terverifikasi

Dokumen ini adalah single source of verified experimental facts untuk repository penelitian. Seluruh angka berasal dari output aktual di `results/`; tidak ada hasil literatur, novelty claim, atau hasil eksperimen baru di dalam dokumen ini.

## 1. Judul penelitian

**A Canonical-State Digital Twin Framework for Occupancy-Aware Smart-Room Power Forecasting and Decision Support**

## 2. Research questions

- **RQ1:** Bagaimana telemetry lingkungan, listrik, dan occupancy dapat diintegrasikan menjadi Canonical Twin State yang konsisten untuk smart room?
- **RQ2:** Seberapa akurat framework memprediksi power smart room 30 menit ke depan?
- **RQ3:** Apakah occupancy memberikan incremental predictive value untuk forecasting power 30 menit ke depan?
- **RQ4:** Bagaimana current Twin State, occupancy, dan forecast diterjemahkan menjadi recommendation decision support yang transparan?

## 3. Provenance dataset

Rantai provenance yang didokumentasikan adalah:

```text
Physical Room
  → Sensor / Camera
  → ESP32 / Raspberry Pi
  → Gateway
  → Azure / Cloud
  → Historical Storage
  → CSV Export
  → UTC Normalization
  → Validation
  → Canonical Twin State
```

CSV hanya menyimpan satu timestamp gabungan. Timestamp independen untuk camera capture, sensor measurement, gateway arrival, dan cloud ingestion tidak tersedia. Occupancy harus ditafsirkan sebagai latest available camera snapshot; nearest-timestamp synchronization tidak dapat dibuktikan.

- File sumber: `sensor_data.csv`
- SHA-256: `ca7831a188a191edbf82a673fac90dbb875b5095986ed07699c02530f2a02a0e`
- Device ID: `RASPBERRY_PI_GATEWAY_001`
- Jumlah gateway: 1
- `room_id`: `unresolved`

## 4. Karakteristik dataset

- Jumlah record: **2.027.520**
- Jumlah kolom: **8**
- Waktu awal: **2026-02-23T23:14:43.896301Z**
- Waktu akhir: **2026-05-24T01:22:06.727676Z**
- Durasi observasi: **7.697.242,831375 detik**
- Presisi timestamp sumber: mikrodetik
- Timestamp naive: **2.027.520**, semuanya diinterpretasikan sebagai UTC tanpa mengubah clock value

Statistik deskriptif resmi:

| Variabel | Unit | Count | Mean | Sample std | Minimum | Median | Maximum |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Temperature | °C | 2.027.520 | 30.1882226562512 | 1.84747819868381 | 26 | 30.5 | 33.9 |
| Humidity | % | 2.027.520 | 66.6261501736095 | 8.45354963144361 | 47 | 69 | 82 |
| Voltage | V | 2.027.520 | 227.044458550349 | 7.26150304728912 | 197.8 | 227.5 | 250.9 |
| Current | A | 2.027.520 | 0.162633257378472 | 0.0117584308510863 | 0.12 | 0.16 | 2.2 |
| Power | W | 2.027.520 | 36.9326713324678 | 3.07721863006936 | 25.4 | 36.8 | 484 |
| Occupancy | orang | 2.027.520 | 3.08495008680549 | 1.3868648962402 | 0 | 3 | 5 |

## 5. Temuan kualitas data

- Missing cells: **0**
- Malformed-width rows: **0**
- Timestamp parse failures: **0**
- Exact duplicate rows: **0**
- Duplicate timestamp rows: **0**
- Non-monotonic source pairs: **0**
- Numeric type issues: **0**
- Nilai di luar validation range: **0**
- Temporal gaps lebih dari 60 detik: **176**
- IQR outlier values: **188.958**
- Record dengan `room_id` unresolved: **2.027.520**
- Occupancy staleness calculable: **false**

IQR outlier merupakan indikator eksploratif, bukan error otomatis. Nilai tersebut dipertahankan dan dilaporkan.

## 6. Canonical Twin State

Schema version: `1.0.0-research`.

Struktur utama mencakup `timestamp_utc`, `room_id`, `device_id`, `environment`, `electrical`, `occupancy`, `data_quality`, dan `provenance`. Nilai `room_id` tetap `unresolved`. Nilai `staleness_seconds` tetap `null` karena timestamp kamera independen tidak tersedia.

Hasil evaluasi empiris:

- Raw records evaluated: **2.027.520**
- Successful transformations: **2.027.520**
- Failed transformations: **0**
- Schema-conforming records: **2.027.520**
- Schema conformity rate: **1.0**
- Required-field completeness rate: **1.0**
- Data-type validity rate: **1.0**
- Timestamp validity rate: **1.0**
- Value-preservation comparisons: **16.220.160**
- Value-preservation mismatches: **0**
- Value-preservation rate: **1.0**
- Records rechecked for determinism: **204**
- Determinism failures: **0**

## 7. Protokol preprocessing

- Raw CSV dibaca tanpa ditimpa.
- Timestamp diparse dan timestamp naive dilokalisasikan sebagai UTC tanpa menggeser clock value.
- Record disusun kronologis.
- Missing, duplicate, gap, range violation, dan outlier dideteksi serta dilaporkan.
- Tidak ada imputasi, interpolasi, penghapusan outlier, atau penghapusan duplikasi secara diam-diam.
- Grid modeling menggunakan cadence **1 menit**.
- Temperature, humidity, voltage, current, dan power diagregasikan dengan mean per menit.
- Occupancy menggunakan last valid observation dalam minute-bin.
- Gap-fill policy: `none`.

Ringkasan grid modeling:

- Minute bins total: **128.289**
- Minute bins dengan telemetry: **127.445**
- Minute bins lengkap: **127.445**
- Minute bins missing: **844**
- Minute bins partial: **0**
- Common usable modeling samples: **121.698**
- Samples not used: **6.591**

## 8. Protokol forecasting

Target didefinisikan tepat berdasarkan waktu:

```text
target_power_30m(t) = power_w(t + 30 menit)
```

- Target unit: Watt
- Forecast horizon: 30 menit
- Split: chronological train/validation/test
- Train fraction: 0,70
- Validation fraction: 0,15
- Test fraction: 0,15
- Usable train samples: **85.242**
- Usable validation samples: **18.330**
- Usable test samples: **18.126**
- Target yang melintasi split boundary dikeluarkan.
- Scaler di-fit hanya pada train.
- Ridge alpha candidates: **0.1, 1.0, 10.0, 100.0**
- Pemilihan alpha menggunakan validation MAE.
- Model family tidak diubah antarperbandingan Ridge.

## 9. Hasil baseline

Hasil validation dan held-out test:

| Model | Selected alpha | Validation MAE (W) | Validation RMSE (W) | Validation R² | Test MAE (W) | Test RMSE (W) | Test R² |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Persistence | N/A | 1.1688996877125792 | 1.855404879447844 | 0.5715254501030278 | 1.1759198533484814 | 1.729499839998615 | 0.5982790418728454 |
| Historical-power Ridge | 100.0 | 1.12152247977447 | 1.7892582133585224 | 0.6015317877093125 | 1.123551294127783 | 1.6493779635376211 | 0.6346376320870958 |
| Non-occupancy multivariate Ridge | 0.1 | 1.0748017022926186 | 1.7601478373812938 | 0.6143920889721102 | 1.0800989673662498 | 1.6208652205943326 | 0.6471604620985363 |

Non-occupancy multivariate Ridge dipilih untuk figure berdasarkan validation MAE. Pemilihan tersebut bukan hasil pemilihan pada test.

## 10. Occupancy ablation

Control dan treatment menggunakan timestamp, target, split, preprocessing, model family, candidate alpha, dan tuning metric yang sama.

| Model | Role | Feature count | Occupancy features | Alpha | Test MAE (W) | Test RMSE (W) | Test R² |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Non-occupancy multivariate Ridge | Control | 20 | 0 | 0.1 | 1.0800989673662498 | 1.6208652205943326 | 0.6471604620985363 |
| Occupancy multivariate Ridge | Treatment | 31 | 11 | 10.0 | 1.0693887584729078 | 1.600945021043651 | 0.6557798629802756 |

Perbedaan treatment terhadap control:

- `delta_mae = MAE_treatment - MAE_control`: **-0.010710208893341955 W**
- `delta_rmse = RMSE_treatment - RMSE_control`: **-0.019920199550681472 W**
- `delta_r2 = R²_treatment - R²_control`: **0.008619400881739292**
- `mae_improvement = MAE_control - MAE_treatment`: **0.010710208893341955 W**
- MAE percentage improvement: **0.991595142383859%**

Angka tersebut adalah perbedaan prediktif pada test set, bukan efek kausal occupancy.

## 11. Ketidakpastian bootstrap

- Method: `moving_block_bootstrap_paired_absolute_error_improvement`
- Metric: `mae_control_minus_mae_treatment`
- Block size: **1.440 samples**
- Iterations: **1.000**
- Confidence level: **0.95**
- Observed MAE improvement: **0.010710208893341957 W**
- CI lower: **-0.006179538217266726 W**
- CI upper: **0.021583038929722683 W**
- `supports_positive_improvement`: **false**

Confidence interval mencakup nol. Hasil ini tidak mendukung klaim bahwa positive improvement telah ditunjukkan secara meyakinkan oleh konfigurasi bootstrap tersebut.

## 12. Evaluasi Digital Twin / Canonical State

Evaluasi Tahap 5 memverifikasi schema conformity, completeness, timestamp validity, data-type validity, value preservation, temporal integrity, quality flags, dan determinisme. Seluruh 2.027.520 record berhasil ditransformasikan dan sesuai schema. Evaluasi tersebut tidak mengukur physical-to-digital latency, occupancy staleness, exact camera-sensor synchronization, atau end-to-end synchronization performance.

## 13. Decision-Support Scenario Evaluation

Decision support menggunakan current state serta output forecast occupancy-aware 30 menit. Model forecasting tidak dilatih ulang pada Tahap 6.

```text
forecast_delta_w = forecast_power_30m_w - current_power_w
```

Threshold numerik adalah declared research scenario threshold, bukan safety limit atau validated comfort standard.

| Rule | Kondisi | Recommendation count |
| --- | --- | ---: |
| `DS-RULE-000` | Input missing/invalid | 0 |
| `DS-RULE-001` | Occupancy = 0 dan current atau forecast power > 40 W | 45 |
| `DS-RULE-002` | Forecast delta > 2 W | 45 |
| `DS-RULE-003` | Occupancy > 0 dan temperature > 32 °C atau humidity > 75% | 4.228 |
| `DS-RULE-004` | Tidak ada active rule | 13.808 |

Ringkasan evaluasi:

- Evaluated samples: **18.126**
- Recommendation traces: **18.126**
- Samples dengan active recommendation: **4.318**
- Recommendation coverage: **0.23822133951230276**
- No-action count: **13.808**
- Invalid input count: **0**
- Multiple-recommendation samples: **0**
- Contradictory recommendation count: **0**
- Determinism failure count: **0**
- Consistency checks: **9 PASS**

Evaluasi ini tidak mempunyai data accept/reject manusia atau measured post-recommendation outcome.

## 14. Informasi reproducibility

- Random seed: **42**
- Konfigurasi: `configs/experiment.yaml`, `configs/features.yaml`, dan `configs/decision_support.yaml`
- Source of truth: `src/preprocessing/`, `src/twin_state/`, `src/features/`, `src/forecasting/`, `src/evaluation/`, dan `src/decision_support/`
- Notebook reproducibility: `notebooks/01_dataset_exploration.ipynb` sampai `notebooks/06_decision_support_analysis.ipynb`
- Unit-test baseline: **40 PASS, 0 FAIL**
- Manifest eksperimen mempertahankan commit dan dirty-state historis saat setiap eksperimen dijalankan; nilai tersebut tidak diperbarui saat pre-freeze cleanup.

## 15. Keterbatasan

- Dataset hanya mencakup satu gateway, satu sistem, dan satu periode observasi.
- Identitas fisik ruang tidak tersedia; `room_id` tetap `unresolved`.
- Timestamp independen kamera, sensor, gateway, dan cloud tidak tersedia.
- Occupancy menggunakan latest available camera snapshot dan belum mempunyai labeled accuracy benchmark.
- Generalisasi lintas ruang, bangunan, perangkat, musim, atau kondisi operasional belum diuji.
- Target adalah power dalam Watt, bukan energy dalam Wh.
- Bootstrap occupancy ablation menghasilkan confidence interval yang mencakup nol.
- Threshold decision support belum mempunyai basis literatur atau validasi kenyamanan.
- Tidak tersedia accept/reject recommendation, tindakan aktual, counterfactual energy, atau post-action outcome.

## 16. Klaim yang didukung

- Dataset yang diaudit memiliki 2.027.520 record, delapan kolom, satu gateway, dan checksum yang tercatat di atas.
- Pipeline dapat merepresentasikan seluruh record dataset sebagai Canonical Twin State yang conforming terhadap schema penelitian, dengan preservasi nilai dan determinisme sesuai pemeriksaan yang dilaporkan.
- Baseline forecasting menghasilkan metrik validation dan held-out test yang tercatat pada tabel resmi untuk protokol temporal penelitian ini.
- Treatment occupancy-aware mempunyai error point estimate yang sedikit lebih rendah daripada control pada paired test samples.
- Rule decision support menghasilkan trace deterministik dan konsisten pada sample evaluasi historis dengan konfigurasi threshold yang dinyatakan secara eksplisit.

## 17. Klaim yang tidak didukung

- Novelty ilmiah hanya berdasarkan artefak repository.
- Efek kausal occupancy terhadap power atau error forecasting.
- Positive occupancy improvement yang konklusif; bootstrap CI mencakup nol.
- Energy saving aktual atau energy optimization.
- Human-in-the-loop effectiveness.
- Autonomous control atau autonomous optimization.
- Validated comfort optimization atau safety classification.
- Physical-to-digital latency, occupancy staleness, exact synchronization, atau end-to-end latency.
- Generalisasi lintas ruang, bangunan, perangkat, musim, atau dataset lain.

## 18. Path evidence resmi

### Dataset dan preprocessing

- `results/tables/dataset_summary.csv`
- `results/tables/data_quality_summary.csv`
- `results/tables/preprocessing_report.csv`
- `results/tables/descriptive_statistics.csv`
- `results/tables/duplicate_summary.csv`
- `results/tables/temporal_gaps.csv`
- `results/tables/outlier_summary.csv`

### Forecasting

- `results/tables/modeling_dataset_summary.csv`
- `results/tables/sample_exclusion_summary.csv`
- `results/tables/temporal_split.csv`
- `results/tables/feature_definition.csv`
- `results/tables/baseline_model_comparison.csv`
- `results/metrics/forecast_metrics.csv`
- `results/metrics/test_predictions.csv`
- `results/metrics/forecast_run_manifest.json`
- `results/figures/forecast_actual_vs_predicted.png`
- `results/figures/forecast_error_distribution.png`

### Occupancy ablation

- `results/tables/occupancy_ablation_comparison.csv`
- `results/tables/fair_ablation_check.csv`
- `results/tables/occupancy_level_error.csv`
- `results/metrics/occupancy_ablation_metrics.csv`
- `results/metrics/occupancy_ablation_bootstrap.csv`
- `results/metrics/occupancy_ablation_test_predictions.csv`
- `results/metrics/occupancy_ablation_manifest.json`

### Canonical Twin State

- `results/tables/canonical_state_evaluation.csv`
- `results/tables/canonical_field_mapping.csv`
- `results/tables/digital_twin_data_quality.csv`
- `results/metrics/canonical_state_evaluation_manifest.json`

### Decision support

- `results/tables/decision_support_scenarios.csv`
- `results/tables/decision_support_rule_summary.csv`
- `results/tables/decision_support_consistency.csv`
- `results/metrics/decision_support_manifest.json`
- `results/figures/decision_support_rule_frequency.png`
- `results/figures/decision_support_occupancy_distribution.png`
- `results/figures/decision_support_forecast_delta.png`
