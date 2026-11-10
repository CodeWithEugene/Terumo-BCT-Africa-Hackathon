"""Pick the forecast for a date: the trained model if it works, otherwise the baseline.

If the model is missing, switched off by staff, or fails for any reason, the
baseline is used and the result is marked "fallback". The app never stops
because the model did.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.engine import baseline, models
from backend.engine.demand import DemandPanel

PREFERRED = "m1"


@dataclass
class Forecast:
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray
    model: str          # which model made these numbers
    mode: str           # "model" or "fallback"
    note: str           # plain words on why, shown in the app


def make(panel: DemandPanel, as_of, horizon: int, model: str = "auto") -> Forecast:
    """`model` is "auto" (best available), or a model name such as "baseline"."""
    wanted = PREFERRED if model == "auto" else model
    if wanted != baseline.NAME:
        try:
            module = models.get(wanted)                    # raises KeyError if the model is not installed
            from backend.engine.backtest import stored_forecast

            out = stored_forecast(panel, wanted, as_of, horizon) or module.forecast(panel, as_of, horizon)
            return Forecast(out["p10"], out["p50"], out["p90"], wanted, "model", "Using the forecast model.")
        except Exception as error:  # noqa: BLE001  (any failure must fall back, not crash)
            reason = ("The forecast model is not available"
                      if isinstance(error, KeyError) else "The forecast model could not run")
            out = baseline.forecast(panel, as_of, horizon)
            return Forecast(out["p10"], out["p50"], out["p90"], baseline.NAME, "fallback",
                            f"{reason}. Using the 4-week average.")
    out = baseline.forecast(panel, as_of, horizon)
    return Forecast(out["p10"], out["p50"], out["p90"], baseline.NAME, "fallback",
                    "Fallback: using the 4-week average.")
