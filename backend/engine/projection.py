"""Stock projection, status and suggested order for every series, as of a date.

A "series" is one hospital, one product (red cells, plasma or platelets) and
one blood group. Red cell cover counts red cell units and whole blood together.

The engine only suggests. Every order or early delivery is a request that a
signed-in person accepts, changes or rejects. Nothing here substitutes groups.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend import config
from backend.engine import forecasting, reasons, words
from backend.engine.simulate import NO_EXPIRY, cumulative_range, days_of_cover, simulate
from backend.engine.world import World

MINUS = "\u2212"
STATUS_RANK = {"act": 0, "watch": 1, "steady": 2, "not_held": 3}


@dataclass
class Snapshot:
    """Everything known on the morning of `as_of` (nothing from that day or later)."""
    world: World
    as_of: pd.Timestamp
    horizon: int
    forecast: forecasting.Forecast
    dates: pd.DatetimeIndex
    shelf: dict = field(default_factory=dict)          # (facility, product, group) -> units
    shelf_split: dict = field(default_factory=dict)    # (facility, product, group) -> {component: units}
    cohorts: dict = field(default_factory=dict)        # (facility, product, group) -> [(days to expiry, units)]
    held: set = field(default_factory=set)             # (facility, product) ever on that hospital's shelf
    delivery_days: dict = field(default_factory=dict)  # facility -> set of weekdays (0 = Monday)
    usual: dict = field(default_factory=dict)          # (facility, product, group, weekday) -> units
    lead_hours: dict = field(default_factory=dict)     # facility -> usual emergency resupply hours
    context: dict = field(default_factory=dict)        # facts for the reasons (see reasons.py)
    supply: object = None                              # supply forecast for red cells, or None
    received: dict = field(default_factory=dict)       # (facility, group) -> expected routine units per week
    settings: dict = field(default_factory=dict)


def build_snapshot(world: World, as_of, model: str = "auto", use_supply: bool | None = None) -> Snapshot:
    as_of = pd.Timestamp(as_of).normalize()
    settings = config.load_settings("thresholds")
    horizon = settings["forecast"]["horizon_days"]
    if not (world.first_date + pd.Timedelta(days=56) <= as_of <= world.last_date + pd.Timedelta(days=1)):
        raise ValueError("That date is outside the data, or too early to have 8 weeks of history.")
    snap = Snapshot(
        world=world, as_of=as_of, horizon=horizon, settings=settings,
        forecast=forecasting.make(world.panel, as_of, horizon, model),
        dates=pd.date_range(as_of, periods=horizon),
    )
    yesterday = as_of - pd.Timedelta(days=1)

    # Shelf at the end of yesterday.
    stock = world.stock[(world.stock["date"] == yesterday) & world.stock["product"].notna()]
    for (facility, product, group), rows in stock.groupby(["facility_id", "product", "blood_group"]):
        snap.shelf[(facility, product, group)] = float(rows["units"].sum())
        snap.shelf_split[(facility, product, group)] = {
            c: int(u) for c, u in zip(rows["component"], rows["units"]) if u > 0}
    past_stock = world.stock[(world.stock["date"] < as_of) & world.stock["product"].notna()]
    snap.held = set(map(tuple, past_stock[["facility_id", "product"]].drop_duplicates().to_numpy()))

    # Which units are on which shelf, to know what expires when.
    moves = world.unit_move[world.unit_move["at"] < as_of].groupby("unit_id").tail(1)
    unit = world.unit.merge(moves[["unit_id", "to_facility_id"]], on="unit_id", how="left")
    unit["place"] = unit["to_facility_id"].fillna(unit["processed_at_id"])
    live = ((unit["available_date"] < as_of) & (unit["expiry_date"] >= as_of) & unit["product"].notna()
            & ((unit["status"] == "in_stock") | (unit["status_date"] >= as_of)))
    unit = unit[live & unit["place"].str.startswith("HSP")]
    unit = unit.assign(days_left=(unit["expiry_date"] - as_of).dt.days)
    counted = unit.groupby(["place", "product", "blood_group", "days_left"]).size()
    by_key: dict = {}
    for (facility, product, group, days_left), n in counted.items():
        by_key.setdefault((facility, product, group), []).append((int(days_left), float(n)))
    for key, on_shelf in snap.shelf.items():
        snap.cohorts[key] = _reconcile(by_key.get(key, []), on_shelf)

    # Delivery days: each hospital's scheduled number of deliveries a week, on the weekdays
    # it has most often received routine deliveries (all confirmed history before the date).
    # Usual quantities: the average over the last few weeks, so a supply that has dried up shows.
    weeks = settings["alerts"]["delivery_learning_weeks"]
    routine = world.delivery[(world.delivery["kind"] == "routine") & (world.delivery["confirmed"] == 1)
                             & (world.delivery["date"] < as_of) & world.delivery["product"].notna()]
    routine = routine.assign(weekday=routine["date"].dt.day_of_week)
    visits = routine.groupby(["facility_id", "weekday"])["date"].nunique()
    per_week = world.facility["routine_deliveries_per_week"]
    for facility, counts in visits.groupby(level=0):
        counts = counts.droplevel(0).sort_values(ascending=False)
        planned = per_week.get(facility)
        keep = int(planned) if pd.notna(planned) and planned > 0 else int(
            (counts / counts.max() >= settings["alerts"]["delivery_day_min_share"]).sum())
        snap.delivery_days[facility] = {int(day) for day in counts.index[:keep]}
    recent = routine[routine["date"] >= as_of - pd.Timedelta(weeks=weeks)]
    usual = recent.groupby(["facility_id", "product", "blood_group", "weekday"])["units"].sum() / weeks
    snap.usual = {key: float(value) for key, value in usual.items()}

    # Usual emergency resupply time, per hospital (falls back to region, then all).
    past = world.emergency[world.emergency["date"] < as_of]
    overall = float(past["hours"].median()) if len(past) else 5.0
    region_of = world.facility["region"]
    by_region = past.assign(region=past["facility_id"].map(region_of)).groupby("region")["hours"].median()
    by_facility = past.groupby("facility_id")["hours"].agg(["median", "count"])
    for facility in world.facility.index[world.facility["kind"] == "hospital"]:
        if facility in by_facility.index and by_facility.loc[facility, "count"] >= 5:
            snap.lead_hours[facility] = float(by_facility.loc[facility, "median"])
        else:
            snap.lead_hours[facility] = float(by_region.get(region_of[facility], overall))

    # Red cell deliveries follow what the regional centre can supply (see supply.py).
    if use_supply is None:
        use_supply = bool(settings.get("supply", {}).get("use_in_projection", False))
    if use_supply:
        try:
            from backend.engine import supply

            made = supply.forecast(world, as_of)
            hist = supply.history(world)
            snap.supply = made
            for h, facility in enumerate(hist.hospitals):
                for g, group in enumerate(hist.groups):
                    snap.received[(facility, group)] = made.received[h, g]
        except Exception:  # noqa: BLE001  (fall back to usual deliveries, never stop the brief)
            snap.supply, snap.received = None, {}

    snap.context = reasons.build_context(snap)
    return snap


def _expected_arrivals(snap: Snapshot, facility: str, product: str, group: str, delivery_days: set) -> np.ndarray:
    """Expected routine units arriving on each projected day."""
    usual = np.array([snap.usual.get((facility, product, group, d.weekday()), 0.0)
                      if d.weekday() in delivery_days else 0.0 for d in snap.dates])
    weekly = snap.received.get((facility, group)) if product == "RBC" else None
    if weekly is None or not delivery_days:
        return usual
    out = np.zeros(snap.horizon)
    for week in range(math.ceil(snap.horizon / 7)):
        days = [t for t in range(7 * week, min(7 * week + 7, snap.horizon)) if snap.dates[t].weekday() in delivery_days]
        if not days or week >= len(weekly):
            continue
        weights = usual[days]
        weights = weights / weights.sum() if weights.sum() > 0 else np.full(len(days), 1 / len(days))
        out[days] = weekly[week] * weights
    return out


def _reconcile(cohorts: list[tuple[int, float]], on_shelf: float) -> list[tuple[int, float]]:
    """Make unit-level expiry dates agree with the shelf count (the count wins)."""
    cohorts = sorted(cohorts)
    known = sum(u for _, u in cohorts)
    if known < on_shelf:
        return cohorts + [(NO_EXPIRY, on_shelf - known)]
    extra = known - on_shelf
    while extra > 1e-9 and cohorts:          # drop the newest units first
        days_left, n = cohorts[-1]
        take = min(n, extra)
        extra -= take
        if n - take <= 1e-9:
            cohorts.pop()
        else:
            cohorts[-1] = (days_left, n - take)
    return cohorts


def series_view(snap: Snapshot, index: int, detail: bool = True) -> dict:
    """The full picture for one series."""
    world, alerts = snap.world, snap.settings["alerts"]
    row = world.panel.series.iloc[index]
    facility, product, group = row["facility_id"], row["component"], row["blood_group"]
    key = (facility, product, group)
    p10, p50, p90 = snap.forecast.p10[:, index], snap.forecast.p50[:, index], snap.forecast.p90[:, index]
    low, high = cumulative_range(p10, p50, p90)
    view: dict = {
        "id": row["series_id"], "facility_id": facility, "facility_name": row["name"],
        "component": product, "component_label": config.load_settings("blood")["products"][product]["label"],
        "blood_group": group, "blood_group_label": words.group_symbol(group),
        "blood_group_words": words.group_words(group),
        "as_of": str(snap.as_of.date()), "model": snap.forecast.model, "mode": snap.forecast.mode,
        "expected_use_7_days": round(float(p50[:7].sum()), 1),
        "expected_use_7_days_range": [round(float(low[:7].sum()), 1), round(float(high[:7].sum()), 1)],
    }
    if (facility, product) not in snap.held:
        view.update({"held": False, "status": "not_held", "status_rank": STATUS_RANK["not_held"],
                     "status_label": "Not held here",
                     "status_line": f"This hospital does not hold {words.PRODUCT_WORDS[product]}. "
                                    "Requests are filled by delivery from the regional centre.",
                     "units_on_shelf": 0, "cover_days": None, "reasons": [], "suggestion": None})
        return view

    shelf = snap.shelf.get(key, 0.0)
    cohorts = snap.cohorts.get(key, [])
    delivery_days = snap.delivery_days.get(facility, set())
    arrivals = _expected_arrivals(snap, facility, product, group, delivery_days)
    is_delivery = [d.weekday() in delivery_days for d in snap.dates]
    lead = alerts["order_lead_days"]
    upcoming = [t for t in range(lead, snap.horizon) if is_delivery[t]]
    n1 = upcoming[0] if upcoming else None                       # next delivery an order can still change
    n2 = upcoming[1] if len(upcoming) > 1 else None
    window = n1 if n1 is not None else snap.horizon

    mid = simulate(cohorts, p50, arrivals)
    busy = simulate(cohorts, high, arrivals)
    quiet = simulate(cohorts, low, arrivals)
    cover, capped = days_of_cover(cohorts, p50)
    worst_cover, _ = days_of_cover(cohorts, high)

    short_before = float(mid.short[:window].sum())
    short_before_busy = float(busy.short[:window].sum())
    short_horizon = float(mid.short.sum())
    use_before = float(p50[:window].sum())
    floor = float(snap.settings.get("minimum_stock", {}).get(product, {}).get(group, 0))
    effectively_empty = shelf + arrivals[0] < 1

    if short_before >= alerts["act_shortfall_units"]:
        status, why = "act", "short_before_delivery"
    elif effectively_empty and use_before >= alerts["empty_shelf_units_at_risk"]:
        status, why = "act", "empty_shelf"
    elif short_before_busy >= alerts["watch_shortfall_units"]:
        status, why = "watch", "short_if_busy"
    elif short_horizon >= alerts["watch_horizon_shortfall_units"]:
        status, why = "watch", "short_later"
    elif (cover is not None and not capped and cover < alerts["watch_cover_days"]
          and p50[:7].sum() >= alerts["watch_min_weekly_use"]):
        status, why = "watch", "low_cover"
    elif shelf < floor:
        status, why = "watch", "below_minimum"
    else:
        status, why = "steady", "steady"

    def first_short(path) -> str | None:
        if path.short.sum() < 0.5:
            return None
        hit = np.nonzero(np.cumsum(path.short) >= 0.5)[0]
        return str(snap.dates[int(hit[0])].date())

    expiring_before = float(mid.expired[:window].sum())
    next_delivery = None
    if n1 is not None:
        next_delivery = {"date": str(snap.dates[n1].date()), "label": words.day(snap.dates[n1]),
                         "days_away": n1, "usual_units": round(float(arrivals[n1]), 1)}

    view.update({
        "held": True, "status": status, "status_why": why, "status_rank": STATUS_RANK[status],
        "status_label": {"act": "Act", "watch": "Watch", "steady": "Steady"}[status],
        "units_on_shelf": int(round(shelf)), "shelf_split": snap.shelf_split.get(key, {}),
        "expected_daily_use": round(float(p50[:7].mean()), 2),
        "cover_days": cover, "cover_capped": capped, "worst_cover_days": worst_cover,
        "next_delivery": next_delivery,
        "arriving_today": round(float(arrivals[0]), 1),
        "deliveries_from_supply_forecast": product == "RBC" and bool(snap.received),
        "stockout_date": first_short(mid), "worst_stockout_date": first_short(busy),
        "shortfall_before_delivery": round(short_before, 1),
        "worst_shortfall_before_delivery": round(short_before_busy, 1),
        "expiring_before_delivery": round(expiring_before, 1),
        "minimum_stock": floor,
        "emergency_lead_hours": round(snap.lead_hours.get(facility, 0.0), 1),
    })
    view["suggestion"] = _suggest(snap, view, p50, high, mid, arrivals, n1, n2, floor, shelf)
    view["status_line"] = reasons.status_line(snap, view)
    view["reasons"] = reasons.build(snap, index, view)
    if detail:
        view["projection"] = [{
            "date": str(d.date()), "label": words.day(d), "weekend": d.weekday() >= 5,
            "demand": round(float(p50[t]), 2), "demand_low": round(float(low[t]), 2),
            "demand_high": round(float(high[t]), 2),
            "delivery": round(float(arrivals[t]), 1), "is_delivery_day": bool(is_delivery[t]),
            "expiring": round(float(mid.expired[t]), 1),
            "stock": round(float(mid.stock_end[t]), 1),
            "stock_low": round(float(busy.stock_end[t]), 1),
            "stock_high": round(float(quiet.stock_end[t]), 1),
            "short": round(float(mid.short[t]), 2),
        } for t, d in enumerate(snap.dates)]
        view["compatible_cover"] = _compatible(snap, facility, product, group)
    return view


def _suggest(snap, view, p50, high, mid, arrivals, n1, n2, floor, shelf) -> dict | None:
    """A suggested quantity, always shown as a sum of its parts."""
    max_days = snap.settings["orders"]["max_cover_days"]
    if view["status"] == "act" and view["status_why"] in ("short_before_delivery", "empty_shelf"):
        # The next routine delivery is too late. Suggest asking for an early one.
        window = n1 if n1 is not None else snap.horizon
        until = words.day(snap.dates[n1]) if n1 is not None else "the end of the fortnight"
        use_busy = float(high[:window].sum())
        have = shelf + float(arrivals[:window].sum())
        raw = use_busy + floor - have
        quantity = max(1, math.ceil(raw - 1e-9))
        parts = [
            {"label": f"Use expected before {until}, allowing for a busy spell", "units": round(use_busy, 1)},
            {"label": "Minimum stock set by staff", "units": floor},
            {"label": "On the shelf now, plus today's delivery", "units": -round(have, 1)},
        ]
        return {"kind": "early_delivery", "title": "Ask the regional centre for an early delivery",
                "needs_approval": "Moving blood between facilities needs authorisation. This is a request, "
                                  "not an order.",
                "quantity": quantity, "usual_quantity": 0, "for_date": view["as_of"],
                "for_label": "today", "parts": [p for p in parts if p["units"] != 0],
                "sum_text": _sum_text(parts, quantity)}
    if n1 is None:
        return None
    end = n2 if n2 is not None else min(n1 + 3, snap.horizon)
    use = float(p50[n1:end].sum())
    margin = float(high[n1:end].sum()) - use
    on_shelf_then = float(mid.stock_end[n1 - 1]) if n1 > 0 else shelf
    raw = use + margin + floor - on_shelf_then
    cap = float(p50[n1:min(n1 + max_days, snap.horizon)].sum()) / max(1, min(max_days, snap.horizon - n1)) * max_days
    cap = math.ceil(cap + floor - on_shelf_then - 1e-9)
    quantity = max(0, min(math.ceil(raw - 1e-9), max(cap, 0)))
    usual = int(round(float(arrivals[n1])))
    span = f"{words.day(snap.dates[n1])} to {words.day(snap.dates[end - 1])}"
    parts = [
        {"label": f"Expected use, {span}", "units": round(use, 1)},
        {"label": "Margin for a busy spell", "units": round(margin, 1)},
        {"label": "Minimum stock set by staff", "units": floor},
        {"label": f"Expected on the shelf on {words.day(snap.dates[n1])} morning", "units": -round(on_shelf_then, 1)},
    ]
    return {"kind": "order", "title": f"Order for {words.day(snap.dates[n1])}",
            "needs_approval": None, "quantity": quantity, "usual_quantity": usual,
            "for_date": str(snap.dates[n1].date()), "for_label": words.day(snap.dates[n1]),
            "capped": math.ceil(raw - 1e-9) > quantity,
            "parts": [p for p in parts if p["units"] != 0], "sum_text": _sum_text(parts, quantity)}


def _sum_text(parts: list[dict], quantity: int) -> str:
    """'6.2 + 2.1 + 2 − 3 = 7.3, rounded up to 8 units'."""
    shown = [p for p in parts if p["units"] != 0]
    if not shown:
        return f"{words.units(quantity)}"
    text = ""
    for i, part in enumerate(shown):
        value = abs(part["units"])
        number = f"{value:g}"
        if i == 0:
            text = number if part["units"] >= 0 else MINUS + number
        else:
            text += f" {'+' if part['units'] >= 0 else MINUS} {number}"
    total = round(sum(p["units"] for p in shown), 1)
    if len(shown) == 1 and total > 0:
        if abs(total - quantity) < 1e-9:
            return words.units(quantity)
        return f"{total:g}, rounded up to {words.units(quantity)}"
    if total <= 0:
        return f"{text} = {MINUS if total < 0 else ''}{abs(total):g}, so no order is needed"
    if abs(total - quantity) < 1e-9:
        return f"{text} = {words.units(quantity)}"
    if quantity < total:
        return f"{text} = {total:g}, held to {words.units(quantity)} to limit wastage"
    return f"{text} = {total:g}, rounded up to {words.units(quantity)}"


def _compatible(snap: Snapshot, facility: str, product: str, group: str) -> dict | None:
    """Units of other groups a qualified person could consider. Information only."""
    blood = config.load_settings("blood")
    if product == "RBC":
        donors = [g for g in blood["red_cell_compatible_donors"][group] if g != group]
    elif product == "FFP":
        letter = group[:-1]
        letters = [l for l in blood["plasma_compatible_donors"][letter] if l != letter]
        donors = [g for g in blood["blood_groups"] if g[:-1] in letters]
    else:
        return None
    rows = [{"blood_group": g, "blood_group_label": words.group_symbol(g),
             "units": int(round(snap.shelf.get((facility, product, g), 0.0)))} for g in donors]
    return {"units": sum(r["units"] for r in rows), "groups": rows,
            "note": "Information only. Issue decisions stay with qualified staff."}


def facility_series(snap: Snapshot, facility_id: str) -> list[int]:
    series = snap.world.panel.series
    return list(series.index[series["facility_id"] == facility_id])


def morning_list(snap: Snapshot, facility_id: str, component: str | None = None, detail: bool = False) -> list[dict]:
    """Every series for one hospital, the ones needing attention first."""
    series = snap.world.panel.series
    views = [series_view(snap, i, detail=detail) for i in facility_series(snap, facility_id)
             if component is None or series.at[i, "component"] == component]
    order = {g: n for n, g in enumerate(config.load_settings("blood")["blood_groups"])}
    return sorted(views, key=lambda v: (v["status_rank"], v["cover_days"] if v["cover_days"] is not None else 99,
                                        order[v["blood_group"]]))
