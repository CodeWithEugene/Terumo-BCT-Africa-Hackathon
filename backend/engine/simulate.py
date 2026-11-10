"""Walk a shelf forward day by day. Pure arithmetic, no data access.

Each day: deliveries arrive, requests are filled oldest units first, and units
that reach their expiry date are removed at the end of the day.
    stock[t+1] = stock[t] + expected_delivery[t] - forecast_demand[t] - units_expiring[t]
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

NO_EXPIRY = 10_000  # "does not expire inside the projection"


@dataclass
class Path:
    stock_end: np.ndarray    # units on the shelf at the end of each day
    short: np.ndarray        # units of demand that could not be met each day
    expired: np.ndarray      # units lost to expiry each day


def simulate(cohorts: list[tuple[int, float]], demand: np.ndarray, arrivals: np.ndarray) -> Path:
    """`cohorts` is a list of (days until expiry counted from day 0, units)."""
    shelf = sorted([[int(d), float(u)] for d, u in cohorts if u > 0])
    days = len(demand)
    stock_end, short, expired = np.zeros(days), np.zeros(days), np.zeros(days)
    for t in range(days):
        if arrivals[t] > 0:
            shelf.append([NO_EXPIRY, float(arrivals[t])])
        need = float(demand[t])
        for cohort in shelf:                 # oldest first
            if need <= 0:
                break
            used = min(cohort[1], need)
            cohort[1] -= used
            need -= used
        short[t] = need
        expired[t] = sum(c[1] for c in shelf if c[0] <= t)
        shelf = [c for c in shelf if c[0] > t and c[1] > 1e-9]
        stock_end[t] = sum(c[1] for c in shelf)
    return Path(stock_end, short, expired)


def days_of_cover(cohorts: list[tuple[int, float]], demand: np.ndarray) -> tuple[float | None, bool]:
    """How long the shelf lasts with no deliveries.

    Returns (days, capped). `days` is None when no use is expected at all.
    `capped` is True when the shelf outlasts the projection.
    """
    if demand.sum() <= 1e-9:
        return None, False
    if sum(u for _, u in cohorts) <= 1e-9:
        return 0.0, False
    path = simulate(cohorts, demand, np.zeros(len(demand)))
    hit = np.nonzero(path.short > 1e-9)[0]
    if len(hit) == 0:
        return float(len(demand)), True
    t = int(hit[0])
    met_share = 1 - path.short[t] / demand[t] if demand[t] > 0 else 0.0
    return round(t + met_share, 2), False


def cumulative_range(p10: np.ndarray, p50: np.ndarray, p90: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Quiet-spell and busy-spell demand paths.

    Daily ranges do not simply add up: a busy day is often followed by a quiet
    one. Treating days as independent, the range of a running total grows with
    the square root of the summed squared daily margins.
    """
    centre = np.cumsum(p50)
    high = centre + np.sqrt(np.cumsum((p90 - p50) ** 2))
    low = np.clip(centre - np.sqrt(np.cumsum((p50 - p10) ** 2)), 0, None)
    low = np.maximum.accumulate(low)
    return np.diff(low, prepend=0.0), np.diff(high, prepend=0.0)


def stockout_probability(shelf: float, arrivals: np.ndarray, expired: np.ndarray, p50: np.ndarray, p90: np.ndarray,
                         days: list[int], draws: int = 400, seed: int = 0) -> dict[int, float]:
    """Chance that demand outruns the shelf within each of `days` (counted from today).

    Daily demand is drawn as counts: Poisson around the forecast, widened to a
    gamma-Poisson mix where the forecast range says demand is burstier than
    Poisson. A path "runs out" on the first day its running demand exceeds the
    units available (shelf plus deliveries so far, minus units expired so far).
    """
    rng = np.random.default_rng(seed)
    mean = np.clip(np.asarray(p50, dtype=float), 0, None)
    spread = np.clip((np.asarray(p90, dtype=float) - mean) / 1.2816, 0, None) ** 2
    variance = np.maximum(mean, spread)
    rate = np.tile(mean, (draws, 1))
    wide = variance > mean + 1e-9
    if wide.any():
        shape = np.where(wide, mean ** 2 / np.where(wide, variance - mean, 1.0), 1.0)
        scale = np.where(wide, (variance - mean) / np.where(mean > 0, mean, 1.0), 0.0)
        gamma = rng.gamma(np.where(shape > 0, shape, 1.0), np.where(scale > 0, scale, 1.0), size=(draws, len(mean)))
        rate = np.where(wide & (mean > 0), gamma, rate)
    demand = rng.poisson(rate)
    available = shelf + np.cumsum(arrivals) - np.concatenate([[0.0], np.cumsum(expired)[:-1]])
    short = np.cumsum(demand, axis=1) > available + 1e-9
    out = {}
    for n in days:
        n = max(1, min(int(n), len(mean)))
        out[n] = float(short[:, :n].any(axis=1).mean())
    return out
