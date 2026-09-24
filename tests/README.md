# Pengujian

Empat belas unit test saat ini memverifikasi:

- lokalisasi timestamp naive sebagai UTC tanpa pergeseran;
- canonical twin state dan missing-versus-zero;
- outlier dipertahankan dan diberi flag;
- exact duplicate, missing value, gap, dan pengurutan preprocessing;
- agregasi satu menit dan occupancy last valid observation;
- minute-bin kosong tetap missing;
- target tepat 30 menit berdasarkan timestamp grid;
- horizon target yang melintasi gap tidak usable;
- rolling feature tidak dipengaruhi future values;
- metadata seluruh feature memiliki source offset maksimum non-future;
- chronological ordering dan boundary split;
- target tidak melintasi split boundary; serta
- scaler hanya fit pada train.

Jalankan dengan `python3 -m unittest discover -s tests -v`.
