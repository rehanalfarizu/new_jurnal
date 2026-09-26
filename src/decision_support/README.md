# Decision support Tahap 6

Modul ini mengimplementasikan **Decision-Support Scenario Evaluation** yang transparan dan deterministik. Input berasal dari state satu menit dan output forecast occupancy-aware Tahap 4 pada split test. Model forecasting tidak dilatih ulang oleh pipeline ini.

Rule dan threshold berada di `configs/decision_support.yaml`. Threshold numerik berstatus `declared_research_scenario_threshold`; threshold tersebut bukan batas keselamatan dan bukan standar kenyamanan tervalidasi.

Jalankan dari root repository:

```bash
python3 -m src.decision_support.cli
```

Setiap recommendation menyimpan source timestamp, input state, occupancy, current power, forecast 30 menit, `forecast_delta_w`, rule ID, konfigurasi threshold, teks recommendation, reason, severity, serta hasil pemeriksaan konflik. `room_id` tetap `unresolved`; `device_id` hanya diambil dari ringkasan satu perangkat Tahap 2.

Pipeline menulis tabel skenario, ringkasan rule, consistency check, manifest, dan tiga figure diagnostik. Hasil hanya menunjukkan perilaku rule pada skenario historis; outcome tindakan manusia, accept/reject, energy saving, causal impact, dan autonomous control tidak dievaluasi.
