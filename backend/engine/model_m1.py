"""Model M1: one pooled gradient-boosting model for every hospital, product and blood group.

It predicts weekly units requested, one and two weeks ahead, then shares each
week out over the days using that series' own weekday pattern.

- Expected demand: scikit-learn HistGradientBoostingRegressor with Poisson loss.
- Range: two more models with quantile loss (10th and 90th percentile).
- Trained fresh for each forecast date on weeks before that date only.
- Rare series (most weeks have no request) are not chased: by default they use
  the baseline, and the staff-set minimum stock protects them.

The column called p50 in the forecast table holds the expected (mean) demand,
because the stock projection needs expected use, not the median (which is zero
for most series).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from backend import config
from backend.db.core import read
from backend.engine import baseline
from backend.engine.demand import DemandPanel

NAME = "m1"
LABEL = "Our forecast (pooled gradient boosting)"

FEATURES = [
    "lag1", "lag2", "lag3", "lag4", "lag5", "lag6", "lag7", "lag8",
    "mean2", "mean4", "mean8", "mean26", "zero8", "zero26", "emergency_share",
    "facility_mean4", "region_group_mean4",
    "facility_type", "keph_level", "beds", "region", "component", "blood_group",
    "week_of_year", "school_in_session", "days_to_next_school_break", "public_holidays", "malaria_season",
    "weeks_ahead",
]

_CACHE: dict[tuple[int, int, int, str], dict[str, np.ndarray]] = {}


@lru_cache(maxsize=1)
def _calendar(stamp: float) -> dict[str, pd.DataFrame]:
    cal = read("SELECT * FROM calendar", parse_dates=["date"])
    return {region: frame.set_index("date").sort_index() for region, frame in cal.groupby("region")}


def _calendar_features(panel: DemandPanel, start: pd.Timestamp) -> np.ndarray:
    """Calendar facts for the 7 days from `start`, one row per series. Shape (series, 5)."""
    calendars = _calendar(config.DB_PATH.stat().st_mtime)
    by_region = {}
    for region, cal in calendars.items():
        week = cal.loc[start:start + pd.Timedelta(days=6)]
        by_region[region] = [
            float(start.isocalendar().week), float(week["school_in_session"].mean()),
            float(min(week["days_to_next_school_break"].iloc[0], 120)), float(week["public_holiday"].sum()),
            float(week["malaria_season"].mean()),
        ]
    return np.array([by_region[r] for r in panel.series["region"]])


def _static(panel: DemandPanel) -> np.ndarray:
    s = panel.series
    codes = lambda column: pd.Categorical(s[column]).codes.astype(float)
    return np.column_stack([codes("facility_type"), s["keph_level"].fillna(0).to_numpy(float),
                            s["beds"].fillna(0).to_numpy(float), codes("region"), codes("component"),
                            codes("blood_group")])


def _history_features(panel: DemandPanel, csum: np.ndarray, csum_em: np.ndarray, csum_rq: np.ndarray, anchor: int) -> np.ndarray:
    """Demand features for every series, using only days before `anchor`. Shape (series, 17)."""
    def week(i: int) -> np.ndarray:           # i = 1 is the week just before the anchor
        return csum[anchor - 7 * (i - 1)] - csum[anchor - 7 * i]

    lags = np.stack([week(i) for i in range(1, 9)], axis=1)
    n26 = min(26, anchor // 7)
    weeks26 = np.stack([week(i) for i in range(1, n26 + 1)], axis=1)
    requests = csum_rq[anchor] - csum_rq[anchor - 56]
    emergencies = csum_em[anchor] - csum_em[anchor - 56]
    share = np.divide(emergencies, requests, out=np.zeros_like(requests), where=requests > 0)
    mean4 = lags[:, :4].mean(axis=1)
    s = panel.series
    facility_mean = pd.Series(mean4).groupby([s["facility_id"].to_numpy(), s["component"].to_numpy()]).transform("sum").to_numpy()
    region_mean = pd.Series(mean4).groupby(
        [s["region"].to_numpy(), s["component"].to_numpy(), s["blood_group"].to_numpy()]).transform("sum").to_numpy()
    return np.column_stack([
        lags, lags[:, :2].mean(axis=1), mean4, lags.mean(axis=1), weeks26.mean(axis=1),
        (lags == 0).mean(axis=1), (weeks26 == 0).mean(axis=1), share, facility_mean, region_mean,
    ])


def _weekday_profile(panel: DemandPanel, cut: int) -> np.ndarray:
    """Each series' share of demand by weekday (rows: weekday of the forecast day). Shape (7, series)."""
    y = panel.requested[max(0, cut - 56):cut]
    weekdays = panel.dates[max(0, cut - 56):cut].dayofweek.to_numpy()
    totals = np.stack([y[weekdays == d].sum(axis=0) for d in range(7)])          # (7, series)
    # Fall back to the pattern of the same product at all hospitals when a series has too little history.
    codes = pd.Categorical(panel.series["component"]).codes
    pooled = np.zeros_like(totals)
    for c in np.unique(codes):
        pooled[:, codes == c] = totals[:, codes == c].sum(axis=1, keepdims=True)
    pooled = np.where(pooled.sum(axis=0) > 0, pooled, 1.0)
    use_own = totals.sum(axis=0) >= 8
    profile = np.where(use_own, totals, pooled)
    return profile / profile.sum(axis=0)


def _fit_predict(panel: DemandPanel, cut: int) -> dict[str, np.ndarray]:
    """Weekly forecasts for weeks 1 and 2 after `cut`. Each array has shape (2, series)."""
    settings = config.load_settings("thresholds")["model"]
    y = panel.requested
    zeros = np.zeros((1, y.shape[1]))
    csum = np.vstack([zeros, np.cumsum(y, axis=0)])
    csum_em = np.vstack([zeros, np.cumsum(panel.emergency, axis=0)])
    csum_rq = np.vstack([zeros, np.cumsum(panel.requests, axis=0)])
    static = _static(panel)

    def rows(anchor: int, weeks_ahead: int) -> np.ndarray:
        start = panel.dates[0] + pd.Timedelta(days=anchor + 7 * (weeks_ahead - 1))
        return np.column_stack([
            _history_features(panel, csum, csum_em, csum_rq, anchor), static,
            _calendar_features(panel, start), np.full(len(panel.series), float(weeks_ahead)),
        ])

    train_x, train_y = [], []
    for weeks_ahead in (1, 2):
        anchor = cut - 7 * weeks_ahead               # the newest anchor whose target week is fully known
        while anchor >= 56:
            target_start = anchor + 7 * (weeks_ahead - 1)
            train_x.append(rows(anchor, weeks_ahead))
            train_y.append(csum[target_start + 7] - csum[target_start])
            anchor -= 7
    x, target = np.vstack(train_x), np.concatenate(train_y)
    future = [rows(cut, 1), rows(cut, 2)]

    common = dict(max_iter=settings["max_iter"], learning_rate=settings["learning_rate"], max_leaf_nodes=15,
                  min_samples_leaf=40, l2_regularization=1.0, random_state=0)
    mean_model = HistGradientBoostingRegressor(loss="poisson", **common).fit(x, target)
    low_model = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, **common).fit(x, target)
    high_model = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, **common).fit(x, target)
    mean = np.stack([np.clip(mean_model.predict(f), 0, None) for f in future])
    low = np.minimum(np.stack([np.clip(low_model.predict(f), 0, None) for f in future]), mean)
    high = np.maximum(np.stack([high_model.predict(f) for f in future]), mean)
    return {"p10": low, "p50": mean, "p90": high}


def forecast(panel: DemandPanel, origin, horizon: int | None = None, rare_method: str | None = None) -> dict[str, np.ndarray]:
    """Daily forecast for `horizon` days from `origin`. Arrays have shape (horizon, series)."""
    settings = config.load_settings("thresholds")
    horizon = horizon or settings["forecast"]["horizon_days"]
    rare_method = rare_method or settings["model"]["rare_method"]
    if horizon > 14:
        raise ValueError("Model M1 forecasts at most 14 days ahead.")
    cut = panel.position(origin)
    key = (id(panel), cut, horizon, rare_method)
    if key in _CACHE:
        return _CACHE[key]

    weekly = _fit_predict(panel, cut)
    profile = _weekday_profile(panel, cut)
    days = pd.date_range(pd.Timestamp(origin), periods=horizon)
    out = {name: np.zeros((horizon, len(panel.series))) for name in ("p10", "p50", "p90")}
    for t, day in enumerate(days):
        share = profile[day.dayofweek]
        week = t // 7
        out["p50"][t] = weekly["p50"][week] * share
        # Daily margins are scaled so that a week of them adds back up to the weekly range.
        out["p10"][t] = out["p50"][t] - (weekly["p50"][week] - weekly["p10"][week]) * np.sqrt(share)
        out["p90"][t] = out["p50"][t] + (weekly["p90"][week] - weekly["p50"][week]) * np.sqrt(share)
    out["p10"] = np.clip(out["p10"], 0, None)

    if rare_method == "baseline":
        simple = baseline.forecast(panel, origin, horizon)
        rare = rare_series(panel, cut)
        for name in out:
            out[name][:, rare] = simple[name][:, rare]
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def rare_series(panel: DemandPanel, cut: int) -> np.ndarray:
    """True for series where most of the last 26 weeks had no request."""
    share = config.load_settings("thresholds")["model"]["rare_zero_week_share"]
    n = min(26, cut // 7)
    weeks = np.stack([panel.requested[cut - 7 * (i + 1):cut - 7 * i].sum(axis=0) for i in range(n)])
    return (weeks == 0).mean(axis=0) >= share


def validate_rare_choice(panel: DemandPanel) -> dict:
    """Compare the two ways of forecasting rare series on dates BEFORE the test window.

    This is how `rare_method` in config/thresholds.yaml was chosen. Nothing here
    touches the test period.
    """
    settings = config.load_settings("thresholds")
    horizon = settings["forecast"]["horizon_days"]
    errors = {"baseline": [], "model": []}
    shares = []
    for date in settings["model"]["validation_origins"]:
        origin = pd.Timestamp(str(date))
        cut = panel.position(origin)
        rare = rare_series(panel, cut)
        shares.append(rare.mean())
        actual = panel.requested[cut:cut + horizon][:, rare]
        errors["baseline"].append(np.abs(baseline.forecast(panel, origin, horizon)["p50"][:, rare] - actual).mean())
        errors["model"].append(np.abs(forecast(panel, origin, horizon, rare_method="model")["p50"][:, rare] - actual).mean())
    return {
        "dates": [str(d) for d in settings["model"]["validation_origins"]],
        "rare_share": float(np.mean(shares)),
        "mae_baseline": float(np.mean(errors["baseline"])), "mae_model": float(np.mean(errors["model"])),
        "better": "baseline" if np.mean(errors["baseline"]) <= np.mean(errors["model"]) else "model",
        "in_use": settings["model"]["rare_method"],
    }
