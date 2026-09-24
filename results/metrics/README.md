# Metrik forecasting

- `forecast_metrics.csv` menyimpan MAE, RMSE, dan R² untuk validation serta test.
- `test_predictions.csv` menyimpan timestamp, target timestamp, actual power, dan prediksi ketiga baseline pada common test samples.
- `forecast_run_manifest.json` menyimpan checksum input, konfigurasi, kode pipeline, random seed, audit scaler, dan model yang dipilih dari validation untuk figure.

MAE dan RMSE menggunakan Watt. File ini tidak menyatakan energy dalam Wh dan tidak menjadi bukti energy saving.

Artefak Tahap 4:

- `occupancy_ablation_metrics.csv`: validation/test MAE, RMSE, dan R² control serta treatment.
- `occupancy_ablation_bootstrap.csv`: moving-block bootstrap confidence interval untuk `mae_improvement = MAE_control - MAE_treatment`; batas interval memakai nama `mae_improvement_ci_lower_w` dan `mae_improvement_ci_upper_w`.
- `occupancy_ablation_test_predictions.csv`: target dan prediksi control/treatment pada common test samples.
- `occupancy_ablation_manifest.json`: checksum, commit, konfigurasi, model audit, dan path output resmi.

Artefak Tahap 5:

- `canonical_state_evaluation_manifest.json`: checksum dataset/config/source code, ringkasan evaluasi canonical, validation counters, limitations, dan path tabel resmi.
