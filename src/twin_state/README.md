# Modul canonical twin state

`canonical.py` mengubah satu raw record menjadi canonical twin state dan menyediakan representasi datar untuk CSV processed.

Transformer mempertahankan timestamp sumber, menerapkan UTC berdasarkan provenance sistem, memvalidasi tipe dan range, membedakan missing occupancy dari nilai nol, serta menghasilkan quality flags. `room_id` berasal dari konfigurasi dan saat ini bernilai `unresolved`. `staleness_seconds` bernilai `None` karena CSV tidak mempunyai timestamp kamera independen.

Schema lengkap dan alasan setiap keputusan tersedia pada [`docs/canonical_twin_state.md`](../../docs/canonical_twin_state.md).

`evaluation.py` menjalankan evaluasi empiris Tahap 5 terhadap seluruh raw record dengan memakai `CanonicalStateTransformer` yang sama. Evaluasi mencakup schema conformity, completeness, validitas tipe dan timestamp, integritas temporal, preservasi nilai source-to-state, quality flags, dan determinisme. Modul ini tidak membuat representasi canonical kedua.

Jalankan pipeline Tahap 5 dengan:

```bash
python3 -m src.twin_state.cli \
  --input /path/to/sensor_data.csv \
  --config configs/experiment.yaml
```

Keluaran resmi ditulis ke `results/tables/` dan manifest reproduksibilitas ditulis ke `results/metrics/canonical_state_evaluation_manifest.json`.
