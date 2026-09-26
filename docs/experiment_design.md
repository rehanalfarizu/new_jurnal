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

Tahap 3 sendiri tidak mengevaluasi occupancy ablation. Tahap 3 maupun Tahap 4 tidak mengevaluasi synchronization latency, energy saving, decision-support outcome, atau novelty. Hasil juga belum menunjukkan generalisasi lintas ruang, perangkat, musim, maupun kondisi operasional lain.

## Occupancy ablation Tahap 4

Control memakai 20 feature non-occupancy dari Tahap 3. Treatment memakai model family Ridge yang sama dan menambahkan 11 occupancy features: `occupancy_count`, `occupancy_lag_1m`, `occupancy_lag_5m`, `occupancy_lag_15m`, `occupancy_lag_30m`, `occupancy_rolling_mean_5m`, `occupancy_rolling_max_5m`, `occupancy_rolling_mean_15m`, `occupancy_rolling_max_15m`, `occupancy_rolling_mean_30m`, dan `occupancy_rolling_max_30m`. Semua occupancy features bersifat backward-looking.

Control dan treatment memakai common timestamps, target, split, gap policy, scaler policy, candidate `alpha`, dan tuning metric yang sama. `delta_mae = MAE_treatment − MAE_control`; nilai negatif berarti treatment menurunkan error. `mae_improvement = MAE_control − MAE_treatment`; nilai positif berarti treatment menurunkan error. Percentage improvement MAE didefinisikan sebagai `(control − treatment) / control × 100%`.

Ketidakpastian `mae_improvement` dihitung menggunakan moving-block bootstrap pada paired absolute-error difference `absolute_error_control − absolute_error_treatment`. Kolom interval diberi nama `mae_improvement_ci_lower_w` dan `mae_improvement_ci_upper_w`. Block berisi 1.440 sample berurutan, dengan 1.000 iterasi dan seed 42. Independent-row bootstrap tidak digunakan.

Hasil hanya mengukur incremental predictive value. Latest available camera snapshot tidak membuktikan sinkronisasi occupancy secara presisi dan tidak mendukung klaim kausal.

## Decision-Support Scenario Evaluation Tahap 6

Evaluasi Tahap 6 menggunakan seluruh output prediksi treatment occupancy-aware pada split test Tahap 4. Setiap timestamp prediksi digabungkan secara one-to-one dengan `modeling_1min.csv` untuk memperoleh current power, temperature, humidity, dan occupancy pada waktu prediksi. `forecast_delta_w` didefinisikan sebagai:

```text
forecast_delta_w = forecast_power_30m_w - current_power_w
```

Rule disimpan di `configs/decision_support.yaml`:

| Rule | Kondisi | Recommendation |
| --- | --- | --- |
| `DS-RULE-000` | Input wajib missing atau invalid | Review input sebelum evaluasi operasional |
| `DS-RULE-001` | Occupancy = 0 dan current atau forecast power > 40 W | Periksa beban aktif |
| `DS-RULE-002` | Forecast delta > 2 W | Tinjau kemungkinan beban mendatang |
| `DS-RULE-003` | Occupancy > 0 dan temperature > 32 °C atau humidity > 75% | Periksa kondisi ruang |
| `DS-RULE-004` | Tidak ada rule signifikan terpenuhi | Lanjutkan pemantauan normal |

Seluruh threshold numerik di atas adalah `declared_research_scenario_threshold`. Nilai tersebut belum mempunyai basis literatur dalam penelitian ini sehingga tidak diperlakukan sebagai standard comfort atau safety limit. Comparator menggunakan `greater_than`, bukan inklusif.

Setiap recommendation menyimpan input state lengkap, rule ID, threshold/configuration, reason, severity, priority, dan deterministic recommendation ID. Konflik didefinisikan sebagai fallback no-action yang muncul bersama active recommendation pada sample yang sama. Rule tindakan lain boleh muncul bersamaan karena meminta pemeriksaan dan tidak menjalankan aktuasi yang berlawanan.

Coverage adalah jumlah sample dengan minimal satu active recommendation dibagi seluruh sample yang dievaluasi. Analisis distribusi occupancy dan periode hari menggunakan timestamp UTC dengan kategori night 00:00–05:59, morning 06:00–11:59, afternoon 12:00–17:59, dan evening 18:00–23:59.

Evaluasi ini tidak menggunakan accept/reject manusia atau measured post-recommendation outcome. Karena itu, hasil tidak mendukung klaim energy saving, human-in-the-loop effectiveness, causal impact, validated comfort optimization, atau autonomous control.
