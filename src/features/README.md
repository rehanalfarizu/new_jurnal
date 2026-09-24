# Modul feature engineering

`time_series.py` menyediakan resampling satu menit, target 30 menit, dan feature forecasting tanpa occupancy.

Mean digunakan untuk temperature, humidity, voltage, current, dan power. Occupancy diagregasikan dengan last valid observation dalam minute-bin, tetapi tidak masuk ke feature model Tahap 3. Bin tanpa telemetry tetap missing.

Power lag menggunakan offset 1, 5, 15, dan 30 menit. Rolling mean dan sample standard deviation menggunakan window 5, 15, dan 30 menit yang berakhir pada t. Seluruh source offset maksimum adalah nol sehingga tidak ada future value yang dipakai sebagai feature.

Daftar feature yang menjadi sumber konfigurasi berada di `configs/features.yaml`; definisi machine-readable dihasilkan pada `results/tables/feature_definition.csv`.

Treatment Tahap 4 menambahkan current occupancy, lag occupancy 1/5/15/30 menit, serta rolling mean dan maximum occupancy 5/15/30 menit. Seluruh feature tersebut menggunakan informasi pada atau sebelum t dan tidak melakukan forward-fill pada gap.
