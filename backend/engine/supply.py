"""Supply forecast for red cells (red cell units plus whole blood).

Demand is nearly flat through the year; supply is what swings. So we forecast,
for each regional centre and each of the next four weeks:

1. cleared units: scheduled drives x usual yield for that kind of venue x the
   share of collections that become usable units, shifted by the testing wait;
2. what the centre ships to its hospitals, from how shipments have followed
   availability (stock plus cleared units) in the past;
3. what each hospital receives: its recent share of its centre's shipments;
4. the centre's stock at the end of each week.

Each is compared with a simple baseline (the average of the last four weeks, or
"stock stays as it is"). Everything is learned only from days before the
forecast date. Emergency appeals are never treated as scheduled: they are a
reaction to a shortage, not a plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from backend import config
from backend.engine.world import World

RED = ("RBC", "WB")


@dataclass
class SupplyHistory:
    """Daily arrays for red cell supply. Axis order: (centre or hospital, group, day)."""
    centres: list[str]
    hospitals: list[str]
    groups: list[str]
    dates: pd.DatetimeIndex
    cleared: np.ndarray          # (centres, groups, days) units that became usable at the centre
    centre_stock: np.ndarray     # (centres, groups, days) end-of-day stock at the centre
    received: np.ndarray         # (hospitals, groups, days) routine units received
    emergency: np.ndarray        # (centres, groups, days) emergency units sent to the region's hospitals
    hospital_centre: np.ndarray  # (hospitals,) index of each hospital's centre


@dataclass
class SupplyForecast:
    as_of: pd.Timestamp
    weeks: int
    cleared: np.ndarray            # (centres, groups, weeks) model
    cleared_baseline: np.ndarray   # (centres, groups, weeks) 4-week average
    shipped: np.ndarray            # (centres, groups, weeks) routine units the centre is expected to ship
    centre_stock: np.ndarray       # (centres, groups, weeks) stock at the end of each week
    centre_stock_now: np.ndarray   # (centres, groups) stock at the end of yesterday
    received: np.ndarray           # (hospitals, groups, weeks) model
    received_baseline: np.ndarray  # (hospitals, groups, weeks) 4-week average
    cleared_recent: np.ndarray     # (centres, groups) average cleared a week over the last 4 weeks
    scheduled_drives: pd.DataFrame # the drives counted, with expected collections


def _dense(index: list, groups: list, dates: pd.DatetimeIndex, frame: pd.DataFrame, key: str, value: str) -> np.ndarray:
    out = np.zeros((len(index), len(groups), len(dates)))
    frame = frame[frame[key].isin(index) & frame["blood_group"].isin(groups)
                  & (frame["date"] >= dates[0]) & (frame["date"] <= dates[-1])]
    i = pd.Index(index).get_indexer(frame[key])
    g = pd.Index(groups).get_indexer(frame["blood_group"])
    d = dates.get_indexer(frame["date"])
    np.add.at(out, (i, g, d), frame[value].to_numpy(dtype=float))
    return out


def build_history(world: World) -> SupplyHistory:
    groups = config.load_settings("blood")["blood_groups"]
    facility = world.facility
    centres = sorted(facility.index[facility["kind"] == "regional_centre"])
    hospitals = sorted(facility.index[facility["kind"] == "hospital"])
    dates = pd.date_range(world.first_date, world.last_date)
    red_units = world.unit[world.unit["component"].isin(RED)]
    cleared = (red_units.groupby(["processed_at_id", "blood_group", "available_date"]).size()
               .rename("units").reset_index().rename(columns={"available_date": "date"}))
    stock = world.stock[world.stock["component"].isin(RED)]
    delivery = world.delivery[world.delivery["component"].isin(RED)]
    routine = delivery[delivery["kind"] == "routine"]
    emergency = delivery[delivery["kind"] == "emergency"].assign(
        centre=lambda f: f["facility_id"].map(facility["region"]))
    return SupplyHistory(
        centres=centres, hospitals=hospitals, groups=groups, dates=dates,
        cleared=_dense(centres, groups, dates, cleared, "processed_at_id", "units"),
        centre_stock=_dense(centres, groups, dates, stock, "facility_id", "units"),
        received=_dense(hospitals, groups, dates, routine, "facility_id", "units"),
        emergency=_dense(centres, groups, dates, emergency, "centre", "units"),
        hospital_centre=np.array([centres.index(facility.at[h, "region"]) for h in hospitals]),
    )


_HISTORY: dict[int, SupplyHistory] = {}


def history(world: World) -> SupplyHistory:
    if id(world) not in _HISTORY:
        _HISTORY.clear()
        _HISTORY[id(world)] = build_history(world)
    return _HISTORY[id(world)]


def _weekly_back(array: np.ndarray, cut: int, weeks: int) -> np.ndarray:
    """Totals for the `weeks` full weeks ending the day before `cut`, oldest first. Shape (..., weeks)."""
    blocks = [array[..., cut - 7 * (k + 1):cut - 7 * k].sum(axis=-1) for k in range(weeks)]
    return np.stack(blocks[::-1], axis=-1)


def expected_clearing(world: World, hist: SupplyHistory, as_of: pd.Timestamp, weeks: int) -> tuple[np.ndarray, pd.DataFrame]:
    """Expected cleared red cell units per centre, group and week, from the drive schedule."""
    settings = config.load_settings("thresholds")["supply"]
    max_wait = settings["max_testing_wait_days"]
    horizon_end = as_of + pd.Timedelta(days=7 * weeks)
    facility = world.facility
    drive = world.drive.assign(centre=world.drive["collecting_site_id"].map(facility["region"]))
    past = drive[drive["date"] < as_of]

    # 1. Usual collections per drive, by venue type (per centre when there is enough history).
    venue_mean = past.groupby("venue_type")["donations_collected"].mean()
    local = past.groupby(["centre", "venue_type"])["donations_collected"].agg(["mean", "count"])

    def usual_yield(centre: str, venue: str) -> float:
        if (centre, venue) in local.index and local.loc[(centre, venue), "count"] >= 5:
            return float(local.loc[(centre, venue), "mean"])
        return float(venue_mean.get(venue, past["donations_collected"].mean()))

    # 2. Usable red cell units per collected donation, per centre (donations old enough to be tested).
    settled = past[past["date"] < as_of - pd.Timedelta(days=max_wait)]
    collected = settled.groupby("centre")["donations_collected"].sum()
    red = world.unit[world.unit["component"].isin(RED) & (world.unit["available_date"] < as_of)]
    site_centre = facility["region"]
    made = red.assign(centre=red["collecting_site_id"].map(site_centre),
                      collected_on=red["collection_date"])
    made = made[made["collected_on"] < as_of - pd.Timedelta(days=max_wait)]
    made = made[made["collected_on"] >= world.drive["date"].min()]
    per_donation = (made.groupby("centre").size() / collected).fillna(0.0)

    # 3. Blood group mix of cleared units per centre, and 4. the testing wait per collecting site.
    mix = made.groupby(["centre", "blood_group"]).size().unstack(fill_value=0)
    mix = mix.div(mix.sum(axis=1), axis=0).reindex(columns=hist.groups, fill_value=0.0)
    waits = (made["available_date"] - made["collected_on"]).dt.days.clip(0, max_wait)
    wait_table = pd.crosstab(made["collecting_site_id"], waits)
    wait_table = wait_table.div(wait_table.sum(axis=1), axis=0)
    wait_all = pd.crosstab(np.zeros(len(waits)), waits).iloc[0]
    wait_all = wait_all / wait_all.sum()

    # Drives that can still produce units after the as-of date: recent ones (collections known)
    # and scheduled ones (collections expected). Unplanned appeals in the future are left out.
    recent = drive[(drive["date"] >= as_of - pd.Timedelta(days=max_wait)) & (drive["date"] < as_of)].copy()
    recent["expected_collected"] = recent["donations_collected"].astype(float)
    recent["known"] = True
    ahead = drive[(drive["date"] >= as_of) & (drive["date"] < horizon_end)
                  & ~drive["venue_type"].isin(settings["unplanned_venues"])].copy()
    ahead["expected_collected"] = [usual_yield(c, v) for c, v in zip(ahead["centre"], ahead["venue_type"])]
    ahead["known"] = False
    counted = pd.concat([recent, ahead], ignore_index=True)

    out = np.zeros((len(hist.centres), len(hist.groups), weeks))
    centre_index = {c: i for i, c in enumerate(hist.centres)}
    for row in counted.itertuples():
        if row.centre not in centre_index or row.centre not in per_donation.index:
            continue
        units = row.expected_collected * per_donation[row.centre]
        spread = wait_table.loc[row.collecting_site_id] if row.collecting_site_id in wait_table.index else wait_all
        shares = mix.loc[row.centre].to_numpy() if row.centre in mix.index else np.full(len(hist.groups), 1 / len(hist.groups))
        for wait, share in spread.items():
            day = (row.date + pd.Timedelta(days=int(wait)) - as_of).days
            if 0 <= day < 7 * weeks and share > 0:
                out[centre_index[row.centre], :, day // 7] += units * share * shares
    schedule = ahead[["date", "centre", "collecting_site_id", "venue_type", "expected_collected"]].copy()
    return out, schedule


def forecast(world: World, as_of, weeks: int | None = None) -> SupplyForecast:
    settings = config.load_settings("thresholds")["supply"]
    weeks = weeks or settings["weeks_ahead"]
    as_of = pd.Timestamp(as_of).normalize()
    hist = history(world)
    cut = int((as_of - hist.dates[0]).days)
    n_back = cut // 7
    base_weeks, share_weeks = settings["baseline_weeks"], settings["share_weeks"]

    cleared, schedule = expected_clearing(world, hist, as_of, weeks)
    cleared_recent = _weekly_back(hist.cleared, cut, base_weeks).mean(axis=-1)
    cleared_baseline = np.repeat(cleared_recent[..., None], weeks, axis=-1)

    # History, week by week: what was available at each centre and what it shipped.
    cleared_w = _weekly_back(hist.cleared, cut, n_back)                       # (C, G, n_back)
    received_w = _weekly_back(hist.received, cut, n_back)                     # (H, G, n_back)
    emergency_w = _weekly_back(hist.emergency, cut, n_back)
    starts = [cut - 7 * (n_back - k) - 1 for k in range(n_back)]              # day before each week
    stock_start = np.stack([hist.centre_stock[..., s] if s >= 0 else hist.centre_stock[..., 0] for s in starts], axis=-1)
    stock_end = np.stack([hist.centre_stock[..., s + 7] for s in starts], axis=-1)
    n_centres, n_groups = len(hist.centres), len(hist.groups)
    shipped_w = np.zeros((n_centres, n_groups, n_back))
    for c in range(n_centres):
        shipped_w[c] = received_w[hist.hospital_centre == c].sum(axis=0)
    available_w = stock_start + cleared_w
    # Units that left the centre some other way (expiry, discards, transfers), as a share of what was available.
    other_out = np.clip(available_w - shipped_w - emergency_w - stock_end, 0, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        loss_rate = np.where(available_w.sum(axis=-1) > 0, other_out.sum(axis=-1) / available_w.sum(axis=-1), 0.0)
    emergency_recent = emergency_w[..., -base_weeks:].mean(axis=-1)

    # Each hospital's share of its centre's routine shipments, over recent weeks.
    recent_received = received_w[..., -share_weeks:].sum(axis=-1)             # (H, G)
    recent_shipped = shipped_w[..., -share_weeks:].sum(axis=-1)               # (C, G)
    share = np.zeros_like(recent_received)
    for h, c in enumerate(hist.hospital_centre):
        with np.errstate(divide="ignore", invalid="ignore"):
            share[h] = np.where(recent_shipped[c] > 0, recent_received[h] / recent_shipped[c], 0.0)

    stock_now = hist.centre_stock[..., cut - 1]
    shipped = np.zeros((n_centres, n_groups, weeks))
    stock_path = np.zeros((n_centres, n_groups, weeks))
    for c in range(n_centres):
        for g in range(n_groups):
            x, y = available_w[c, g], shipped_w[c, g]
            fitted = None
            if len(x) >= 6 and y.sum() > 0 and np.ptp(x) > 0:
                fitted = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(x, y)
            stock = stock_now[c, g]
            for k in range(weeks):
                available = stock + cleared[c, g, k]
                ship = float(fitted.predict([available])[0]) if fitted is not None else float(y[-base_weeks:].mean())
                ship = min(ship, available)
                shipped[c, g, k] = ship
                stock = max(0.0, available - ship - min(emergency_recent[c, g], max(available - ship, 0.0)))
                stock *= (1 - min(loss_rate[c, g], 0.9))
                stock_path[c, g, k] = stock

    received = np.zeros((len(hist.hospitals), n_groups, weeks))
    for h, c in enumerate(hist.hospital_centre):
        received[h] = share[h][:, None] * shipped[c]
    received_baseline = np.repeat(received_w[..., -base_weeks:].mean(axis=-1)[..., None], weeks, axis=-1)

    return SupplyForecast(as_of=as_of, weeks=weeks, cleared=cleared, cleared_baseline=cleared_baseline,
                          shipped=shipped, centre_stock=stock_path, centre_stock_now=stock_now,
                          received=received, received_baseline=received_baseline,
                          cleared_recent=cleared_recent, scheduled_drives=schedule)


def actuals(world: World, as_of, weeks: int) -> dict[str, np.ndarray]:
    """What really happened in the forecast weeks (NaN where the data ends)."""
    hist = history(world)
    cut = int((pd.Timestamp(as_of) - hist.dates[0]).days)
    n_days = len(hist.dates)

    def weekly(array: np.ndarray) -> np.ndarray:
        out = np.full(array.shape[:-1] + (weeks,), np.nan)
        for k in range(weeks):
            if cut + 7 * (k + 1) <= n_days:
                out[..., k] = array[..., cut + 7 * k:cut + 7 * (k + 1)].sum(axis=-1)
        return out

    stock = np.full(hist.centre_stock.shape[:-1] + (weeks,), np.nan)
    for k in range(weeks):
        if cut + 7 * (k + 1) - 1 < n_days:
            stock[..., k] = hist.centre_stock[..., cut + 7 * (k + 1) - 1]
    return {"cleared": weekly(hist.cleared), "received": weekly(hist.received), "centre_stock": stock}
