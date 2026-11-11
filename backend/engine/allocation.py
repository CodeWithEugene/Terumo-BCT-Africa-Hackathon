"""Fair-share allocation of red cells, and a replay that tests it on past data.

The finding behind it: on most days a hospital ran short of a blood group,
another hospital in the same region held spare units of that group. The blood
was enough; it was on the wrong shelf.

The rule: when a regional centre sends out units of a blood group, give each
unit to the hospital that would otherwise have the fewest days of cover
(units on the shelf divided by its average daily requests). Hospitals with no
requests for that group get none. Only hospitals with a delivery scheduled
that weekday can receive, so the delivery rounds stay as they are.

The replay: take the period of the forecast tests. Keep the same requests and
the same units leaving each centre on the same days. Walk every hospital shelf
forward twice: once sending each unit where it really went, once using the
rule. Emergency deliveries are left out of both runs, so the comparison is
"how much demand could a hospital's own shelf not meet". The rule only ever
sees days before the day it is deciding. Nothing was tuned on this period.

This is a proposal tool. Moving blood needs authorisation; a person approves.

Run from the repo root:   python -m backend.engine.allocation
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from backend import config
from backend.engine import words
from backend.engine.projection import build_snapshot
from backend.engine.world import World, get_world

RED = ("RBC", "WB")
POLICIES = {"actual": "As it happened", "fair": "Fair share"}


def fair_share(units: int, shelf: np.ndarray, daily: np.ndarray, eligible: np.ndarray,
               protected_days: np.ndarray | None = None) -> np.ndarray:
    """Split `units` whole units so the lowest days of cover is raised first.

    `protected_days` (optional, per hospital) is a staff-set minimum: those
    hospitals are brought up to that many days of cover before anything is shared.
    """
    give = np.zeros(len(shelf), dtype=int)
    can = eligible & (daily > 0)
    if units <= 0 or not can.any():
        return give
    cover = np.where(can, shelf / np.where(daily > 0, daily, 1.0), np.inf)
    step = np.where(can, 1.0 / np.where(daily > 0, daily, 1.0), 0.0)
    units = int(units)
    if protected_days is not None:
        while units > 0:
            below = can & (cover < protected_days)
            if not below.any():
                break
            h = int(np.argmin(np.where(below, cover, np.inf)))
            give[h] += 1
            cover[h] += step[h]
            units -= 1
    for _ in range(int(units)):
        h = int(np.argmin(cover))
        give[h] += 1
        cover[h] += step[h]
    return give


def _walk(shelves: list[list[int]], arrivals: list[list[int]], demand: np.ndarray, day: int) -> tuple[np.ndarray, np.ndarray]:
    """One day for one blood group at every hospital of a region: arrive, issue oldest first, expire."""
    short = np.zeros(len(shelves))
    expired = np.zeros(len(shelves))
    for h, shelf in enumerate(shelves):
        if arrivals[h]:
            shelf.extend(arrivals[h])
            shelf.sort()
        need = int(demand[h])
        used = min(need, len(shelf))
        del shelf[:used]
        short[h] = need - used
        keep = [e for e in shelf if e > day]
        expired[h] = len(shelf) - len(keep)
        shelves[h] = keep
    return short, expired


def replay(db_path: Path | None = None) -> pd.DataFrame:
    """Scores for both policies, for every hospital and overall."""
    world = get_world(db_path)
    settings = config.load_settings("thresholds")["allocation"]
    start = pd.Timestamp(str(settings["replay_first_day"]))
    end = world.last_date
    panel, groups = world.panel, config.load_settings("blood")["blood_groups"]
    snap = build_snapshot(world, start, "baseline", use_supply=False)
    n_days = (end - start).days + 1
    cut = panel.position(start)

    # Routine red cell units that reached a hospital in the period, with their real expiry dates.
    moves = world.unit_move[(world.unit_move["transfer_type"] == "routine")
                            & world.unit_move["to_facility_id"].str.startswith("HSP")]
    moves = moves.assign(day=(moves["at"].dt.normalize() - start).dt.days)
    moves = moves[(moves["day"] >= 0) & (moves["day"] < n_days)]
    units = world.unit[world.unit["component"].isin(RED)][["unit_id", "blood_group", "expiry_date"]]
    moves = moves.merge(units, on="unit_id")
    moves["expiry_day"] = (moves["expiry_date"] - start).dt.days
    by_key = {key: frame for key, frame in moves.groupby(["blood_group", "day"])}

    series = panel.series
    rows = []
    for region, hospitals in world.facility[world.facility["kind"] == "hospital"].groupby("region"):
        names = list(hospitals.index)
        position = {h: i for i, h in enumerate(names)}
        delivery_days = [snap.delivery_days.get(h, set()) for h in names]
        for group in groups:
            cols = [int(series.index[(series["facility_id"] == h) & (series["component"] == "RBC")
                                     & (series["blood_group"] == group)][0]) for h in names]
            requested = panel.requested[:, cols]
            start_shelf = [sorted(int(d) for d, n in snap.cohorts.get((h, "RBC", group), []) for _ in range(int(round(n))))
                           for h in names]
            shelves = {policy: [list(s) for s in start_shelf] for policy in POLICIES}
            totals = {policy: {"short": np.zeros(len(names)), "expired": np.zeros(len(names)),
                               "days": np.zeros(len(names))} for policy in POLICIES}
            for day in range(n_days):
                frame = by_key.get((group, day))
                frame = frame[frame["to_facility_id"].isin(position)] if frame is not None else None
                demand = requested[cut + day]
                arrive = {policy: [[] for _ in names] for policy in POLICIES}
                if frame is not None and len(frame):
                    for h, e in zip(frame["to_facility_id"], frame["expiry_day"]):
                        arrive["actual"][position[h]].append(int(e))
                    # Fair share: same units, same day. Need is known only from earlier days.
                    daily = requested[cut + day - settings["demand_days"]:cut + day].mean(axis=0)
                    weekday = (start + pd.Timedelta(days=day)).weekday()
                    eligible = np.array([weekday in d for d in delivery_days])
                    shelf_now = np.array([len(s) for s in shelves["fair"]], dtype=float)
                    give = fair_share(len(frame), shelf_now, daily, eligible)
                    if give.sum() == 0:                       # nobody eligible: leave the units where they went
                        arrive["fair"] = [list(a) for a in arrive["actual"]]
                    else:
                        expiries = sorted(int(e) for e in frame["expiry_day"])
                        for h in np.argsort(-daily):          # the busiest shelves take the oldest units
                            arrive["fair"][h] = expiries[:give[h]]
                            expiries = expiries[give[h]:]
                for policy in POLICIES:
                    short, expired = _walk(shelves[policy], arrive[policy], demand, day)
                    totals[policy]["short"] += short
                    totals[policy]["expired"] += expired
                    totals[policy]["days"] += short > 0
            asked = requested[cut:cut + n_days].sum(axis=0)
            for policy in POLICIES:
                for i, h in enumerate(names):
                    rows.append({"policy": policy, "facility_id": h, "blood_group": group,
                                 "units_requested": float(asked[i]), "units_short": float(totals[policy]["short"][i]),
                                 "shortage_days": float(totals[policy]["days"][i]),
                                 "units_expired": float(totals[policy]["expired"][i])})
    detail = pd.DataFrame(rows)
    by_hospital = detail.groupby(["policy", "facility_id"], as_index=False)[
        ["units_requested", "units_short", "shortage_days", "units_expired"]].sum()
    overall = by_hospital.groupby("policy", as_index=False)[
        ["units_requested", "units_short", "shortage_days", "units_expired"]].sum()
    overall["facility_id"] = "ALL"
    out = pd.concat([overall, by_hospital], ignore_index=True)
    out["short_pct"] = 100 * out["units_short"] / out["units_requested"].where(out["units_requested"] > 0)
    out["first_day"], out["last_day"] = str(start.date()), str(end.date())
    return out


def spare_elsewhere(world: World) -> dict:
    """How often a hospital ran short while another hospital in its region held spare units."""
    settings = config.load_settings("thresholds")["allocation"]
    hospitals = world.facility[world.facility["kind"] == "hospital"]
    stock = world.stock[world.stock["component"].isin(RED) & world.stock["facility_id"].isin(hospitals.index)]
    stock = stock.groupby(["date", "facility_id", "blood_group"], as_index=False)["units"].sum()
    demand = pd.DataFrame({"facility_id": np.repeat(world.panel.series["facility_id"].to_numpy(), 1)})
    series = world.panel.series
    red = series[series["component"] == "RBC"]
    daily = pd.Series(world.panel.requested[:, red.index].mean(axis=0), index=pd.MultiIndex.from_frame(
        red[["facility_id", "blood_group"]]))
    stock["own_use"] = [daily.get((f, g), 0.0) for f, g in zip(stock["facility_id"], stock["blood_group"])]
    stock["spare"] = (stock["units"] - settings["spare_cover_days"] * stock["own_use"]).clip(lower=0)
    stock["region"] = stock["facility_id"].map(hospitals["region"])
    stock["date"] = stock["date"] + pd.Timedelta(days=1)                  # the shelf at the start of the day
    region = stock.groupby(["region", "blood_group", "date"], as_index=False)["spare"].sum()
    short_rows = []
    for i in red.index:
        days = np.nonzero(world.panel.shortage[:, i] > 0)[0]
        for d in days:
            short_rows.append((red.at[i, "facility_id"], red.at[i, "blood_group"], world.panel.dates[d]))
    short = pd.DataFrame(short_rows, columns=["facility_id", "blood_group", "date"])
    short["region"] = short["facility_id"].map(hospitals["region"])
    short = short.merge(region, on=["region", "blood_group", "date"], how="left")
    short = short.merge(stock[["facility_id", "blood_group", "date", "spare"]].rename(columns={"spare": "own_spare"}),
                        on=["facility_id", "blood_group", "date"], how="left").fillna(0.0)
    elsewhere = short["spare"] - short["own_spare"]
    del demand
    # How the replay's "as it happened" run compares with the real records for the same period.
    start = pd.Timestamp(str(settings["replay_first_day"]))
    from backend.db.core import read as _read

    real = _read("SELECT SUM(units_requested) r, SUM(units_from_local_stock) l FROM demand_daily "
                 "WHERE component = 'RBC' AND blood_group <> 'unknown' AND date >= ?", (str(start.date()),)).iloc[0]
    return {"shortage_days": int(len(short)), "with_spare_elsewhere_pct": round(100 * float((elsewhere >= 2).mean()), 1),
            "spare_cover_days": settings["spare_cover_days"],
            "real_not_from_shelf_pct": round(100 * float(1 - real["l"] / real["r"]), 1)}


def run(db_path: Path | None = None, write_docs: bool = True, verbose: bool = True) -> pd.DataFrame:
    world = get_world(db_path)
    scores = replay(db_path)
    fact = spare_elsewhere(world)
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        scores.to_sql("allocation_replay", conn, if_exists="replace", index=False)
        pd.DataFrame([{"key": k, "value": str(v)} for k, v in fact.items()]).to_sql(
            "allocation_fact", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()
    from backend.engine.results import write_results

    write_results(db_path, write_docs=write_docs)
    if verbose:
        print("\n".join(results_section(db_path)))
    return scores


def results_section(db_path: Path | None = None) -> list[str]:
    from backend.db.core import read

    scores = read("SELECT * FROM allocation_replay", path=db_path)
    fact = read("SELECT key, value FROM allocation_fact", path=db_path).set_index("key")["value"]
    names = read("SELECT facility_id, name FROM facility", path=db_path).set_index("facility_id")["name"]
    overall = scores[scores["facility_id"] == "ALL"].set_index("policy")
    a, f = overall.loc["actual"], overall.loc["fair"]
    change = lambda key: f"{100 * (f[key] - a[key]) / a[key]:+.0f}%" if a[key] else "n/a"
    lines = [
        "## Fair-share allocation (red cells): a replay with the same blood",
        "",
        f"**The finding.** On {fact['with_spare_elsewhere_pct']}% of the {int(fact['shortage_days']):,} days a hospital ran "
        f"short of a blood group, other hospitals in the same region together held at least 2 spare units of that group "
        f"(spare = beyond {fact['spare_cover_days']} days of their own average use).",
        "",
        f"**The test.** {a['first_day']} to {a['last_day']}. Same requests, same units leaving each regional centre on the "
        "same days, same delivery rounds. Each hospital shelf is walked forward twice: sending every unit where it really "
        "went, and giving each unit to the hospital with the fewest days of cover. Emergency deliveries are left out of "
        "both runs. The rule sees only earlier days and nothing was tuned on this period.",
        "",
        "| | As it happened | Fair share | Change |",
        "| --- | --- | --- | --- |",
        f"| Units a hospital's own shelf could not supply | {a['units_short']:,.0f} | {f['units_short']:,.0f} | {change('units_short')} |",
        f"| As a share of units requested | {a['short_pct']:.1f}% | {f['short_pct']:.1f}% | |",
        f"| Hospital-group-days with a shortfall | {a['shortage_days']:,.0f} | {f['shortage_days']:,.0f} | {change('shortage_days')} |",
        f"| Units expired on hospital shelves | {a['units_expired']:,.0f} | {f['units_expired']:,.0f} | {change('units_expired')} |",
        "",
        f"**Is the replay realistic?** In the real records for this period, {fact.get('real_not_from_shelf_pct', 'n/a')}% of requested "
        f"red cell units did not come from the hospital's own shelf. The replay's \"as it happened\" run gives "
        f"{a['short_pct']:.1f}%.",
        "",
        "**Who gains and who loses.** The gain is not free. Hospitals that were starved gain most; the best-stocked "
        "hospitals, including the national referral hospital, lose cover. A real rule would protect a minimum for "
        "referral hospitals. We did not add that here, because it would mean tuning on the test period.",
        "",
        "### By hospital (share of requested units the shelf could not supply)",
        "",
        "| Hospital | Units requested | As it happened | Fair share |",
        "| --- | --- | --- | --- |",
    ]
    wide = scores[scores["facility_id"] != "ALL"].pivot(index="facility_id", columns="policy", values="short_pct")
    asked = scores[(scores["facility_id"] != "ALL") & (scores["policy"] == "actual")].set_index("facility_id")["units_requested"]
    for facility in wide.sort_values("actual", ascending=False).index:
        lines.append(f"| {names[facility]} | {asked[facility]:,.0f} | {wide.at[facility, 'actual']:.1f}% | {wide.at[facility, 'fair']:.1f}% |")
    lines += ["", "Limits: a replay is a model of the shelves, not the real world. It assumes units can be re-split within "
              "a delivery day, ignores vehicle capacity, and takes the centre's total output as given.", ""]
    return lines


def propose(snap, centre: str, shipped_week: np.ndarray, usual: np.ndarray, hospitals: list[str], groups: list[str]) -> dict:
    """This week's expected units from the centre, split the usual way and the fair-share way."""
    world = snap.world
    series = world.panel.series
    mine = [h for h in hospitals if world.facility.at[h, "region"] == centre]
    index = [hospitals.index(h) for h in mine]
    fair = np.zeros((len(mine), len(groups)))
    usual_units = usual[index]                                             # (hospitals, groups)
    shelf = np.zeros((len(mine), len(groups)))
    daily = np.zeros((len(mine), len(groups)))
    settings = config.load_settings("thresholds")["allocation"]
    kinds = set(settings.get("protected_facility_types", []))
    floor_days = float(settings.get("protected_cover_days", 0) or 0)
    protected = np.array([floor_days if world.facility.at[h, "facility_type"] in kinds else 0.0 for h in mine])
    protected_names = [world.facility.at[h, "name"] for h in mine
                       if floor_days > 0 and world.facility.at[h, "facility_type"] in kinds]
    for g, group in enumerate(groups):
        cols = [int(series.index[(series["facility_id"] == h) & (series["component"] == "RBC")
                                 & (series["blood_group"] == group)][0]) for h in mine]
        daily[:, g] = snap.forecast.p50[:7, cols].mean(axis=0)
        shelf[:, g] = [snap.shelf.get((h, "RBC", group), 0.0) for h in mine]
        fair[:, g] = fair_share(int(round(float(shipped_week[g]))), shelf[:, g], daily[:, g],
                                np.ones(len(mine), dtype=bool), protected)
    rows = []
    for i, h in enumerate(mine):
        use = float(daily[i].sum())
        cover = lambda extra: round((float(shelf[i].sum()) + extra) / use, 1) if use > 0 else None
        rows.append({"facility_id": h, "name": world.facility.at[h, "name"],
                     "on_shelf": int(shelf[i].sum()), "weekly_use": round(use * 7, 1),
                     "cover_now": cover(0.0), "usual_units": round(float(usual_units[i].sum()), 0),
                     "fair_units": int(fair[i].sum()), "cover_usual": cover(float(usual_units[i].sum())),
                     "cover_fair": cover(float(fair[i].sum())),
                     "change": int(fair[i].sum() - round(float(usual_units[i].sum())))})
    rows.sort(key=lambda r: -r["change"])
    moved = int(sum(r["change"] for r in rows if r["change"] > 0))
    gain = [r["name"] for r in rows if r["change"] > 0][:3]
    total = int(fair.sum())
    covers_usual = [r["cover_usual"] for r in rows if r["cover_usual"] is not None]
    covers_fair = [r["cover_fair"] for r in rows if r["cover_fair"] is not None]
    return {
        "id": f"{centre}|ALLOC|{snap.as_of.date()}", "as_of": str(snap.as_of.date()), "rows": rows,
        "total_units": total, "units_moved": moved,
        "protected": {"days": floor_days, "hospitals": protected_names} if protected_names else None,
        "lowest_cover_usual": min(covers_usual) if covers_usual else None,
        "lowest_cover_fair": min(covers_fair) if covers_fair else None,
        "text": (f"About {words.units(total)} of red cells should leave the centre this week. Sharing them by days of cover "
                 f"sends {words.units(moved)} to a different hospital than usual"
                 + (f", mostly to {', '.join(gain)}." if gain else ".")),
        "suggestion": {
            "kind": "allocation", "title": "Share this week's red cells by days of cover",
            "needs_approval": "This is a proposal for the distribution plan. Moving blood needs authorisation, "
                              "and no unit moves until a person approves it.",
            "quantity": moved, "usual_quantity": 0, "unit_word": "units re-routed",
            "for_date": str(snap.as_of.date()), "for_label": "this week",
            "parts": [{"label": "Units expected to leave the centre this week", "units": total}],
            "sum_text": f"{moved} of {total} units go to a different hospital than the usual split",
        },
    }


if __name__ == "__main__":
    run()
