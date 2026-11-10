"""Reasons: two or three short sentences per alert, built by templates.

Every number in a sentence is computed from data before the as-of date.
No language model is involved.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.engine import words
from backend.pipeline.calendar import school_breaks


def build_context(snap) -> dict:
    """Facts shared by many series: school calendar, collections, centre stock, trends."""
    world, as_of = snap.world, snap.as_of
    panel = world.panel
    cut = panel.position(as_of)
    context: dict = {}

    # Requests: last 4 weeks against the 4 weeks before, and recent unmet requests.
    context["last4"] = panel.requested[cut - 28:cut].sum(axis=0)
    context["prev4"] = panel.requested[cut - 56:cut - 28].sum(axis=0)
    context["unmet14"] = panel.unmet[cut - 14:cut].sum(axis=0)

    # Routine deliveries received in the last 4 weeks, per series.
    recent = world.delivery[(world.delivery["kind"] == "routine") & (world.delivery["date"] < as_of)
                            & (world.delivery["date"] >= as_of - pd.Timedelta(days=28))
                            & world.delivery["product"].notna()]
    context["routine28"] = recent.groupby(["facility_id", "product", "blood_group"])["units"].sum().to_dict()

    # Stock at each regional centre at the end of yesterday.
    yesterday = as_of - pd.Timedelta(days=1)
    centre = world.stock[(world.stock["date"] == yesterday) & world.stock["facility_id"].str.startswith("RBTC")
                         & world.stock["product"].notna()]
    context["centre_stock"] = centre.groupby(["facility_id", "product", "blood_group"])["units"].sum().to_dict()

    # School calendar and what the last long break did to collections, per region.
    breaks = school_breaks()
    long_breaks = breaks[breaks["days"] >= 14]
    current = long_breaks[(long_breaks["start"] <= as_of) & (long_breaks["end"] >= as_of)]
    ahead = long_breaks[long_breaks["start"] > as_of]
    done = long_breaks[long_breaks["end"] < as_of]
    school: dict = {"in_break": len(current) > 0}
    if len(current):
        school["break_name"] = current.iloc[0]["name"]
        school["break_end"] = current.iloc[0]["end"]
        school["days_since_start"] = int((as_of - current.iloc[0]["start"]).days)
    if len(ahead):
        school["next_start"] = ahead.iloc[0]["start"]
        school["next_name"] = ahead.iloc[0]["name"]
        school["days_to_next"] = int((ahead.iloc[0]["start"] - as_of).days)
    context["school"] = school

    drops: dict = {}
    if len(done):
        last = done.iloc[-1]
        site_region = world.facility["region"]
        drive = world.drive.assign(region=world.drive["collecting_site_id"].map(site_region))
        during = drive[(drive["date"] >= last["start"]) & (drive["date"] <= last["end"])]
        before = drive[(drive["date"] >= last["start"] - pd.Timedelta(days=28)) & (drive["date"] < last["start"])]
        # The data starts on 1 Nov 2025, inside a break, so only use breaks with a full "before" period.
        if before["date"].min() <= last["start"] - pd.Timedelta(days=21):
            for region in world.facility.index[world.facility["kind"] == "regional_centre"]:
                rate_during = during.loc[during["region"] == region, "donations_collected"].sum() / last["days"]
                rate_before = before.loc[before["region"] == region, "donations_collected"].sum() / 28
                if rate_before > 0:
                    drops[region] = {"name": last["name"], "change_pct": round(100 * (rate_during / rate_before - 1)),
                                     "per_week_before": round(rate_before * 7), "per_week_during": round(rate_during * 7)}
    context["break_effect"] = drops
    return context


def status_line(snap, view: dict) -> str:
    """One plain sentence that says what the status means for this group."""
    why = view["status_why"]
    group = view["blood_group_words"]
    delivery = view["next_delivery"]["label"] if view["next_delivery"] else None
    before = f"before {delivery}'s delivery" if delivery else "in the next 14 days"
    if why == "short_before_delivery":
        day = words.day(view["stockout_date"]) if view["stockout_date"] else "soon"
        return (f"{group} is expected to run out on {day}, {before}: "
                f"about {words.units(view['shortfall_before_delivery'])} short.")
    if why == "empty_shelf":
        return (f"The {group} shelf is empty and requests are expected {before}. "
                f"An emergency delivery here usually takes about {view['emergency_lead_hours']:g} hours.")
    if why == "short_if_busy":
        return (f"{group} lasts until {delivery} on a normal run of days, but would run out in a busy spell "
                f"(about {words.units(view['worst_shortfall_before_delivery'])} short).")
    if why == "short_later":
        day = words.day(view["stockout_date"]) if view["stockout_date"] else "later in the fortnight"
        return f"{group} is fine {before}, but is expected to run short on {day} if orders stay as usual."
    if why == "low_cover":
        return f"{group} has {words.days(view['cover_days'])} of cover on the shelf, under the watch level."
    if why == "below_minimum":
        return (f"{group} is below the minimum of {words.units(view['minimum_stock'])} set by staff "
                f"({words.units(view['units_on_shelf'])} on the shelf).")
    if view["cover_days"] is None:
        return f"No {group} requests are expected in the next 14 days."
    return f"{group} is steady {before}."


def build(snap, index: int, view: dict) -> list[dict]:
    """Up to three reasons, most useful first. Each has an icon name and a sentence."""
    context, world = snap.context, snap.world
    row = world.panel.series.iloc[index]
    group = view["blood_group_words"]
    region, region_name = row["region"], row["region_name"]
    found: list[tuple[int, dict]] = []

    def add(priority: int, icon: str, text: str) -> None:
        found.append((priority, {"icon": icon, "text": text}))

    # 1. Shelf against expected use.
    if view["next_delivery"]:
        d = view["next_delivery"]
        use = float(snap.forecast.p50[:d["days_away"], index].sum())
        verb = "is expected to bring" if view.get("deliveries_from_supply_forecast") else "usually brings"
        today = (f", and today's delivery {verb} {words.units(view['arriving_today'])}"
                 if view["arriving_today"] >= 0.5 else "")
        add(1 if view["status"] != "steady" else 4, "shelf",
            f"{words.units(view['units_on_shelf'])} on the shelf{today}. Expected use before {d['label']} is "
            f"{words.units(use)}. " + (
                f"The delivery on {d['label']} is expected to bring {words.units(d['usual_units'])}."
                if view.get("deliveries_from_supply_forecast") else
                f"The usual delivery on {d['label']} brings {words.units(d['usual_units'])}."))

    # 2. Units expiring before the next delivery.
    if view["expiring_before_delivery"] >= 1 and view["next_delivery"]:
        add(2, "expiry", f"{words.units(round(view['expiring_before_delivery']))} "
                         f"{'expires' if round(view['expiring_before_delivery']) == 1 else 'expire'} "
                         f"before {view['next_delivery']['label']}.")

    # 3. Requests going up or down.
    last, prev = float(context["last4"][index]), float(context["prev4"][index])
    alerts = snap.settings["alerts"]
    if max(last, prev) >= alerts["trend_min_units"] and prev > 0:
        change = round(100 * (last / prev - 1))
        if abs(change) >= alerts["trend_min_change_pct"]:
            direction = "up" if change > 0 else "down"
            add(2 if change > 0 else 5, "trend",
                f"Requests for {group} are {direction} {abs(change)}% on the 4 weeks before "
                f"({words.units(last)} against {words.units(prev)}).")

    # 3b. Routine deliveries not keeping up with requests.
    delivered = float(context["routine28"].get((row["facility_id"], row["component"], row["blood_group"]), 0.0))
    if last >= alerts["trend_min_units"] and delivered < 0.6 * last:
        add(2 if view["status"] != "steady" else 4, "supply",
            f"Routine deliveries brought {words.units(delivered)} of {group} in the last 4 weeks, "
            f"against {words.units(last)} requested.")

    # 3c. What the regional centre is expected to clear this week.
    if snap.supply is not None and row["component"] == "RBC":
        from backend.engine import supply as supply_engine

        hist = supply_engine.history(world)
        c, g = hist.centres.index(region), hist.groups.index(row["blood_group"])
        ahead, usual = float(snap.supply.cleared[c, g, 0]), float(snap.supply.cleared_recent[c, g])
        what = f"{group} red cell units"
        if usual < alerts["trend_min_units"]:          # too few of this group to compare; use all groups
            ahead, usual = float(snap.supply.cleared[c, :, 0].sum()), float(snap.supply.cleared_recent[c].sum())
            what = "red cell units of all groups"
        if usual > 0:
            change = round(100 * (ahead / usual - 1))
            if abs(change) >= alerts["trend_min_change_pct"]:
                add(2 if change < 0 else 5, "supply_forecast",
                    f"From the drive schedule, the {region_name} centre should clear about {round(ahead)} {what} "
                    f"this week, {'down' if change < 0 else 'up'} {abs(change)}% on its 4-week average of {round(usual)}.")

    # 4. Requests recently not met.
    unmet = int(context["unmet14"][index])
    if unmet > 0:
        add(3, "unmet", f"{unmet} {'request' if unmet == 1 else 'requests'} for {group} "
                        f"{'was' if unmet == 1 else 'were'} not fully met here in the last 14 days.")

    # 5. School calendar and collections at the regional centre.
    school, effect = context["school"], context["break_effect"].get(region)
    tail = ""
    if effect and effect["change_pct"] < 0:
        tail = (f" Collections at the {region_name} centre fell {abs(effect['change_pct'])}% during the last "
                f"school break, the {effect['name']} ({effect['per_week_before']} a week down to {effect['per_week_during']}).")
    if school.get("in_break"):
        add(3, "school", f"Schools have been closed for {school['days_since_start']} days and reopen after "
                         f"{words.day(school['break_end'])}.{tail}")
    elif school.get("days_to_next", 999) <= alerts["school_notice_days"]:
        add(3, "school", f"Schools close in {school['days_to_next']} days.{tail}")

    # 6. What the regional centre holds.
    centre = context["centre_stock"].get((region, row["component"], row["blood_group"]))
    if centre is not None and view["status"] != "steady":
        add(4, "centre", f"The {region_name} centre held {words.units(centre)} of {group} "
                         f"{words.PRODUCT_WORDS[row['component']]} at the end of yesterday.")

    # 7. Staff minimum.
    if view["minimum_stock"] > 0 and view["units_on_shelf"] < view["minimum_stock"] and view["status_why"] != "below_minimum":
        add(3, "minimum", f"The shelf is below the minimum of {words.units(view['minimum_stock'])} set by staff.")

    found.sort(key=lambda item: item[0])
    return [reason for _, reason in found[:3]]
