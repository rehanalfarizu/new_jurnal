# Proposed canonical twin state

This schema is a room-specific research representation for the inspected smart-room system. It is not presented as a universal ontology or a Digital Twin standard.

```yaml
schema_version: 1.0.0-research
timestamp_utc: 2026-02-23T23:14:43.896301Z
room_id: room-01
device_id: RASPBERRY_PI_GATEWAY_001
environment:
  temperature_c: 27.5
  humidity_percent: 65.0
electrical:
  voltage_v: 220.0
  current_a: 2.2
  power_w: 484.0
occupancy:
  count: 5
data_quality:
  valid: true
  staleness_seconds: null
  flags: []
provenance:
  source_file_sha256: ca7831a188a191edbf82a673fac90dbb875b5095986ed07699c02530f2a02a0e
  source_row_number: 2
```

The example mirrors a supplied record and demonstrates shape only. It is not a claim that `room-01`, staleness, or the validation result existed in the source system.

## Field policy

| Field | Type | Rule | Missing behavior | Provenance |
| --- | --- | --- | --- | --- |
| `schema_version` | string | Exact supported version | Reject unknown versions | Research code |
| `timestamp_utc` | timezone-aware timestamp | Parseable UTC with nanosecond-capable storage | Invalid state; preserve raw row in audit | CSV timestamp plus documented UTC assertion |
| `room_id` | string | Non-empty configured identifier | Unavailable until room mapping is supplied | Not present in CSV |
| `device_id` | string | Non-empty | Invalid state | `DeviceID` |
| `environment.temperature_c` | float | Finite; range configured from sensor specification and protocol | Null plus quality flag; no silent imputation | `Suhu (C)` |
| `environment.humidity_percent` | float | Finite in 0 to 100 | Null plus quality flag | `Kelembaban (%)` |
| `electrical.voltage_v` | float | Finite and non-negative; upper range documented | Null plus quality flag | `Tegangan (V)` |
| `electrical.current_a` | float | Finite and non-negative; upper range documented | Null plus quality flag | `Arus (A)` |
| `electrical.power_w` | float | Finite and non-negative; consistency check reported separately | Null plus quality flag | `Daya (W)` |
| `occupancy.count` | integer | Non-negative integer | Null is distinct from measured zero | `Jumlah Orang` |
| `data_quality.valid` | boolean | Derived from declared validation rules | Always present | Research code |
| `data_quality.staleness_seconds` | float or null | Difference between canonical time and source measurement time | Null when source time is unavailable | Not derivable from current CSV |
| `data_quality.flags` | list of strings | Stable machine-readable codes | Empty only when checks pass | Research code |

## Temporal semantics

The supplied row timestamp is the only common time field. Until independent source timestamps are available, the canonical record can represent the exported gateway snapshot time but cannot establish simultaneous physical measurements. Every downstream analysis must preserve that limitation.
