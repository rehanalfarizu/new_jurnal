"""Metrik regresi untuk 30-minute-ahead power forecasting."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(actual: Any, predicted: Any) -> dict[str, float]:
    """Hitung MAE, RMSE, dan R² dalam satu fungsi teruji."""

    y_true = np.asarray(actual, dtype=float)
    y_pred = np.asarray(predicted, dtype=float)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }
