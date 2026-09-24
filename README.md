# Empirical Evaluation of a Canonical-State Digital Twin Framework

Repository ini memuat penelitian, eksperimen, evaluasi, dan artefak reproduksibilitas untuk penelitian **“Empirical Evaluation of a Canonical-State Digital Twin Framework for Occupancy-Aware Smart-Room Energy Forecasting and Decision Support.”** Repository ini tidak menyalin atau membangun ulang aplikasi Digital Twin pada `dashboard_digitaltwin`.

## Status

Tahap 3 Forecasting Foundation telah diimplementasikan dan dijalankan pada dataset lengkap. Pipeline membentuk time series dengan cadence tetap satu menit, membuat target `power(t+30 minutes)`, membangun feature backward-looking tanpa occupancy, menerapkan chronological split 70/15/15, memilih konfigurasi Ridge menggunakan validation, dan mengevaluasi tiga baseline pada test.

Occupancy tersedia dalam data hasil agregasi, tetapi tidak digunakan sebagai feature model pada Tahap 3. Occupancy ablation tetap menjadi pekerjaan Tahap 4.

## Struktur repository

```text
configs/       Konfigurasi data, feature, split, dan model
data/          Dokumentasi data; raw dan processed lokal tidak dicatat Git
docs/          Provenance, canonical state, desain eksperimen, dan limitation
src/           Preprocessing, feature engineering, forecasting, dan evaluation
tests/         Unit test data, waktu, leakage, split, dan transformasi
results/       Tabel, metrik, prediksi test, dan figure reproducible
paper/         Pemetaan bukti terverifikasi ke naskah
```

## Instalasi

```bash
python3 -m pip install -r requirements.txt
```

## Menjalankan Tahap 2

```bash
python3 -m src.preprocessing.cli \
  --config configs/experiment.yaml \
  explore \
  --input /path/to/sensor_data.csv \
  --output-dir results/tables
```

## Menjalankan Tahap 3

```bash
python3 -m src.forecasting.cli \
  --input /path/to/sensor_data.csv \
  --config configs/experiment.yaml \
  --features-config configs/features.yaml \
  --processed-output data/processed/modeling_1min.csv \
  --tables-dir results/tables \
  --metrics-dir results/metrics \
  --figures-dir results/figures
```

File `data/processed/modeling_1min.csv` menyimpan seluruh grid satu menit, termasuk bin kosong, feature, target, split, dan alasan pengecualian sample. File ini diabaikan Git karena berukuran besar dan dapat dibuat ulang dari dataset sumber.

## Pengujian

```bash
python3 -m unittest discover -s tests -v
```

Pengujian meliputi UTC, canonical state, resampling, bin kosong, target tepat 30 menit, feature backward-looking, chronological split, boundary purge, forecast horizon yang melintasi gap, dan scaler yang hanya fit pada train.

## Batas interpretasi

- Target dan prediksi adalah power dalam Watt, bukan energy dalam Wh.
- Metrik test merupakan hasil baseline pada satu dataset dan satu periode observasi; belum membuktikan generalisasi lintas ruang atau musim.
- Metrik tidak membuktikan energy saving, synchronization latency, atau efek kausal occupancy.
- Occupancy tidak digunakan sebagai feature pada Tahap 3.

Desain rinci tersedia pada [desain eksperimen](docs/experiment_design.md). Hasil machine-readable tersedia pada [tabel](results/tables/README.md) dan [metrik](results/metrics/README.md).
