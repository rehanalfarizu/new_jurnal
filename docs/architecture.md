# Research architecture boundary

The existing application remains the operational system. This repository begins at exported historical telemetry and implements only the reproducible research path.

```text
Physical room
  -> ESP32 environmental and electrical sensing
  -> Raspberry Pi YOLO occupancy and gateway snapshot
  -> Azure ingestion and Table Storage
  -> external CSV export
  -> immutable raw-data intake
  -> validation and temporal alignment
  -> canonical room state
  -> feature and future-target construction
  -> temporal forecasting experiments
  -> occupancy ablation and evaluation
  -> decision-support scenario evaluation
  -> generated evidence for the paper
```

The first four stages belong to the existing system. The remaining stages belong here. This repository must not contain a second dashboard, firmware copy, camera service, cloud deployment, or 3D viewer.

The path from Azure Table Storage to the supplied CSV is not yet reproducible because the export command/query and table snapshot are absent. Treat that link as a documented provenance gap.
