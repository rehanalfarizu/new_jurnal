# Empirical Evaluation of a Canonical-State Digital Twin Framework

Repository ini memuat penelitian, eksperimen, evaluasi, dan artefak reproduksibilitas untuk penelitian **“Empirical Evaluation of a Canonical-State Digital Twin Framework for Occupancy-Aware Smart-Room Energy Forecasting and Decision Support.”** Repository ini tidak menyalin atau membangun ulang aplikasi Digital Twin pada `dashboard_digitaltwin`.

## Status

Tahap 2–6 telah diimplementasikan. Tahap 5 mengevaluasi Canonical Twin State tanpa mengulang forecasting atau occupancy ablation. Tahap 6 menambahkan **Decision-Support Scenario Evaluation** yang memakai output forecast occupancy-aware Tahap 4 serta state saat ini, dengan rule dan threshold yang dapat diaudit.

Notebook [`notebooks/04_occupancy_ablation.ipynb`](notebooks/04_occupancy_ablation.ipynb) menyediakan antarmuka Jupyter/Google Colab. Notebook tidak menduplikasi logika eksperimen; seluruh perhitungan resmi tetap berada di `src/` dan hasil machine-readable tetap ditulis ke `results/`.

Notebook [`notebooks/05_digital_twin_evaluation.ipynb`](notebooks/05_digital_twin_evaluation.ipynb) menyediakan antarmuka Tahap 5 dengan prinsip source of truth yang sama.

Notebook [`notebooks/06_decision_support_analysis.ipynb`](notebooks/06_decision_support_analysis.ipynb) menyediakan antarmuka Tahap 6. Rule engine tetap berada di `src/decision_support/`; notebook tidak melatih ulang model forecasting.

Rangkaian reproducibility notebook kini lengkap: [`01_dataset_exploration.ipynb`](notebooks/01_dataset_exploration.ipynb) membaca evidence eksplorasi resmi, [`02_canonical_twin_state.ipynb`](notebooks/02_canonical_twin_state.ipynb) mendemonstrasikan transformasi satu raw record, dan [`03_baseline_forecasting.ipynb`](notebooks/03_baseline_forecasting.ipynb) menyajikan protokol serta hasil baseline Tahap 3 tanpa retraining. Source of truth seluruh komputasi tetap berada di `src/`.

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

## Menjalankan Decision-Support Scenario Evaluation Tahap 6

Tahap 6 memerlukan output forecast resmi dan `data/processed/modeling_1min.csv` dari Tahap 4:

```bash
python3 -m src.decision_support.cli
```

Lokasi alternatif dapat diberikan melalui argumen `--predictions` dan `--modeling-state`. Threshold berada di `configs/decision_support.yaml` dan dilabeli sebagai threshold skenario penelitian.

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
- Recommendation Tahap 6 belum diuji terhadap accept/reject manusia atau measured post-recommendation outcome dan tidak membuktikan energy saving, causal impact, validated comfort optimization, maupun autonomous control.

Desain rinci tersedia pada [desain eksperimen](docs/experiment_design.md). Hasil machine-readable tersedia pada [tabel](results/tables/README.md) dan [metrik](results/metrics/README.md).
