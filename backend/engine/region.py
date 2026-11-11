"""The regional centre's view: supply for the next four weeks, the gap against
demand, and suggestions for extra drives. Everything is a suggestion; a person
accepts, changes or rejects it."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.engine import supply, words
from backend.engine.projection import Snapshot

def start_of(row: dict) -> str:
    return row["short_label"].replace("Week of ", "")


VENUE_WORDS = {
    "church": "churches", "mosque": "mosques", "corporate": "workplaces", "market_or_stage": "markets and bus stages",
    "community_event": "community events", "fixed_site_walk_in": "the fixed walk-in site",
    "secondary_school": "secondary schools", "university_college": "universities and colleges",
}


def regional_view(snap: Snapshot, centre: str, extra_drives: list[dict] | None = None) -> dict:
    world = snap.world
    hist = supply.history(world)
    made = supply.forecast(world, snap.as_of, extra_drives=extra_drives)
    c = hist.centres.index(centre)
    weeks = made.weeks
    starts = [snap.as_of + pd.Timedelta(days=7 * k) for k in range(weeks)]
    calendar = world.calendar.loc[centre]

    # Regional demand for red cells per group and week. The demand forecast covers two weeks;
    # weeks 3 and 4 use the average of those two (demand is nearly flat through the year).
    series = world.panel.series
    demand = np.zeros((len(hist.groups), weeks))
    for g, group in enumerate(hist.groups):
        cols = series.index[(series["region"] == centre) & (series["component"] == "RBC")
                            & (series["blood_group"] == group)].to_numpy()
        daily = snap.forecast.p50[:, cols].sum(axis=1)
        week1, week2 = daily[:7].sum(), daily[7:14].sum()
        demand[g] = [week1, week2, (week1 + week2) / 2, (week1 + week2) / 2][:weeks]

    # A simple balance per group: what the centre holds, plus what it clears, minus what its hospitals need.
    gap = np.zeros_like(demand)
    stock_end = np.zeros_like(demand)
    for g in range(len(hist.groups)):
        stock = float(made.centre_stock_now[c, g])
        for k in range(weeks):
            available = stock + made.cleared[c, g, k]
            gap[g, k] = max(0.0, demand[g, k] - available)
            stock = max(0.0, available - demand[g, k]) * (1 - float(made.loss_rate[c, g]))
            stock_end[g, k] = stock

    schedule = made.scheduled_drives[made.scheduled_drives["centre"] == centre]
    week_rows = []
    for k, start in enumerate(starts):
        end = start + pd.Timedelta(days=6)
        drives = schedule[(schedule["date"] >= start) & (schedule["date"] <= end)]
        in_break = bool((calendar.loc[start:end, "school_in_session"] == 0).mean() >= 0.5)
        week_rows.append({
            "week": k + 1, "start": str(start.date()), "label": f"{words.day(start)} to {words.day(end)}",
            "short_label": f"Week of {start.day} {start:%b}", "school_break": in_break,
            "expected_cleared": round(float(made.cleared[c, :, k].sum()), 0),
            "usual_cleared": round(float(made.cleared_recent[c].sum()), 0),
            "demand": round(float(demand[:, k].sum()), 0),
            "units_short": round(float(gap[:, k].sum()), 0),
            "scheduled_drives": int(len(drives)),
            "expected_donors": round(float(drives["expected_collected"].sum()), 0),
        })

    groups = [{
        "blood_group": group, "blood_group_label": words.group_symbol(group),
        "stock_now": int(made.centre_stock_now[c, g]),
        "weeks": [{"week": k + 1, "demand": round(float(demand[g, k]), 1), "cleared": round(float(made.cleared[c, g, k]), 1),
                   "short": round(float(gap[g, k]), 1), "stock_end": round(float(stock_end[g, k]), 1)} for k in range(weeks)],
    } for g, group in enumerate(hist.groups)]

    per_donation = float(made.rates["units_per_donation"].get(centre, 0.0))
    suggestions = []
    for k in range(1, weeks):                                    # 2 to 4 weeks out: time to organise a drive
        short = float(gap[:, k].sum())
        if short < 1 or per_donation <= 0:
            continue
        row = week_rows[k]
        table = made.rates["venue_yield_in_breaks" if row["school_break"] else "venue_yield_in_term"]
        venues = sorted([v for v in table if v["count"] >= 5 and v["venue_type"] in VENUE_WORDS],
                        key=lambda v: -v["mean"])[:3]
        donors = math.ceil(short / per_donation)
        worst = sorted(((gap[g, k], hist.groups[g]) for g in range(len(hist.groups)) if gap[g, k] >= 0.5), reverse=True)[:3]
        when = "during school breaks" if row["school_break"] else "in term time"
        venue_text = ", ".join(f"{VENUE_WORDS[v['venue_type']]} ({v['mean']:.0f} a drive)" for v in venues)
        suggestions.append({
            "id": f"{centre}|DRIVE|{row['start']}", "as_of": str(snap.as_of.date()), "week": k + 1,
            "week_label": row["label"], "school_break": row["school_break"],
            "groups_short": [words.group_symbol(g) for _, g in worst],
            "text": f"About {words.units(round(short))} of red cells short in the week of {row['label']}"
                    + (f", mostly {', '.join(words.group_words(g) for _, g in worst)}." if worst else "."),
            "venue_text": f"Venues that have yielded most {when}: {venue_text}." if venues else "",
            # A draft only. No donor data is held and nothing is sent; a person must approve and send it.
            "call_out_draft": (f"{world.facility.at[centre, 'region_name']} blood centre: we need "
                               + (" and ".join(words.group_words(g) for _, g in worst[:2]) if worst else "all groups of")
                               + f" blood in the week of {start_of(row)}. One donation can help up to three patients. "
                               "Please come to your nearest drive. Reply STOP to opt out.")[:300],
            "venues": [{"venue_type": v["venue_type"], "label": VENUE_WORDS[v["venue_type"]],
                        "per_drive": round(v["mean"], 0)} for v in venues],
            "suggestion": {
                "kind": "drive", "title": f"Add collections in the week of {row['label']}",
                "needs_approval": "This is a suggestion for the drive planner. Nothing is booked and no donor is contacted.",
                "quantity": donors, "usual_quantity": 0, "unit_word": "donors",
                "for_date": row["start"], "for_label": row["short_label"],
                "parts": [{"label": "Usable red cell units short that week", "units": round(short, 0)}],
                "sum_text": f"{round(short)} units ÷ {per_donation:.2f} usable units per donation = {donors} donors",
            },
        })

    from backend.engine import allocation as fair
    proposal = fair.propose(snap, centre, made.shipped[c, :, 0], made.received[:, :, 0], hist.hospitals, hist.groups)

    # Platelets: turn the regional platelet forecast into apheresis donors to book (an assumption-based hint).
    apheresis = None
    if bool(world.facility.at[centre, "makes_platelets"]):
        from backend import config as _config

        per_donation = _config.load_settings("thresholds")["apheresis"]["whole_blood_units_per_apheresis_donation"]
        cols = series.index[(series["region"] == centre) & (series["component"] == "PLT")].to_numpy()
        daily_mid = snap.forecast.p50[:7, cols].sum(axis=1)
        daily_busy = snap.forecast.p90[:7, cols].sum(axis=1)
        apheresis = {
            "units_per_donation": per_donation,
            "week_units": round(float(daily_mid.sum()), 1), "week_units_busy": round(float(daily_busy.sum()), 1),
            "days": [{"label": words.day(snap.dates[t]), "units": round(float(daily_mid[t]), 1),
                      "donors": int(math.ceil(daily_mid[t] / per_donation - 1e-9)),
                      "donors_busy": int(math.ceil(daily_busy[t] / per_donation - 1e-9))} for t in range(7)],
            "week_donors": int(math.ceil(daily_mid.sum() / per_donation - 1e-9)),
            "week_donors_busy": int(math.ceil(daily_busy.sum() / per_donation - 1e-9)),
            "note": f"Based on about {per_donation} whole-blood-derived platelet units per apheresis donation, which staff can "
                    "change in the settings. Platelets last 5 days, so they are collected to order.",
        }

    total_expected, total_usual = sum(w["expected_cleared"] for w in week_rows), sum(w["usual_cleared"] for w in week_rows)
    change = round(100 * (total_expected / total_usual - 1)) if total_usual else 0
    return {
        "centre": {"facility_id": centre, "name": world.facility.at[centre, "name"],
                   "region_name": world.facility.at[centre, "region_name"]},
        "weeks": week_rows, "groups": groups, "drive_suggestions": suggestions, "allocation": proposal, "apheresis": apheresis,
        "supply_change_pct": change,
        "rates": {"units_per_donation": round(per_donation, 2),
                  "median_testing_wait_days": made.rates["median_testing_wait_days"]},
        "what_if": extra_drives or [],
        "notes": ["Scheduled drives for the next 4 weeks are counted. Emergency appeals are never counted as planned supply.",
                  "Demand for weeks 3 and 4 is the average of weeks 1 and 2, because demand is steady through the year.",
                  "The balance covers the centre's own stock and what it clears."],
    }
