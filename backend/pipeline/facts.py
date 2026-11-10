"""Compute the headline facts from the built database and write docs/DATA_FACTS.md.

Every number in the README, the pitch and the landing page comes from here.
The facts are also saved in the ``data_fact`` table so the app can show them.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from backend import config

RED_CELL_STOCK = ("RBC", "WB")


def _q(conn: sqlite3.Connection, sql: str, **kw) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, **kw)


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _md_table(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([head, rule, *rows])


def compute_facts(db_path: Path | None = None) -> tuple[dict[str, float | str], dict[str, pd.DataFrame]]:
    """Return (single numbers, small tables)."""
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        facts: dict[str, float | str] = {}
        tables: dict[str, pd.DataFrame] = {}
        groups = config.load_settings("blood")["blood_groups"]

        demand = _q(conn, "SELECT * FROM demand_daily", parse_dates=["date"])
        facility = _q(conn, "SELECT * FROM facility")
        hospitals = facility[facility["kind"] == "hospital"]
        first, last = demand["date"].min(), demand["date"].max()
        n_days = (last - first).days + 1
        facts["first_date"] = str(first.date())
        facts["last_date"] = str(last.date())
        facts["hospitals"] = int(len(hospitals))

        # --- Requests and fill rate -------------------------------------------------
        requests = int(demand["requests"].sum())
        asked = int(demand["units_requested"].sum())
        issued = int(demand["units_issued"].sum())
        facts["requests"] = requests
        facts["units_requested"] = asked
        facts["units_issued"] = issued
        facts["requests_not_fully_met_pct"] = _pct(demand["requests_not_fully_met"].sum(), requests)
        facts["unit_fill_rate_pct"] = _pct(issued, asked)
        facts["unmet_units"] = asked - issued

        by_component = demand.groupby("component").agg(
            requests=("requests", "sum"), units_requested=("units_requested", "sum"),
            unmet_units=("unmet_units", "sum"), local=("units_from_local_stock", "sum"),
            issued=("units_issued", "sum")).reset_index()
        by_component["unmet %"] = [_pct(u, r) for u, r in zip(by_component.unmet_units, by_component.units_requested)]
        by_component["issued from own shelf %"] = [_pct(l, i) for l, i in zip(by_component.local, by_component.issued)]
        tables["by_component"] = by_component.drop(columns=["local", "issued"])

        by_group = demand.groupby("blood_group").agg(
            units_requested=("units_requested", "sum"), unmet_units=("unmet_units", "sum")).reindex(
                groups + ["unknown"]).reset_index()
        by_group["unmet %"] = [_pct(u, r) for u, r in zip(by_group.unmet_units, by_group.units_requested)]
        tables["by_group"] = by_group
        for row in by_group.itertuples():
            facts[f"unmet_pct_{row.blood_group}"] = row._4

        monthly = demand.assign(month=demand["date"].dt.strftime("%Y-%m")).groupby("month").agg(
            units_requested=("units_requested", "sum"), unmet_units=("unmet_units", "sum")).reset_index()
        monthly["unmet %"] = [_pct(u, r) for u, r in zip(monthly.unmet_units, monthly.units_requested)]
        tables["by_month"] = monthly

        # --- Stock-outs: red cells (red cell units plus whole blood) at hospitals ---
        stock = _q(conn, "SELECT date, facility_id, blood_group, SUM(units) AS units FROM stock_daily "
                         "WHERE component IN ('RBC','WB') AND facility_id LIKE 'HSP-%' "
                         "GROUP BY date, facility_id, blood_group", parse_dates=["date"])
        grid = pd.MultiIndex.from_product(
            [sorted(hospitals["facility_id"]), groups, pd.date_range(first, last)],
            names=["facility_id", "blood_group", "date"])
        shelf = stock.set_index(["facility_id", "blood_group", "date"])["units"].reindex(grid, fill_value=0)
        red = demand[(demand["component"] == "RBC") & (demand["blood_group"] != "unknown")]
        unmet_days = (red[red["requests_not_fully_met"] > 0]
                      .groupby(["facility_id", "blood_group"])["date"].nunique())
        empty = (shelf == 0)
        facts["red_cell_empty_shelf_days_pct"] = _pct(empty.sum(), len(empty))

        g = pd.DataFrame({
            "empty-shelf days %": (empty.groupby("blood_group").mean() * 100).round(1),
            "days with an unmet request (all hospitals)": unmet_days.groupby("blood_group").sum(),
        }).reindex(groups).fillna(0).reset_index()
        g["days with an unmet request (all hospitals)"] = g["days with an unmet request (all hospitals)"].astype(int)
        tables["stockout_by_group"] = g

        f = pd.DataFrame({
            "empty-shelf days % (average of 8 groups)": (empty.groupby("facility_id").mean() * 100).round(1),
            "group-days with an unmet red cell request": unmet_days.groupby("facility_id").sum(),
        }).fillna(0).reset_index()
        f["group-days with an unmet red cell request"] = f["group-days with an unmet red cell request"].astype(int)
        f = f.merge(hospitals[["facility_id", "name", "facility_type"]], on="facility_id")
        f = f[["facility_id", "name", "facility_type", "empty-shelf days % (average of 8 groups)",
               "group-days with an unmet red cell request"]].sort_values(
                   "group-days with an unmet red cell request", ascending=False)
        tables["stockout_by_facility"] = f
        facts["red_cell_unmet_group_days"] = int(unmet_days.sum())

        # --- Wastage ----------------------------------------------------------------
        unit = _q(conn, "SELECT component, status, COUNT(*) AS units, SUM(temp_excursion_exposed) AS exposed "
                        "FROM unit GROUP BY component, status")
        wide = unit.pivot(index="component", columns="status", values="units").fillna(0).astype(int)
        wide["all units"] = wide.sum(axis=1)
        wide["wasted"] = wide.get("expired", 0) + wide.get("discarded_temperature", 0)
        wide["wasted %"] = [_pct(w, a) for w, a in zip(wide["wasted"], wide["all units"])]
        tables["wastage"] = wide.reset_index()
        red_rows = wide.loc[list(RED_CELL_STOCK)]
        facts["red_cell_wastage_pct"] = _pct(red_rows["wasted"].sum(), red_rows["all units"].sum())
        facts["red_cell_expired_units"] = int(red_rows["expired"].sum())
        facts["red_cell_discarded_warm_units"] = int(red_rows["discarded_temperature"].sum())
        facts["exposed_units_transfused"] = int(
            unit.loc[unit["status"] == "transfused", "exposed"].sum())

        # --- Emergency resupply -----------------------------------------------------
        emergency = _q(conn, "SELECT e.hours, f.region_name FROM emergency_resupply e "
                             "JOIN facility f ON f.facility_id = e.facility_id")
        facts["emergency_resupplies"] = int(len(emergency))
        facts["emergency_median_hours"] = round(float(emergency["hours"].median()), 1)
        facts["emergency_p90_hours"] = round(float(emergency["hours"].quantile(0.9)), 1)
        by_region = emergency.groupby("region_name")["hours"].agg(["count", "median"]).round(1).reset_index()
        by_region.columns = ["region", "emergency resupplies", "median hours"]
        tables["emergency_by_region"] = by_region

        # --- How sparse is demand? --------------------------------------------------
        series = (demand[demand["blood_group"] != "unknown"]
                  .groupby(["facility_id", "component", "blood_group"])
                  .agg(days_with_demand=("date", "nunique"), units=("units_requested", "sum")).reset_index())
        series["zero_share"] = 1 - series["days_with_demand"] / n_days
        series["per_week"] = series["units"] / (n_days / 7)
        facts["demand_series"] = int(len(series))
        facts["zero_demand_days_median_pct"] = round(float(series["zero_share"].median() * 100), 1)
        facts["series_under_one_unit_a_week_pct"] = _pct((series["per_week"] < 1).sum(), len(series))
        sparse = series.groupby("component").agg(
            series=("units", "size"), zero_days=("zero_share", "median"), per_week=("per_week", "median")).reset_index()
        sparse["median share of days with no request %"] = (sparse.pop("zero_days") * 100).round(1)
        sparse["median units a week"] = sparse.pop("per_week").round(2)
        tables["sparsity"] = sparse

        # --- Whole blood and red cell requests --------------------------------------
        issued_for_red = _q(conn, "SELECT component, COUNT(*) AS units FROM unit "
                                  "WHERE issued_for_component = 'RBC' GROUP BY component")
        total_red = int(issued_for_red["units"].sum())
        whole = int(issued_for_red.loc[issued_for_red["component"] == "WB", "units"].sum())
        facts["red_cell_requests_filled_by_whole_blood_pct"] = _pct(whole, total_red)
        facts["units_issued_for_red_cell_requests"] = total_red
        wb_region = _q(conn, "SELECT f.region_name AS region, "
                             "SUM(u.component='WB') AS whole_blood, COUNT(*) AS all_units "
                             "FROM unit u JOIN facility f ON f.facility_id = u.processed_at_id "
                             "WHERE u.issued_for_component = 'RBC' GROUP BY f.region_name")
        wb_region["whole blood %"] = [_pct(w, a) for w, a in zip(wb_region.whole_blood, wb_region.all_units)]
        tables["whole_blood_by_region"] = wb_region

        # --- Collections and school breaks ------------------------------------------
        drive = _q(conn, "SELECT date, venue_type, donations_collected FROM drive WHERE date >= ?",
                   params=(facts["first_date"],), parse_dates=["date"])
        cal = _q(conn, "SELECT DISTINCT date, school_in_session FROM calendar", parse_dates=["date"])
        cal = cal[(cal["date"] >= first) & (cal["date"] <= last)]
        drive = drive.merge(cal, on="date")
        days_in = int(cal["school_in_session"].sum())
        days_out = int(len(cal) - days_in)
        per_week = drive.groupby(["venue_type", "school_in_session"])["donations_collected"].sum().unstack(fill_value=0)
        venue = pd.DataFrame({
            "venue type": per_week.index,
            "collected a week, term time": (per_week[1] / days_in * 7).round(0).astype(int).values,
            "collected a week, school breaks": (per_week[0] / days_out * 7).round(0).astype(int).values,
        })
        tables["collections_by_venue"] = venue
        term_week = per_week[1].sum() / days_in * 7
        break_week = per_week[0].sum() / days_out * 7
        facts["collections_per_week_term"] = int(round(term_week))
        facts["collections_per_week_break"] = int(round(break_week))
        facts["collections_drop_in_breaks_pct"] = round(100 * (1 - break_week / term_week), 1)
        schools = drive[drive["venue_type"].isin(["secondary_school", "university_college"])]
        facts["collections_from_schools_and_universities_pct"] = _pct(
            schools["donations_collected"].sum(), drive["donations_collected"].sum())

        supply = _q(conn, "SELECT SUM(attempts) a, SUM(collected) c, SUM(deferred) d, SUM(reactive) r, "
                          "SUM(cleared_donations) ok FROM supply_daily WHERE date >= ?",
                    params=(facts["first_date"],)).iloc[0]
        facts["donation_attempts"] = int(supply["a"])
        facts["deferred_pct"] = _pct(supply["d"], supply["a"])
        facts["reactive_pct_of_tested"] = _pct(supply["r"], supply["r"] + supply["ok"])

        # --- Data quality notes -----------------------------------------------------
        moves = _q(conn, "SELECT COUNT(*) n, SUM(confirmed = 0) u FROM unit_move").iloc[0]
        facts["transfers_not_confirmed_pct"] = _pct(moves["u"], moves["n"])
        note = _q(conn, "SELECT value FROM pipeline_note WHERE key='temperature_glitches_dropped'")
        facts["temperature_glitches_dropped"] = int(note["value"].iloc[0])
        unknown = demand.loc[demand["blood_group"] == "unknown", "requests"].sum()
        facts["requests_with_unknown_group"] = int(unknown)
        return facts, tables
    finally:
        conn.close()


def render(facts: dict, tables: dict[str, pd.DataFrame]) -> str:
    f = facts
    lines = [
        "# Data facts",
        "",
        "Written by `python -m backend.pipeline.build`. Do not edit by hand.",
        "All data is the organisers' **synthetic** starter dataset. These numbers describe the model "
        "dataset, not any real hospital or blood centre.",
        "",
        f"Period: {f['first_date']} to {f['last_date']}. {f['hospitals']} hospitals.",
        "",
        "## Headline numbers",
        "",
        f"- **{f['requests']:,} requests for {f['units_requested']:,} units.** "
        f"{f['requests_not_fully_met_pct']}% of requests were not fully met. "
        f"{f['unit_fill_rate_pct']}% of requested units were issued ({f['unmet_units']:,} units short).",
        f"- **O negative patients fare worst:** {f['unmet_pct_O-']}% of O negative units requested were not "
        f"issued, against {f['unmet_pct_O+']}% for O positive.",
        f"- **Wastage:** {f['red_cell_wastage_pct']}% of red cell and whole blood units were wasted "
        f"({f['red_cell_expired_units']:,} expired, {f['red_cell_discarded_warm_units']:,} discarded after a "
        "fridge or cool box went out of range).",
        f"- **Emergency resupply:** {f['emergency_resupplies']:,} requests needed an emergency delivery. "
        f"Median time from request to last unit at the bedside: {f['emergency_median_hours']} hours "
        f"(1 in 10 took more than {f['emergency_p90_hours']} hours).",
        f"- **Empty shelves are common:** across hospitals and the 8 groups, the red cell shelf "
        f"(red cells plus whole blood) was empty at the end of {f['red_cell_empty_shelf_days_pct']}% of days. "
        f"There were {f['red_cell_unmet_group_days']:,} hospital-group-days with a red cell request that was not fully met.",
        f"- **School breaks:** collections averaged {f['collections_per_week_term']:,} a week in term time and "
        f"{f['collections_per_week_break']:,} a week in school breaks "
        f"({f['collections_drop_in_breaks_pct']}% lower). "
        f"{f['collections_from_schools_and_universities_pct']}% of all collections came from secondary school "
        "and university drives.",
        f"- **Demand is sparse:** {f['demand_series']} hospital, component and group series had any request. "
        f"The median series had no request on {f['zero_demand_days_median_pct']}% of days, and "
        f"{f['series_under_one_unit_a_week_pct']}% of series ask for less than one unit a week.",
        f"- **Whole blood fills red cell requests:** {f['red_cell_requests_filled_by_whole_blood_pct']}% of the "
        f"{f['units_issued_for_red_cell_requests']:,} units issued for red cell requests were whole blood. "
        "We therefore count red cells and whole blood together as red cell cover.",
        f"- **Not flagged:** {f['exposed_units_transfused']:,} units were transfused after being in a fridge or "
        "cool box that went out of range.",
        "",
        "## Requests by component", "", _md_table(tables["by_component"]), "",
        "Hospitals in this dataset hold no platelets, so every platelet request waits for a delivery.", "",
        "## Unmet units by blood group", "", _md_table(tables["by_group"]), "",
        "## Unmet units by month", "", _md_table(tables["by_month"]), "",
        "## Red cell stock-outs by blood group (hospitals)", "",
        "\"Empty shelf\" counts red cells plus whole blood. A group a hospital never holds counts as empty.", "",
        _md_table(tables["stockout_by_group"]), "",
        "## Red cell stock-outs by hospital", "", _md_table(tables["stockout_by_facility"]), "",
        "## Wastage by component", "",
        "Share of all units made in the period (units still in stock at the end are in the total).", "",
        _md_table(tables["wastage"]), "",
        "## Emergency resupply time by region", "", _md_table(tables["emergency_by_region"]), "",
        "## How sparse demand is", "", _md_table(tables["sparsity"]), "",
        "## Whole blood issued for red cell requests, by processing centre", "",
        _md_table(tables["whole_blood_by_region"]), "",
        "## Collections by venue type, term time against school breaks", "",
        "School break dates are in `config/calendar_ke.yaml`.", "",
        _md_table(tables["collections_by_venue"]), "",
        "## Supply and data quality", "",
        f"- {f['donation_attempts']:,} donation attempts in the period; {f['deferred_pct']}% deferred; "
        f"{f['reactive_pct_of_tested']}% of tested donations reactive and discarded.",
        f"- {f['transfers_not_confirmed_pct']}% of transfers have no arrival time (kept, marked \"not confirmed arrived\").",
        f"- {f['temperature_glitches_dropped']} fridge readings were sensor faults and were dropped.",
        f"- {f['requests_with_unknown_group']} requests record the patient group as unknown. They count in "
        "hospital totals and are left out of per-group forecasts.",
        "- Join key is always `facility_id`. The typed facility name is never read.",
        "- The donor table is not in this repo and is never loaded.",
        "",
    ]
    return "\n".join(lines)


def write_data_facts(db_path: Path | None = None, out_path: Path | None = None,
                     write_docs: bool = True) -> str:
    facts, tables = compute_facts(db_path)
    text = render(facts, tables)
    if write_docs:
        (out_path or config.DOCS_DIR / "DATA_FACTS.md").write_text(text, encoding="utf-8", newline="\n")
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        pd.DataFrame([{"key": k, "value": str(v)} for k, v in facts.items()]).to_sql(
            "data_fact", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()
    return text
