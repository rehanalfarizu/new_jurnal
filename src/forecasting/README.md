# Modul forecasting

`pipeline.py` menjalankan forecasting foundation Tahap 3 dan `cli.py` menyediakan command-line interface.

Pipeline membangun tiga baseline:

1. Persistence: `prediction(t+30) = power(t)`.
2. Historical power Ridge: power history dan time features.
3. Non-occupancy multivariate Ridge: historical power, time, temperature, humidity, voltage, dan current.

Scaler hanya fit pada train. Candidate `alpha` Ridge dipilih menggunakan validation MAE. Test hanya digunakan setelah konfigurasi dipilih. Semua model memakai common usable timestamps dan target yang sama.

Pipeline menyimpan tabel, metrik, prediksi test, execution manifest, serta dua figure. Tidak ada occupancy feature, random split, deep learning, atau tuning berbasis test pada Tahap 3.
