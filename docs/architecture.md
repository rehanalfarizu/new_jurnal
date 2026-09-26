# Batas arsitektur penelitian

Aplikasi existing tetap menjadi sistem operasional. Repository ini dimulai dari telemetry historis yang telah diekspor dan hanya mengimplementasikan jalur penelitian yang reproducible.

```text
Physical Room
  -> sensing lingkungan dan listrik ESP32
  -> occupancy YOLO dan snapshot gateway Raspberry Pi
  -> ingestion Azure dan Table Storage
  -> ekspor CSV eksternal
  -> intake raw data yang tidak diubah
  -> validasi dan penyelarasan temporal
  -> Canonical Twin State
  -> konstruksi feature dan future target
  -> eksperimen temporal forecasting
  -> occupancy ablation dan evaluasi
  -> Decision-Support Scenario Evaluation
  -> bukti yang dihasilkan untuk paper
```

Empat tahap pertama merupakan bagian sistem existing. Tahap selanjutnya merupakan ruang lingkup repository penelitian ini. Repository ini tidak memuat dashboard kedua, salinan firmware, layanan kamera, cloud deployment, atau 3D viewer.

Jalur dari Azure Table Storage ke CSV yang tersedia belum dapat direproduksi karena command/query ekspor dan snapshot table tidak tersedia. Hubungan tersebut diperlakukan sebagai provenance gap yang terdokumentasi.

Decision support Tahap 6 berhenti pada recommendation trace. Modul tersebut tidak mengirim command ke perangkat dan tidak melakukan autonomous control. Inputnya adalah state saat ini serta prediksi occupancy-aware 30 menit dari output penelitian, bukan jalur operasional baru.
