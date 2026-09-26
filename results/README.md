# Hasil yang dihasilkan kode

Direktori ini berisi artefak yang dibuat oleh pipeline penelitian.

- `tables/`: ringkasan data, modeling, canonical state, dan decision-support scenario.
- `metrics/`: metrik validation/test, prediksi test, dan execution manifest.
- `figures/`: figure diagnostik forecasting, occupancy ablation, dan decision support.

Nilai tidak ditulis manual. Semua artefak Tahap 3 dapat dibuat ulang dengan CLI forecasting dan konfigurasi yang dicatat.

Tahap 4 menambahkan control-versus-treatment occupancy ablation, paired predictions, error per occupancy level, fair-ablation checks, dan moving-block bootstrap. Notebook hanya membaca artefak resmi tersebut atau memanggil pipeline untuk meregenerasinya.

Tahap 5 menambahkan evaluasi empiris Canonical Twin State: schema conformity, source-to-state mapping, completeness yang dipisahkan berdasarkan kategori, temporal integrity, data-quality behavior, preservasi nilai, dan determinisme. Evaluasi ini tidak menjalankan forecasting.

Tahap 6 menambahkan trace recommendation per sample, ringkasan rule, consistency check, manifest, serta tiga figure informatif. Pipeline menggunakan prediksi test Tahap 4 tanpa melatih ulang model. Hasil merupakan evaluasi skenario dan bukan pengukuran energy saving atau outcome intervensi.
