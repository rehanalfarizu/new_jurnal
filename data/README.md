# Sumber dan penanganan data

## Dataset sumber

Dataset merupakan ekspor CSV historis dari sistem Azure dan disediakan di luar repository. Pipeline Tahap 2 menghitung ulang profil berikut langsung dari file sumber; angka ini bukan nilai hard-coded:

| Properti | Hasil terhitung |
| --- | --- |
| Nama file | `sensor_data.csv` |
| Ukuran | 162.251.693 byte |
| SHA-256 | `ca7831a188a191edbf82a673fac90dbb875b5095986ed07699c02530f2a02a0e` |
| Record | 2.027.520 |
| Kolom | 8 |
| Device unik | 1 (`RASPBERRY_PI_GATEWAY_001`) |
| Waktu awal | `2026-02-23T23:14:43.896301Z` |
| Waktu akhir | `2026-05-24T01:22:06.727676Z` |

Nilai lengkap, termasuk statistik deskriptif, distribusi, duplikasi, interval sampling, dan gap, berada di [`results/tables`](../results/tables/README.md). Seluruh angka dapat dibuat ulang dengan perintah pada [README utama](../README.md).

## Penanganan timestamp

String timestamp memiliki presisi mikrodetik tetapi tidak memiliki suffix zona waktu. Provenance implementasi sistem menyatakan bahwa waktu tersebut berasal dari UTC. Pipeline menerapkan aturan berikut:

1. mempertahankan teks timestamp asli;
2. mem-parse nilai tanggal dan waktu;
3. melokalisasikan nilai naive sebagai UTC tanpa menggeser clock value;
4. menyimpan hasil canonical dengan suffix `Z`;
5. mencatat kegagalan parse bila ada; dan
6. tidak mengonversi nilai secara diam-diam ke zona `Asia/Jakarta`.

## Kebijakan data mentah

Data mentah tidak ditulis ulang. Untuk penggunaan lokal, file dapat ditempatkan pada `data/raw/sensor_data.csv`; direktori `data/raw/`, `data/interim/`, dan `data/processed/` diabaikan oleh Git. Data gambar, kredensial, atau ekspor penuh tidak boleh dicatat ke repository.

Transformasi substantive disimpan terpisah sebagai data processed. Semua langkah melaporkan jumlah record sebelum, sesudah, jumlah terdampak, alasan, dan tindakan.

## Dataset modeling satu menit

Tahap 3 menghasilkan `data/processed/modeling_1min.csv` tanpa menimpa CSV sumber. File processed memuat grid UTC satu menit yang lengkap dari waktu awal sampai akhir, termasuk bin tanpa telemetry sebagai missing.

Selain hasil agregasi, file tersebut memuat target `target_power_30m`, feature backward-looking, label split, indikator eligibility, dan alasan eksklusif apabila sample tidak digunakan. Tidak ada forward-fill atau interpolasi. Karena file dapat dibuat ulang dan berukuran besar, `data/processed/` tetap diabaikan Git.
