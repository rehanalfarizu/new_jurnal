# Research code

Code is separated by scientific responsibility. Each module must expose deterministic functions that can be tested without notebooks or the existing dashboard.

- `preprocessing`: raw intake, validation, timestamp handling, gaps, duplicates, and audit logs.
- `twin_state`: raw-to-canonical mapping, quality flags, and state serialization.
- `features`: leakage-safe temporal, lag, rolling, environmental, and occupancy features.
- `forecasting`: persistence and comparable statistical or machine-learning baselines.
- `evaluation`: temporal splits, metrics, residuals, ablation comparisons, and output writers.
- `decision_support`: transparent scenario rules and trace generation.

No source module is implemented at the audit checkpoint.
