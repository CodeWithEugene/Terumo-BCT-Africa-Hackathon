"""Demand history as a dense panel: one column per hospital, component and blood group."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backend import config
from backend.db.core import read

COMPONENTS = ("RBC", "FFP", "PLT")


@dataclass
class DemandPanel:
    dates: pd.DatetimeIndex        # every day of the data, in order
    series: pd.DataFrame           # one row per series, with facility details
    requested: np.ndarray          # (days, series) units requested
    emergency: np.ndarray          # (days, series) emergency requests
    requests: np.ndarray           # (days, series) number of requests
    unmet: np.ndarray              # (days, series) requests not fully met
    shortage: np.ndarray           # (days, series) requests not fully met, or that needed an emergency delivery

    def position(self, date) -> int:
        """Row number of a date. A date one day past the end is allowed (returns len)."""
        date = pd.Timestamp(date)
        if date == self.dates[-1] + pd.Timedelta(days=1):
            return len(self.dates)
        return int(self.dates.get_loc(date))


def load_panel(db_path: Path | None = None) -> DemandPanel:
    groups = config.load_settings("blood")["blood_groups"]
    facility = read(
        "SELECT facility_id, name, facility_type, keph_level, beds, region, region_name, "
        "routine_deliveries_per_week FROM facility WHERE kind = 'hospital' ORDER BY facility_id",
        path=db_path)
    series = (
        facility.merge(pd.DataFrame({"component": COMPONENTS}), how="cross")
        .merge(pd.DataFrame({"blood_group": groups}), how="cross")
        .reset_index(drop=True)
    )
    series["series_id"] = series["facility_id"] + "|" + series["component"] + "|" + series["blood_group"]

    demand = read("SELECT facility_id, component, blood_group, date, units_requested, emergency_requests, "
                  "requests, requests_not_fully_met, shortage_requests FROM demand_daily WHERE blood_group <> 'unknown'",
                  parse_dates=["date"], path=db_path)
    bounds = read("SELECT MIN(date) a, MAX(date) b FROM stock_daily", path=db_path).iloc[0]
    dates = pd.date_range(bounds["a"], bounds["b"])

    demand["series_id"] = demand["facility_id"] + "|" + demand["component"] + "|" + demand["blood_group"]
    column = pd.Series(np.arange(len(series)), index=series["series_id"])
    rows = dates.get_indexer(demand["date"])
    cols = column.reindex(demand["series_id"]).to_numpy()

    def dense(values: pd.Series) -> np.ndarray:
        out = np.zeros((len(dates), len(series)), dtype=float)
        np.add.at(out, (rows, cols), values.to_numpy(dtype=float))
        return out

    return DemandPanel(
        dates=dates, series=series,
        requested=dense(demand["units_requested"]),
        emergency=dense(demand["emergency_requests"]),
        requests=dense(demand["requests"]),
        unmet=dense(demand["requests_not_fully_met"]),
        shortage=dense(demand["shortage_requests"]),
    )
