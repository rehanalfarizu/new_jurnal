# Modul canonical twin state

`canonical.py` mengubah satu raw record menjadi canonical twin state dan menyediakan representasi datar untuk CSV processed.

Transformer mempertahankan timestamp sumber, menerapkan UTC berdasarkan provenance sistem, memvalidasi tipe dan range, membedakan missing occupancy dari nilai nol, serta menghasilkan quality flags. `room_id` berasal dari konfigurasi dan saat ini bernilai `unresolved`. `staleness_seconds` bernilai `None` karena CSV tidak mempunyai timestamp kamera independen.

Schema lengkap dan alasan setiap keputusan tersedia pada [`docs/canonical_twin_state.md`](../../docs/canonical_twin_state.md).
