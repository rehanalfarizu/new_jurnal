# Empirical Evaluation of a Canonical-State Digital Twin Framework

This repository contains the research, experiments, evaluation, and reproducibility assets for occupancy-aware smart-room energy forecasting and decision support. It does not duplicate or deploy the existing Digital Twin application.

The implementation system remains in [`ikhsanudin017/dashboard_digitaltwin`](https://github.com/ikhsanudin017/dashboard_digitaltwin). This repository treats that system as an evidence source for data provenance, raw-field semantics, and operational context.

## Current status

The repository is at the audit and experiment-design stage. No forecasting accuracy, occupancy benefit, synchronization latency, energy saving, or novelty result is claimed yet.

- The source repositories and supplied artifacts have been inspected.
- The supplied CSV schema and basic integrity have been checked read-only.
- Research boundaries, provenance gaps, and the proposed canonical state are documented.
- Major experiments have not started.

See [the repository audit](docs/repository_audit.md) before implementing or interpreting experiments.

## Repository map

```text
configs/       Declared experiment and feature settings
data/          Data documentation and raw-to-canonical dictionary
docs/          Architecture, provenance, state, design, questions, limitations
src/           Research code organized by scientific responsibility
tests/         Tests for transformations, splits, leakage, and metrics
results/       Generated metrics, tables, and figures only
paper/         Mapping from verified evidence to manuscript sections
```

## Research boundary

The repository will evaluate:

1. integration of environmental, electrical, and occupancy telemetry into a room-specific canonical state;
2. true 30-minute-ahead power forecasting using temporal evaluation;
3. the incremental predictive value of occupancy through controlled ablation; and
4. transparent decision-support scenarios based on current state and forecasts.

Literature novelty, state-of-the-art positioning, and unsupported causal or savings claims are outside the technical evidence produced here.

## Data

The supplied Azure export is kept outside Git. Its inspected location, checksum, schema, and timestamp caveat are recorded in [data/README.md](data/README.md). The timestamp strings contain microseconds but no timezone suffix. The supplied research brief identifies them as UTC; preprocessing must preserve the raw text and attach UTC explicitly with an audit record.

## Next gate

Before model training, implement and test the data loader, validation report, temporal alignment policy, target construction, and split-boundary checks described in [docs/experiment_design.md](docs/experiment_design.md).
