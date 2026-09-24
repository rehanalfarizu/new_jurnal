# Source code penelitian

Kode dipisahkan berdasarkan tanggung jawab ilmiah. Fungsi utama dapat diuji tanpa notebook dan tanpa menjalankan dashboard existing.

- `preprocessing`: intake data mentah, validasi, timestamp, gap, duplikasi, dan audit log;
- `twin_state`: raw-to-canonical mapping, validator schema, quality flags, serialization, dan evaluasi empiris Tahap 5;
- `features`: feature temporal, lag, rolling, lingkungan, dan occupancy yang mencegah leakage;
- `forecasting`: persistence dan baseline statistik atau machine learning yang sebanding;
- `evaluation`: temporal split, metrik, residual, ablation comparison, dan output writer;
- `decision_support`: rule skenario dan trace yang transparan.

Notebook hanya menjadi antarmuka reproducible. Source of truth komputasi tetap berada di direktori ini.
