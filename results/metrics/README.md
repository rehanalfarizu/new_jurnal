# Metrik forecasting

- `forecast_metrics.csv` menyimpan MAE, RMSE, dan R² untuk validation serta test.
- `test_predictions.csv` menyimpan timestamp, target timestamp, actual power, dan prediksi ketiga baseline pada common test samples.
- `forecast_run_manifest.json` menyimpan checksum input, konfigurasi, kode pipeline, random seed, audit scaler, dan model yang dipilih dari validation untuk figure.

MAE dan RMSE menggunakan Watt. File ini tidak menyatakan energy dalam Wh dan tidak menjadi bukti energy saving.
