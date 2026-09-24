# Modul preprocessing

Modul ini menyediakan eksplorasi dataset dan preprocessing yang dapat dijalankan ulang melalui `python3 -m src.preprocessing.cli`.

Pipeline melakukan:

1. validasi delapan kolom input;
2. perhitungan SHA-256;
3. parse timestamp serta lokalisasi UTC tanpa pergeseran clock value;
4. pemeriksaan urutan dan external sort saat menulis dataset canonical;
5. validasi tipe, missing value, exact duplicate, duplicate timestamp, range, dan outlier IQR;
6. distribusi interval sampling dan daftar temporal gap;
7. statistik deskriptif serta distribusi setiap variabel; dan
8. audit jumlah record sebelum, sesudah, terdampak, alasan, dan tindakan.

Data mentah hanya dibaca. Exact duplicate dihitung menggunakan indeks SQLite sementara. Missing value, duplikasi, gap, dan outlier dipertahankan serta dilaporkan; pipeline tidak melakukan imputasi, winsorization, resampling, atau penghapusan pada Tahap 2.

Subcommand `preprocess` menulis CSV canonical terurut dengan external sort sehingga tidak harus memuat seluruh raw record ke memori. Tidak ada train/test split atau forecasting dalam modul ini.
