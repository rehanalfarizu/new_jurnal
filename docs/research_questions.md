# Research questions

## RQ1

How can environmental, electrical, and occupancy telemetry be integrated into a consistent canonical Digital Twin state for a smart-room environment?

Evidence: data dictionary, provenance mapping, canonical-state schema, validation report, temporal-alignment audit, and state completeness metrics.

## RQ2

How accurately can the proposed framework forecast smart-room power consumption 30 minutes ahead?

Evidence: timestamp-matched future target, temporal partitions, persistence and historical-power baselines, held-out MAE, RMSE, R-squared, residual analysis, and reproducibility manifest.

## RQ3

Does occupancy information provide incremental predictive value for 30-minute-ahead smart-room power forecasting, where the target is `power(t+30 min)` in W?

Evidence: paired environment-without-occupancy and environment-with-occupancy models under identical data, preprocessing, temporal splits, model family, and tuning budget.

## RQ4

How can current Twin State, occupancy information, and forecast outputs be translated into transparent decision-support recommendations?

Evidence: explicit scenario inputs, rule or score trace, recommendation outputs, consistency tests, and limitations. Measured savings or human outcomes require additional data.
