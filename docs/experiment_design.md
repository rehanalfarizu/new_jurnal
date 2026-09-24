# Desain eksperimen Tahap 3

## Modeling time series

Raw CSV hanya dibaca dan tidak diubah. Record diagregasikan ke grid UTC dengan cadence tepat satu menit:

| Variabel | Agregasi per menit |
| --- | --- |
| Temperature | Mean |
| Humidity | Mean |
| Voltage | Mean |
| Current | Mean |
| Power | Mean |
| Occupancy | Last valid observation dalam minute-bin |

Pipeline melakukan reindex dari minute-bin pertama sampai terakhir. Minute-bin tanpa telemetry tetap ada dengan nilai missing. Tidak ada forward-fill, interpolasi, atau penghapusan outlier.

## Target forecasting

Target utama adalah **30-minute-ahead power forecasting**:

```text
target_power_30m(t) = power_w(t + 30 menit)
```

Target dibuat setelah grid satu menit terbentuk, bukan melalui pergeseran 30 raw row. Unit target tetap Watt. Timestamp target disimpan secara eksplisit dan unit test memverifikasi selisih tepat 30 menit.

Sample dikeluarkan dari modeling apabila target `t+30` missing atau salah satu minute-bin pada horizon `t+1` sampai `t+30` tidak memiliki telemetry. Raw data dan baris grid tetap disimpan; hanya eligibility modeling yang berubah.

## Feature set tanpa occupancy

Baseline historical power menggunakan:

- current power pada t;
- power lag 1, 5, 15, dan 30 menit;
- rolling mean dan sample standard deviation power untuk window 5, 15, dan 30 menit;
- representasi siklik waktu dalam hari dan hari dalam minggu; serta
- indikator weekend.

Model non-occupancy multivariate menambahkan current-minute temperature, humidity, voltage, dan current. Rolling feature mencakup t dan waktu sebelumnya saja. Definisi offset sumber setiap feature tercatat pada `configs/features.yaml` dan `results/tables/feature_definition.csv`.

Occupancy tidak digunakan sebagai feature atau untuk menentukan label pada Tahap 3.

## Gap handling dan common sample

Sebuah sample hanya usable jika:

1. minute-bin t memiliki telemetry lengkap;
2. seluruh lag dan rolling window tersedia;
3. target power tepat pada t+30 tersedia;
4. horizon t+1 sampai t+30 tidak melintasi bin kosong; dan
5. state timestamp serta target timestamp berada pada split yang sama.

Semua baseline dievaluasi pada common usable timestamps yang sama agar perbandingan berpasangan dan tidak dipengaruhi jumlah sample berbeda.

## Chronological split

Seluruh grid waktu dibagi berdasarkan urutan timestamp:

- Train: 70% periode awal.
- Validation: 15% periode berikutnya.
- Test: 15% periode terakhir.

Random split tidak digunakan. Target yang melintasi boundary train–validation atau validation–test dikeluarkan. Scaler di-fit hanya pada train. Candidate `alpha` Ridge dipilih berdasarkan MAE validation. Test tidak digunakan untuk pemilihan konfigurasi.

## Baseline

| Model | Definisi |
| --- | --- |
| Persistence | `prediction(t+30) = power(t)` |
| Historical power Ridge | Historical power dan time features |
| Non-occupancy multivariate Ridge | Historical power, time, temperature, humidity, voltage, dan current |

Candidate `alpha` adalah 0,1; 1; 10; dan 100. Model sederhana digunakan agar pipeline mudah direproduksi dan hasil baseline dapat diaudit. Deep learning tidak digunakan.

## Evaluasi

MAE, RMSE, dan R² dihitung pada validation serta test. Validation digunakan untuk pemilihan `alpha` dan pemilihan model yang ditampilkan pada figure. Seluruh baseline tetap dilaporkan pada test menggunakan konfigurasi yang telah dipilih tanpa melihat test.

Metrik MAE dan RMSE menggunakan unit Watt. R² tidak memiliki unit.

## Batas klaim

Tahap 3 belum mengevaluasi occupancy ablation, synchronization latency, energy saving, decision-support outcome, atau novelty. Hasil juga belum menunjukkan generalisasi lintas ruang, perangkat, musim, maupun kondisi operasional lain.
