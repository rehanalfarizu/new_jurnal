# Canonical twin state yang executable

Canonical twin state adalah representasi penelitian yang spesifik untuk smart-room yang dievaluasi. Struktur ini bukan ontologi universal dan bukan klaim standar Digital Twin baru.

Implementasi executable berada di [`src/twin_state/canonical.py`](../src/twin_state/canonical.py). Satu raw record diubah secara deterministik menjadi struktur berikut:

```yaml
schema_version: 1.0.0-research
timestamp_utc: 2026-02-23T23:14:43.896301Z
room_id: unresolved
device_id: RASPBERRY_PI_GATEWAY_001
environment:
  temperature_c: 27.5
  humidity_percent: 65.0
electrical:
  voltage_v: 220.0
  current_a: 2.2
  power_w: 484.0
occupancy:
  count: 0
data_quality:
  valid: true
  staleness_seconds: null
  flags:
    - room_id_unresolved
provenance:
  source_file_sha256: ca7831a188a191edbf82a673fac90dbb875b5095986ed07699c02530f2a02a0e
  source_row_number: 2
  source_timestamp_text: "2026-02-23 23:14:43.896301"
  timestamp_policy: localized_naive_as_utc
```

Contoh tersebut menunjukkan bentuk data. `room_id: unresolved` adalah penanda eksplisit bahwa identitas ruang tidak tersedia pada CSV, bukan nama ruang yang dibuat-buat.

## Aturan field

| Field | Tipe | Aturan |
| --- | --- | --- |
| `schema_version` | string | Versi schema dari konfigurasi |
| `timestamp_utc` | string ISO 8601 | Timestamp aware UTC dengan presisi mikrodetik |
| `room_id` | string | Nilai konfigurasi; `unresolved` sampai pemetaan ruang tersedia |
| `device_id` | string | Harus non-kosong |
| `environment.temperature_c` | float atau null | Numeric finite dan divalidasi terhadap range konfigurasi |
| `environment.humidity_percent` | float atau null | Numeric finite dan divalidasi terhadap range konfigurasi |
| `electrical.voltage_v` | float atau null | Numeric finite dan divalidasi terhadap range konfigurasi |
| `electrical.current_a` | float atau null | Numeric finite dan divalidasi terhadap range konfigurasi |
| `electrical.power_w` | float atau null | Numeric finite dan divalidasi terhadap range konfigurasi |
| `occupancy.count` | integer atau null | Integer non-negatif; missing berbeda dari hasil pengukuran nol |
| `data_quality.valid` | boolean | Hasil validasi timestamp, device, tipe, finite value, integer, dan range |
| `data_quality.staleness_seconds` | float atau null | `null` karena timestamp kamera independen tidak tersedia |
| `data_quality.flags` | daftar string | Kode stabil untuk masalah dan limitation per record |

`room_id_unresolved` tidak menjadikan pengukuran numerik invalid, tetapi tetap dicatat pada setiap state agar keterbatasan spasial tidak hilang. Nilai missing, invalid, non-finite, non-integer, atau di luar range membuat `valid` bernilai `false`; nilai asli tidak dihapus atau diimputasi.

## Semantik waktu dan staleness

Timestamp CSV tanpa suffix dilokalisasikan sebagai UTC sesuai provenance yang telah diverifikasi. Lokalisasi tidak mengubah angka waktu. Teks sumber tetap disimpan pada `provenance.source_timestamp_text`.

CSV hanya menyediakan satu timestamp untuk record gabungan. Karena tidak terdapat timestamp kamera independen, `staleness_seconds` selalu `null` pada Tahap 2. Nilai tersebut tidak boleh diganti nol, karena nol akan menyatakan sinkronisasi sempurna yang tidak dibuktikan oleh data.

## Validasi dan pengujian

Unit test mencakup lokalisasi UTC tanpa pergeseran, konversi timestamp yang memiliki offset, struktur raw-to-canonical, perbedaan missing dan occupancy nol, staleness null, serta flag outlier. Pipeline penuh juga memvalidasi setiap record menggunakan transformer yang sama.
