# Modul evaluation

`temporal.py` membuat chronological split 70/15/15 dan mengklasifikasikan eligibility setiap minute-bin. Sample dikeluarkan apabila feature window tidak lengkap, target missing, horizon 30 menit melintasi gap, atau target melewati split boundary.

`metrics.py` menghitung MAE, RMSE, dan R². MAE dan RMSE dilaporkan dalam Watt karena target adalah power, bukan energy.

Test set tidak digunakan untuk memilih feature, model, atau `alpha`. Semua baseline dinilai pada timestamp test yang sama.
