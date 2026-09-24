# Hasil yang dihasilkan kode

Direktori ini berisi artefak yang dibuat oleh pipeline penelitian.

- `tables/`: ringkasan modeling dataset, feature, split, tuning, dan perbandingan baseline.
- `metrics/`: metrik validation/test, prediksi test, dan execution manifest.
- `figures/`: actual-vs-predicted dan distribusi forecast error.

Nilai tidak ditulis manual. Semua artefak Tahap 3 dapat dibuat ulang dengan CLI forecasting dan konfigurasi yang dicatat.

Tahap 4 menambahkan control-versus-treatment occupancy ablation, paired predictions, error per occupancy level, fair-ablation checks, dan moving-block bootstrap. Notebook hanya membaca artefak resmi tersebut atau memanggil pipeline untuk meregenerasinya.

Tahap 5 menambahkan evaluasi empiris Canonical Twin State: schema conformity, source-to-state mapping, completeness yang dipisahkan berdasarkan kategori, temporal integrity, data-quality behavior, preservasi nilai, dan determinisme. Evaluasi ini tidak menjalankan forecasting.
