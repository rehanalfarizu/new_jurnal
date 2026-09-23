# Experiment design before implementation

## Primary target

Predict power at `t + 30 minutes` from information available at or before `t`.

The source is irregularly sampled at roughly 3.5-second median intervals. A row shift is not a valid 30-minute target. Target construction must use timestamp matching. The exact match tolerance remains unset in `configs/experiment.yaml` until the gap distribution and operational sampling policy are reviewed.

## Evaluation order

1. Verify raw file hash and schema.
2. Parse timestamp text without modifying the raw column.
3. Generate data-quality and gap reports.
4. Define the canonical timeline and alignment policy.
5. Construct future targets by timestamp.
6. Define chronological train, validation, and test boundaries.
7. Purge at least the forecast horizon around boundaries when required to prevent target overlap.
8. Fit transformations on training data only.
9. Evaluate baselines and comparable occupancy ablations.
10. Generate metrics, predictions, plots, and an execution manifest.
11. Run transparent decision-support scenarios using only verified forecasts and declared assumptions.

## Model comparisons

| Model | Features | Purpose |
| --- | --- | --- |
| Persistence | Current power | Mandatory naive baseline |
| Historical power | Power history and time | Tests predictable temporal structure |
| Environment without occupancy | Power history, time, temperature, humidity | Comparable non-occupancy model |
| Environment with occupancy | Same features plus occupancy | Occupancy ablation treatment |

Use the same target rows, split boundaries, preprocessing, estimator family, and tuning budget for the two environmental models.

## Metrics

Report MAE, RMSE, and R-squared on the held-out temporal test interval. Also retain row-level predictions and evaluate errors across occupancy levels and time periods when group sizes support it. Percentage improvement must name its baseline and denominator.

## Decision-support scope

The study may evaluate whether rules or ranked scenarios are traceable and internally consistent. Without accept/reject and measured-outcome data, label this a decision-support scenario evaluation. Do not claim validated human-in-the-loop performance, autonomous optimization, or observed energy savings.

## Required tests

- raw schema and column mapping;
- timezone localization and sub-second preservation;
- sorting, duplicate, gap, and outlier reporting;
- no silent deletion;
- time-based target matching;
- no feature timestamp later than prediction time;
- split boundaries and horizon purge;
- training-only fitting of learned preprocessing;
- metric calculations on fixed fixtures;
- paired ablation rows and identical configurations;
- canonical-state validity and missing-versus-zero handling;
- deterministic results under the configured seed where the estimator supports it.
