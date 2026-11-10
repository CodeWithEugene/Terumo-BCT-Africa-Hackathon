"""Baseline B0: "what a manager does in their head".

The forecast for a day is the average of the same weekday over the previous
four weeks. The range (p10 to p90) comes from how wrong that rule was over the
eight weeks before the forecast date.
"""
from __future__ import annotations

import numpy as np

from backend import config
from backend.engine.demand import DemandPanel

NAME = "baseline"
LABEL = "The usual way (4-week average)"


def same_weekday_mean(y: np.ndarray, target: int, cutoff: int, weeks: int) -> np.ndarray:
    """Mean of the `weeks` most recent same-weekday rows strictly before `cutoff`."""
    first_back = (target - cutoff) // 7 + 1
    rows = [target - 7 * (first_back + k) for k in range(weeks)]
    rows = [r for r in rows if r >= 0]
    if not rows:
        return np.zeros(y.shape[1])
    return y[rows].mean(axis=0)


def error_quantiles(y: np.ndarray, cutoff: int, weeks: int, lookback_days: int = 56) -> tuple[np.ndarray, np.ndarray]:
    """10th and 90th percentile of (actual - forecast) for the rule, per series, before `cutoff`."""
    errors = []
    for day in range(max(cutoff - lookback_days, 7 * weeks), cutoff):
        errors.append(y[day] - same_weekday_mean(y, day, day, weeks))
    if not errors:
        zero = np.zeros(y.shape[1])
        return zero, zero
    stacked = np.vstack(errors)
    return np.quantile(stacked, 0.10, axis=0), np.quantile(stacked, 0.90, axis=0)


def forecast(panel: DemandPanel, origin, horizon: int | None = None) -> dict[str, np.ndarray]:
    """Forecast `horizon` days starting on `origin`, using only days before it.

    Returns arrays of shape (horizon, series): p10, p50, p90.
    """
    settings = config.load_settings("thresholds")["forecast"]
    horizon = horizon or settings["horizon_days"]
    weeks = settings["baseline_weeks"]
    cutoff = panel.position(origin)
    y = panel.requested
    p50 = np.vstack([same_weekday_mean(y, cutoff + h, cutoff, weeks) for h in range(horizon)])
    low, high = error_quantiles(y, cutoff, weeks)
    return {
        "p10": np.clip(p50 + low, 0, None),
        "p50": p50,
        "p90": p50 + np.clip(high, 0, None),
    }
