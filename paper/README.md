# Peta claim–evidence paper

Dokumen JournalISI adalah template format, bukan sumber evidence. Prosa manuscript hanya boleh menggunakan output terverifikasi dari repository. Ringkasan angka terpusat tersedia pada `EXPERIMENT_SUMMARY.md`.

## RQ1 — Canonical-state evidence

**Pertanyaan:** Bagaimana telemetry lingkungan, listrik, dan occupancy dapat diintegrasikan menjadi Canonical Twin State yang konsisten?

Evidence:

- `docs/canonical_twin_state.md`
- `docs/data_provenance.md`
- `data/data_dictionary.csv`
- `configs/experiment.yaml`
- `results/tables/canonical_field_mapping.csv`
- `results/tables/canonical_state_evaluation.csv`
- `results/tables/digital_twin_data_quality.csv`
- `results/metrics/canonical_state_evaluation_manifest.json`
- `notebooks/02_canonical_twin_state.ipynb`
- `notebooks/05_digital_twin_evaluation.ipynb`

Batas klaim: schema conformity tidak membuktikan physical-to-digital latency, occupancy staleness, atau exact camera-sensor synchronization.

## RQ2 — Forecasting evidence

**Pertanyaan:** Seberapa akurat framework memprediksi power 30 menit ke depan?

Evidence:

- `configs/experiment.yaml`
- `configs/features.yaml`
- `results/tables/modeling_dataset_summary.csv`
- `results/tables/sample_exclusion_summary.csv`
- `results/tables/temporal_split.csv`
- `results/tables/feature_definition.csv`
- `results/tables/baseline_model_comparison.csv`
- `results/metrics/forecast_metrics.csv`
- `results/metrics/test_predictions.csv`
- `results/metrics/forecast_run_manifest.json`
- `results/figures/forecast_actual_vs_predicted.png`
- `results/figures/forecast_error_distribution.png`
- `notebooks/03_baseline_forecasting.ipynb`

Batas klaim: metrik held-out berlaku untuk dataset dan periode observasi ini; target adalah power dalam Watt, bukan energy saving.

## RQ3 — Occupancy-ablation evidence

**Pertanyaan:** Apakah occupancy memberikan incremental predictive value untuk forecasting power 30 menit ke depan?

Evidence:

- `results/tables/occupancy_ablation_feature_definition.csv`
- `results/tables/fair_ablation_check.csv`
- `results/tables/occupancy_ablation_comparison.csv`
- `results/tables/occupancy_level_error.csv`
- `results/metrics/occupancy_ablation_metrics.csv`
- `results/metrics/occupancy_ablation_bootstrap.csv`
- `results/metrics/occupancy_ablation_test_predictions.csv`
- `results/metrics/occupancy_ablation_manifest.json`
- `results/figures/occupancy_ablation_comparison.png`
- `results/figures/occupancy_level_error.png`
- `notebooks/04_occupancy_ablation.ipynb`

Batas klaim: treatment mempunyai point estimate test yang lebih baik, tetapi bootstrap confidence interval untuk MAE improvement mencakup nol dan tidak mendukung klaim efek kausal.

## RQ4 — Decision-support evidence

**Pertanyaan:** Bagaimana current Twin State, occupancy, dan forecast diterjemahkan menjadi recommendation yang transparan?

Evidence:

- `configs/decision_support.yaml`
- `results/tables/decision_support_scenarios.csv`
- `results/tables/decision_support_rule_summary.csv`
- `results/tables/decision_support_consistency.csv`
- `results/metrics/decision_support_manifest.json`
- `results/figures/decision_support_rule_frequency.png`
- `results/figures/decision_support_occupancy_distribution.png`
- `results/figures/decision_support_forecast_delta.png`
- `notebooks/06_decision_support_analysis.ipynb`

Batas klaim: belum tersedia accept/reject manusia, post-recommendation outcome, causal evaluation, validated comfort threshold, atau autonomous control.

## Pemetaan bagian manuscript

| Bagian manuscript | Evidence repository |
| --- | --- |
| Introduction | Research questions dan literature review yang dikelola terpisah; tidak ada novelty claim dari repository |
| Methods | Architecture, provenance, canonical state, preprocessing, feature configuration, target, temporal split, model, dan metrik |
| Results | Tabel dan manifest resmi yang dipetakan ke RQ1–RQ4 di atas |
| Discussion | Keterbatasan teknis serta perbandingan literatur yang dilakukan terpisah |
| Conclusion | Hanya kesimpulan yang didukung held-out results dan limitation terdokumentasi |

Gunakan `paper/figures/` dan `paper/tables/` hanya untuk salinan terpilih atau link yang berasal dari `results/`. Jangan mengetik ulang angka ilmiah secara manual ke manuscript.
