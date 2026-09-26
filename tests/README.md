# Pengujian

Empat puluh unit test saat ini memverifikasi:

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
- treatment merupakan control dengan tambahan occupancy features;
- seluruh occupancy feature bersifat non-future; serta
- moving-block bootstrap berpasangan bersifat deterministik untuk seed yang sama.
- daftar treatment berisi tepat 11 occupancy features;
- invalid timestamp, missing required field, dan incorrect numeric type menghasilkan quality flag yang sesuai;
- schema validator mendeteksi field canonical yang hilang dan tipe nested yang salah;
- raw record yang sama menghasilkan canonical representation yang sama;
- nilai device, lingkungan, listrik, dan occupancy dipertahankan oleh transformasi;
- `room_id` unresolved tidak membuat telemetry valid menjadi invalid;
- `staleness_seconds` tetap `None` tanpa timestamp independen; serta
- pipeline evaluasi Tahap 5 menghasilkan tabel schema, mapping, data quality, dan manifest dari data uji sintetis.
- rule decision support A–D memakai threshold konfigurasi dan comparator yang eksplisit;
- `forecast_delta_w` dihitung sebagai forecast 30 menit dikurangi current power;
- setiap recommendation memiliki reason, threshold trace, dan ID deterministik;
- missing occupancy berbeda dari occupancy nol dan missing forecast tidak dianggap nol;
- input non-finite menghasilkan trace invalid input;
- no-action dapat dihasilkan dan konflik no-action versus active recommendation dapat dideteksi; serta
- input decision-support identik menghasilkan output identik.

Jalankan dengan `python3 -m unittest discover -s tests -v`.
