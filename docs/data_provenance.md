# Data provenance

## Verified source relationships

| Data | Implementation evidence | Storage behavior |
| --- | --- | --- |
| Temperature and humidity | ESP32 `suhu` and `kelembaban` payload fields | Sensor or aggregated gateway entity |
| Voltage current and power | ESP32 `tegangan`, `arus`, and calculated `daya` fields | Sensor or aggregated gateway entity |
| Occupancy | Raspberry Pi YOLO `jumlahOrang` or `people_count` | Separate `PeopleCount` entity or latest-value gateway snapshot |
| Device identity | ESP32/camera ID or `RASPBERRY_PI_GATEWAY_001` | Table partition/device field |
| Source time | Device/gateway `timestamp` | Stored alongside Azure `receivedAt` in some paths |

## Occupancy merge behavior

The source contains two different behaviors:

1. Direct camera messages are written to the separate `PeopleCount` table. The application retrieves people count separately from sensor telemetry.
2. The gateway local API maintains latest values in memory. Its pipeline reads the latest ESP32 state and latest camera count, assigns a new gateway timestamp, and writes a combined sensor row. This is a snapshot merge, not a timestamp-nearest join proven from independent source records.

The supplied CSV has one gateway device ID and combined sensor/occupancy columns, which is consistent with the second path. However, the CSV does not contain the original ESP32 measurement time, original camera detection time, gateway merge time, and Azure receipt time as separate columns. Occupancy age and synchronization error therefore cannot be reconstructed.

## Required provenance manifest

Before publication, add a machine-readable manifest containing:

- source repository commit;
- Azure account/resource aliases without credentials;
- table/container name;
- export query or script version;
- export UTC time;
- row count and SHA-256;
- selected columns and renames;
- timestamp timezone assertion and its owner/evidence;
- known filtering, retention, and deduplication performed before export.

## Unsupported statements

Do not claim end-to-end latency, synchronized sensing, causal occupancy effects, or complete physical-to-digital fidelity from the current CSV alone.
