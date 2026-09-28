# Figure manuskrip

Direktori ini memuat salinan figure berorientasi publikasi yang dibuat setelah `experiment-v1.0`. Figure hanya menggunakan prediksi, tabel, dan manifest resmi yang telah dibekukan; tidak ada model yang dilatih ulang dan tidak ada file historis pada `results/figures/` yang ditimpa.

Figure menggunakan palet penuh warna yang konsisten, label berbahasa Inggris, background putih, dan resolusi PNG 300 dpi. Seluruh figure publikasi dapat dibuat ulang tanpa dataset mentah menggunakan:

```bash
python3 scripts/generate_publication_figures.py
```

Generator tersebut membaca langsung artefak CSV resmi, memvalidasi kelengkapan metrik, serta memastikan total sample konsisten dengan seluruh 18.126 prediksi held-out test. Generator hanya menghasilkan PNG agar direktori figure tidak dipenuhi format duplikat.

## Figure 2 — Forecasting performance

Berkas: `forecasting_performance.png`.

**Figure 2.** Held-out test performance for 30-minute-ahead power forecasting, comparing the persistence baseline, historical-power Ridge, and non-occupancy multivariate Ridge over the common test evaluation. MAE and RMSE are reported in watts, whereas R² is dimensionless; the three metrics are therefore shown on separate axes. Numeric labels reproduce the official Stage-3 metrics without model rerunning.

## Figure 3 — Occupancy ablation

Berkas: `occupancy_ablation_comparison.png`.

**Figure 3.** Fair occupancy ablation on the common held-out test set. Panel (a) compares the non-occupancy multivariate Ridge control with the occupancy-aware Ridge treatment using separate axes for MAE, RMSE, and R². Panel (b) shows the paired MAE-improvement point estimate (control minus occupancy-aware) and its 95% moving-block-bootstrap confidence interval; the dashed vertical reference marks zero improvement. The interval crosses zero.

## Figure 4 — MAE by occupancy level

Berkas: `occupancy_level_error.png`.

**Figure 4.** Descriptive held-out test MAE by occupancy count at the forecast origin for the control and occupancy-aware models. Each thin connector denotes a paired comparison within one discrete occupancy stratum; points are not connected across strata. Sample sizes are shown below each occupancy category and sum to 18,126. This subgroup comparison does not imply a continuous trend or a causal effect of occupancy on forecast error.

## Figure 5 — Decision-support outcomes

Berkas: `decision_support_rule_frequency.png`.

**Figure 5.** Decision-support outcomes over the complete 18,126-sample held-out test evaluation. Panel (a) contrasts samples with an active recommendation against normal monitoring. Panel (b) decomposes active recommendations into DS-RULE-001, DS-RULE-002, and DS-RULE-003; DS-RULE-000 is retained as an annotation for rule-set completeness. Labels report absolute counts and percentages of all evaluated samples. Frequencies describe deterministic scenario-rule activation, not energy savings or human decision effectiveness.

## Figure tambahan

- `forecast_actual_vs_predicted_full_test.png`
- `occupancy_aware_actual_vs_predicted_full_test.png`
- `forecast_error_distribution_full_test.png`
- `decision_support_occupancy_distribution.png`
- `decision_support_forecast_delta.png`
- `download.png` (flowchart metodologi yang digunakan dalam naskah)

`download.png` dipertahankan tanpa perubahan dan tidak dikelola oleh generator figure.
