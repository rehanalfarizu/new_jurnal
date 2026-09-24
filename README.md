# Empirical Evaluation of a Canonical-State Digital Twin Framework

Repository ini memuat penelitian, eksperimen, evaluasi, dan artefak reproduksibilitas untuk penelitian **“Empirical Evaluation of a Canonical-State Digital Twin Framework for Occupancy-Aware Smart-Room Energy Forecasting and Decision Support.”** Repository ini tidak menyalin atau membangun ulang aplikasi Digital Twin pada `dashboard_digitaltwin`.

## Status

Tahap 2–4 telah diimplementasikan. Tahap 5 menambahkan evaluasi empiris Canonical Twin State tanpa mengulang forecasting atau occupancy ablation. Evaluasi memakai transformer existing untuk mengukur schema conformity, completeness, source-to-state mapping, temporal integrity, quality flags, preservasi nilai, dan determinisme.

Notebook [`notebooks/04_occupancy_ablation.ipynb`](notebooks/04_occupancy_ablation.ipynb) menyediakan antarmuka Jupyter/Google Colab. Notebook tidak menduplikasi logika eksperimen; seluruh perhitungan resmi tetap berada di `src/` dan hasil machine-readable tetap ditulis ke `results/`.

Notebook [`notebooks/05_digital_twin_evaluation.ipynb`](notebooks/05_digital_twin_evaluation.ipynb) menyediakan antarmuka Tahap 5 dengan prinsip source of truth yang sama.

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

## Menjalankan occupancy ablation Tahap 4

```bash
python3 -m src.forecasting.occupancy_cli \
  --input /path/to/sensor_data.csv \
  --config configs/experiment.yaml \
  --features-config configs/features.yaml
```

## Menjalankan evaluasi Canonical Twin State Tahap 5

```bash
python3 -m src.twin_state.cli \
  --input /path/to/sensor_data.csv \
  --config configs/experiment.yaml
```

Notebook dapat dijalankan secara lokal atau melalui Google Colab. Atur lokasi dataset melalui environment variable agar tidak bergantung pada path komputer tertentu:

```bash
export SENSOR_DATA_PATH=/path/to/sensor_data.csv
jupyter lab notebooks/04_occupancy_ablation.ipynb
```

File `data/processed/modeling_1min.csv` menyimpan seluruh grid satu menit, termasuk bin kosong, feature, target, split, dan alasan pengecualian sample. File ini diabaikan Git karena berukuran besar dan dapat dibuat ulang dari dataset sumber.

## Pengujian

```bash
python3 -m unittest discover -s tests -v
```

Pengujian meliputi UTC, valid/invalid canonical state, schema conformity, determinisme, preservasi nilai, unresolved metadata, staleness unavailable, pipeline evaluasi Tahap 5, resampling, bin kosong, target tepat 30 menit, feature backward-looking, chronological split, boundary purge, forecast horizon yang melintasi gap, dan scaler yang hanya fit pada train.

## Batas interpretasi

- Target dan prediksi adalah power dalam Watt, bukan energy dalam Wh.
- Metrik test merupakan hasil baseline pada satu dataset dan satu periode observasi; belum membuktikan generalisasi lintas ruang atau musim.
- Metrik tidak membuktikan energy saving, synchronization latency, atau efek kausal occupancy.
- Occupancy hanya digunakan pada treatment Tahap 4 dan tidak mengubah control Tahap 3.

Desain rinci tersedia pada [desain eksperimen](docs/experiment_design.md). Hasil machine-readable tersedia pada [tabel](results/tables/README.md) dan [metrik](results/metrics/README.md).
