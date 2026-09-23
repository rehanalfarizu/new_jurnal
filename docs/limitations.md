# Known limitations before experiments

- The CSV timestamp text has no timezone suffix. UTC origin is asserted in the supplied brief rather than encoded in the file.
- One timestamp per row is insufficient for physical-to-digital latency measurement.
- Original ESP32 and camera timestamps are not separate in the combined export, so occupancy alignment and staleness cannot be reconstructed.
- All records use one gateway device ID; `room_id` is absent.
- The exact Azure export script, query, table snapshot, and pre-export filtering are unavailable.
- The electrical path in the inspected firmware uses legacy ZMPT101B/SCT013 sensing and calculated apparent power. The relationship to any later PZEM design is not established by the CSV.
- Occupancy detector accuracy has no labeled benchmark in the supplied evidence.
- The data covers one system and one observed period. Generalization to other rooms, buildings, sensors, or seasons requires new data.
- Existing ML metrics use incompatible targets or random row splits and will not be reused as paper results.
- Comfort and recommendation rules are heuristic and not calibrated PMV/PPD or measured occupant preference.
- No recommendation acceptance, action, comfort outcome, or counterfactual energy data is available.
- The JournalISI file is a template with placeholder content. It contains inconsistent issue headers and example references; it is only a structural reference.
