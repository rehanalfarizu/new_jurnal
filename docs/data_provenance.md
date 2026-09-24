# Provenance data

## Rantai provenance yang digunakan

```text
Physical Room
  → Sensor / Camera
  → ESP32 / Raspberry Pi
  → Gateway
  → Azure / Cloud
  → Historical Storage
  → CSV Export
  → UTC Normalization
  → Validation
  → Canonical Twin State
```

| Tahap | Data atau proses | Status bukti |
| --- | --- | --- |
| Physical Room | Ruang fisik yang diamati | Identitas `room_id` tidak terdapat pada CSV |
| Sensor / Camera | Sensor lingkungan dan listrik serta kamera occupancy | Jenis sumber diverifikasi dari implementasi |
| ESP32 / Raspberry Pi | ESP32 menghasilkan telemetry sensor; Raspberry Pi menjalankan deteksi occupancy | Diverifikasi dari implementasi sistem |
| Gateway | Gateway menggabungkan state sensor terbaru dan snapshot kamera terbaru | Diverifikasi dari perilaku kode |
| Azure / Cloud | Pesan dikirim ke layanan cloud/Azure | Diverifikasi dari implementasi |
| Historical Storage | Record gabungan disimpan sebagai histori | Struktur field sesuai ekspor CSV |
| CSV Export | Delapan kolom diekspor ke `sensor_data.csv` | Diverifikasi langsung dari file |
| UTC Normalization | Timestamp naive diinterpretasikan sebagai UTC tanpa perubahan clock value | Dijalankan oleh pipeline Tahap 2 berdasarkan provenance sistem |
| Validation | Schema, tipe, missing, duplikasi, gap, range, dan outlier diperiksa | Dijalankan dan diuji di repository ini |
| Canonical Twin State | Raw record dipetakan ke struktur canonical versi penelitian | Diimplementasikan di `src/twin_state/canonical.py` |

## Hubungan field sumber

| Data | Sumber implementasi | Perilaku penyimpanan |
| --- | --- | --- |
| Temperature dan humidity | Field `suhu` dan `kelembaban` dari ESP32 | Disimpan pada record sensor/gateway |
| Voltage, current, dan power | Field `tegangan`, `arus`, dan `daya` dari ESP32 | Disimpan pada record sensor/gateway |
| Occupancy | `jumlahOrang` atau `people_count` dari layanan YOLO Raspberry Pi | Dapat disimpan terpisah atau sebagai snapshot terbaru pada gateway |
| Device identity | ID perangkat/gateway | CSV berisi satu ID gateway |
| Waktu | Timestamp perangkat/gateway | CSV hanya mempertahankan satu timestamp gabungan |

## Perilaku penggabungan occupancy

Implementasi sumber mempunyai dua jalur:

1. Pesan kamera langsung dapat disimpan pada entitas `PeopleCount` yang terpisah.
2. API lokal gateway mempertahankan nilai terbaru dari ESP32 dan kamera di memori. Pipeline gateway mengambil kedua nilai terbaru tersebut, memberikan timestamp gateway, lalu menulis record sensor gabungan.

Struktur CSV—satu `DeviceID` gateway dan kolom sensor serta occupancy pada record yang sama—konsisten dengan jalur kedua. Namun, CSV tidak menyimpan timestamp pengukuran ESP32, timestamp deteksi kamera, timestamp penggabungan gateway, dan waktu penerimaan Azure sebagai field terpisah.

Dengan demikian, occupancy pada setiap record harus dijelaskan sebagai **latest available camera snapshot**. Data saat ini tidak membuktikan nearest-timestamp synchronization. Occupancy staleness dan synchronization latency tidak dapat dihitung dan tidak boleh diklaim.

## Informasi provenance yang masih diperlukan untuk publikasi

- commit sumber implementasi yang digunakan saat ekspor;
- alias resource Azure tanpa kredensial;
- nama table/container histori;
- query atau versi skrip ekspor;
- waktu ekspor dalam UTC;
- identitas fisik ruang untuk `room_id`;
- timestamp independen sensor, kamera, gateway, dan cloud;
- kebijakan filtering, retention, dan deduplication sebelum ekspor.

Repository ini tidak mengklaim latency end-to-end, sinkronisasi sensor secara simultan, efek kausal occupancy, atau fidelity fisik-ke-digital yang lengkap dari CSV saat ini.
