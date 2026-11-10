"""What the API endpoints do, kept apart from the web layer."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import HTTPException

from backend import config
from backend.api.auth import User, require_facility, scope
from backend.db.app_tables import get_setting
from backend.db.core import read, session, table_exists
from backend.engine import baseline, forecasting, models, words
from backend.engine.brief import summary_sentence
from backend.engine.projection import Snapshot, build_snapshot, morning_list, series_view
from backend.engine.world import get_world


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def model_choice() -> str:
    """ "baseline" when staff have switched the model off, otherwise "auto"."""
    return baseline.NAME if get_setting("force_baseline", "0") == "1" else "auto"


@lru_cache(maxsize=16)
def _snapshot(as_of: str, choice: str, stamp: float) -> Snapshot:
    return build_snapshot(get_world(), as_of, choice)


def snapshot(as_of: str | None, choice: str | None = None) -> Snapshot:
    as_of = as_of or str(config.load_settings("site")["default_as_of"])
    allowed = {str(d["date"]) for d in config.load_settings("site")["as_of_dates"]}
    if as_of not in allowed:
        raise HTTPException(status_code=400, detail="Choose one of the prepared dates.")
    return _snapshot(as_of, choice or model_choice(), config.DB_PATH.stat().st_mtime)


def mode_info(snap: Snapshot | None = None) -> dict:
    """The block added to every response so the app can always show the mode."""
    forced = get_setting("force_baseline", "0") == "1"
    available = forecasting.PREFERRED in models.REGISTRY
    if snap is not None:
        mode, model, note = snap.forecast.mode, snap.forecast.model, snap.forecast.note
    else:
        mode = "fallback" if forced or not available else "model"
        model = baseline.NAME if mode == "fallback" else forecasting.PREFERRED
        note = "Using the forecast model." if mode == "model" else "Fallback: using the 4-week average."
    if forced:
        note = "Fallback: using the 4-week average (switched on by staff)."
    return {"mode": mode, "model": model, "mode_note": note, "fallback_forced": forced,
            "model_available": available}


def as_of_dates() -> dict:
    site = config.load_settings("site")
    return {"default": str(site["default_as_of"]),
            "dates": [{"date": str(d["date"]), "label": f"{words.day(d['date'])} {pd.Timestamp(d['date']).year}",
                       "note": d["note"]} for d in site["as_of_dates"]]}


def facility_card(facility_id: str) -> dict:
    row = get_world().facility.loc[facility_id]
    return {"facility_id": facility_id, "name": row["name"], "facility_type": row["facility_type"],
            "county": row["county"], "region_name": row["region_name"], "connectivity": row["connectivity"]}


def user_card(user: User) -> dict:
    world = get_world()
    home = world.facility.loc[user.facility_id]
    return {"username": user.username, "display_name": user.display_name, "role": user.role,
            "role_label": user.role_label, "facility_id": user.facility_id, "facility_name": home["name"],
            "facilities": [facility_card(f) for f in scope(user)]}


def _decisions_for(as_of: str, facility_id: str) -> dict[str, dict]:
    rows = read("SELECT * FROM decision WHERE as_of = ? AND facility_id = ? AND withdrawn_at IS NULL "
                "ORDER BY decision_id", (as_of, facility_id))
    return {row["series_id"]: _decision_card(row) for row in rows.to_dict("records")}


def _decision_card(row: dict) -> dict:
    at = pd.Timestamp(row["created_at"])
    verb = {"accept": "Accepted", "change": "Changed", "reject": "Rejected"}[row["action"]]
    row = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in row.items()}
    row["summary"] = f"{verb} by {row['display_name']}, {at:%H:%M}"
    row["at_label"] = f"{words.day(at)} {at:%H:%M}"
    row["blood_group_label"] = "All groups" if row["blood_group"] == "all" else words.group_symbol(row["blood_group"])
    return row


def brief(user: User, as_of: str | None, facility_id: str | None, component: str) -> dict:
    facility_id = require_facility(user, facility_id)
    snap = snapshot(as_of)
    views = morning_list(snap, facility_id, component)
    decisions = _decisions_for(str(snap.as_of.date()), facility_id)
    for view in views:
        view["decision"] = decisions.get(view["id"])
    held = [v for v in views if v["held"]]
    deliveries = sorted({v["next_delivery"]["date"] for v in held if v.get("next_delivery")})
    products = config.load_settings("blood")["products"]
    return {
        **mode_info(snap),
        "as_of": str(snap.as_of.date()), "as_of_label": f"{words.day(snap.as_of)} {snap.as_of.year}",
        "facility": facility_card(facility_id),
        "component": component, "component_label": products[component]["label"],
        "components": [{"component": c, "label": spec["label"], "held": (facility_id, c) in snap.held}
                       for c, spec in products.items()],
        "sentence": summary_sentence(views),
        "next_delivery_label": words.day(deliveries[0]) if deliveries else None,
        "counts": {s: sum(v["status"] == s for v in views) for s in ("act", "watch", "steady", "not_held")},
        "series": views,
    }


def overview(user: User, as_of: str | None, component: str) -> dict:
    """Every hospital the user may see, with the status of each blood group."""
    snap = snapshot(as_of)
    rows = []
    for facility_id in scope(user):
        views = morning_list(snap, facility_id, component)
        order = {g: n for n, g in enumerate(config.load_settings("blood")["blood_groups"])}
        cells = sorted(views, key=lambda v: order[v["blood_group"]])
        rows.append({
            **facility_card(facility_id),
            "act": sum(v["status"] == "act" for v in views), "watch": sum(v["status"] == "watch" for v in views),
            "next_delivery_label": next((v["next_delivery"]["label"] for v in views
                                         if v.get("next_delivery")), None),
            "groups": [{"id": v["id"], "blood_group": v["blood_group"], "blood_group_label": v["blood_group_label"],
                        "status": v["status"], "status_label": v["status_label"], "cover_days": v["cover_days"],
                        "cover_capped": v.get("cover_capped", False), "units_on_shelf": v["units_on_shelf"]}
                       for v in cells],
        })
    rows.sort(key=lambda r: (-r["act"], -r["watch"], r["name"]))
    return {**mode_info(snap), "as_of": str(snap.as_of.date()), "component": component, "facilities": rows}


def _series_index(series_id: str) -> int:
    series = get_world().panel.series
    match = series.index[series["series_id"] == series_id]
    if len(match) == 0:
        raise HTTPException(status_code=404, detail="That series does not exist.")
    return int(match[0])


def what_happened(snap: Snapshot, index: int) -> dict:
    """The real outcome for the projected days. The forecast never sees this."""
    world = snap.world
    row = world.panel.series.iloc[index]
    cut = world.panel.position(snap.as_of)
    stock = world.stock[(world.stock["facility_id"] == row["facility_id"]) & (world.stock["product"] == row["component"])
                        & (world.stock["blood_group"] == row["blood_group"]) & (world.stock["date"] >= snap.as_of)]
    shelf = stock.groupby("date")["units"].sum()
    days = []
    for t, date in enumerate(snap.dates):
        if cut + t >= len(world.panel.dates):
            break
        days.append({"date": str(date.date()), "label": words.day(date),
                     "requested": float(world.panel.requested[cut + t, index]),
                     "requests_not_fully_met": int(world.panel.unmet[cut + t, index]),
                     "shortage_requests": int(world.panel.shortage[cut + t, index]),
                     "stock": float(shelf.get(date, 0.0))})
    unmet_days = [d["label"] for d in days if d["shortage_requests"] > 0]
    if unmet_days:
        text = ("A request was not fully met, or needed an emergency delivery, on "
                + ", ".join(unmet_days[:4]) + ("." if len(unmet_days) <= 4 else " and later."))
    else:
        text = "Every request in these days was filled from the hospital's own shelf."
    return {"note": "What really happened next. Hidden from the forecast; shown so you can check it.",
            "summary": text, "days": days}


def series_detail(user: User, series_id: str, as_of: str | None) -> dict:
    index = _series_index(series_id)
    facility_id = get_world().panel.series.at[index, "facility_id"]
    require_facility(user, facility_id)
    snap = snapshot(as_of)
    view = series_view(snap, index, detail=True)
    view["decision"] = _decisions_for(str(snap.as_of.date()), facility_id).get(series_id)
    view["actual"] = what_happened(snap, index)
    view["forecast_compare"] = _both_forecasts(snap, index)
    view["facility"] = facility_card(facility_id)
    view["action_label"] = ("Request approval" if user.role == "regional_officer"
                            or (view.get("suggestion") or {}).get("kind") == "early_delivery" else "Accept")
    return {**mode_info(snap), "series": view}


def _both_forecasts(snap: Snapshot, index: int) -> dict:
    """Expected use over the next 7 days under the baseline and under the model."""
    simple = baseline.forecast(snap.world.panel, snap.as_of, snap.horizon)
    out = {"baseline_7_days": round(float(simple["p50"][:7, index].sum()), 1), "model_7_days": None}
    if snap.forecast.mode == "model":
        out["model_7_days"] = round(float(snap.forecast.p50[:7, index].sum()), 1)
    return out


def region(user: User, as_of: str | None, extra_donors: int | None = None, extra_date: str | None = None) -> dict:
    """The regional officer's supply view. Hospital officers have no access."""
    from backend.engine.region import regional_view

    if user.role != "regional_officer":
        raise HTTPException(status_code=403, detail="This view is for regional centre officers.")
    snap = snapshot(as_of)
    extra = None
    if extra_donors and extra_date:
        date = pd.Timestamp(extra_date)
        if not (snap.as_of <= date < snap.as_of + pd.Timedelta(days=28)) or not (1 <= extra_donors <= 2000):
            raise HTTPException(status_code=422, detail="Choose a date in the next 4 weeks and 1 to 2,000 donors.")
        extra = [{"date": str(date.date()), "centre": user.facility_id, "donors": int(extra_donors)}]
    view = regional_view(snap, user.facility_id, extra)
    open_decisions = _decisions_for(str(snap.as_of.date()), user.facility_id)
    for item in view["drive_suggestions"]:
        item["decision"] = open_decisions.get(item["id"])
        item["action_label"] = "Request approval"
    return {**mode_info(snap), "as_of": str(snap.as_of.date()), **view}


def _record_drive_decision(user: User, body: dict) -> dict:
    from backend.engine.region import regional_view

    access = config.load_settings("access")
    action = body["action"]
    centre = body["series_id"].split("|")[0]
    if user.role != "regional_officer" or centre != user.facility_id:
        raise HTTPException(status_code=403, detail="You do not have access to that centre.")
    snap = snapshot(body.get("as_of"))
    item = next((s for s in regional_view(snap, centre)["drive_suggestions"] if s["id"] == body["series_id"]), None)
    if item is None:
        raise HTTPException(status_code=400, detail="There is no drive suggestion for that week.")
    suggestion = item["suggestion"]
    if action in ("change", "reject"):
        if body.get("reason_code") not in {r["code"] for r in access["reason_codes"][action]}:
            raise HTTPException(status_code=422, detail="Please choose a reason.")
        if body["reason_code"] == "other" and not (body.get("note") or "").strip():
            raise HTTPException(status_code=422, detail="Please add a note to explain \"Other\".")
    quantity = suggestion["quantity"] if action == "accept" else 0 if action == "reject" else body.get("quantity")
    if quantity is None or (action == "change" and quantity == suggestion["quantity"]):
        raise HTTPException(status_code=422, detail="Enter a different number of donors, or use Accept.")
    as_of = str(snap.as_of.date())
    note = (body.get("note") or "").strip() or None
    with session() as conn:
        if conn.execute("SELECT 1 FROM decision WHERE as_of = ? AND series_id = ? AND withdrawn_at IS NULL",
                        (as_of, item["id"])).fetchone():
            raise HTTPException(status_code=409, detail="A decision is already recorded for this week.")
        cursor = conn.execute(
            "INSERT INTO decision (created_at, user_id, username, display_name, role, as_of, series_id, facility_id, "
            "component, blood_group, suggestion_kind, for_date, status_seen, suggested_quantity, action, "
            "final_quantity, reason_code, note, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now(), user.user_id, user.username, user.display_name, user.role, as_of, item["id"], centre, "RBC", "all",
             "drive", suggestion["for_date"], "watch", suggestion["quantity"], action, int(quantity),
             body.get("reason_code"), note, snap.forecast.mode))
        decision_id = cursor.lastrowid
        _audit(conn, user, "decision", facility_id=centre, series_id=item["id"], as_of=as_of,
               saw={"text": item["text"], "venues": item["venue_text"], "suggested_quantity": suggestion["quantity"],
                    "sum": suggestion["sum_text"], "suggestion_kind": "drive", "mode": snap.forecast.mode},
               decided={"action": action, "final_quantity": int(quantity), "decision_id": decision_id,
                        "is_request_for_approval": True},
               reason_code=body.get("reason_code"), note=note)
        saved = dict(conn.execute("SELECT * FROM decision WHERE decision_id = ?", (decision_id,)).fetchone())
    return {**mode_info(snap), "decision": _decision_card(saved), "undo_seconds": access["undo_seconds"]}


def record_decision(user: User, body: dict) -> dict:
    if "|DRIVE|" in body["series_id"]:
        return _record_drive_decision(user, body)
    access = config.load_settings("access")
    action = body["action"]
    index = _series_index(body["series_id"])
    row = get_world().panel.series.iloc[index]
    require_facility(user, row["facility_id"])
    snap = snapshot(body.get("as_of"))
    view = series_view(snap, index, detail=False)
    suggestion = view.get("suggestion")
    if not view["held"] or suggestion is None:
        raise HTTPException(status_code=400, detail="There is no suggestion to decide on for this group.")
    if action in ("change", "reject"):
        codes = {r["code"] for r in access["reason_codes"][action]}
        if body.get("reason_code") not in codes:
            raise HTTPException(status_code=422, detail="Please choose a reason.")
        if body["reason_code"] == "other" and not (body.get("note") or "").strip():
            raise HTTPException(status_code=422, detail="Please add a note to explain \"Other\".")
    if action == "accept":
        quantity = suggestion["quantity"]
    elif action == "reject":
        quantity = 0
    else:
        quantity = body.get("quantity")
        if quantity is None or quantity < 0 or quantity > 500:
            raise HTTPException(status_code=422, detail="Enter a quantity between 0 and 500 units.")
        if quantity == suggestion["quantity"]:
            raise HTTPException(status_code=422, detail="That is the suggested quantity. Use Accept instead.")
    as_of = str(snap.as_of.date())
    saw = {"status": view["status"], "status_line": view["status_line"], "units_on_shelf": view["units_on_shelf"],
           "cover_days": view["cover_days"], "suggestion_kind": suggestion["kind"],
           "suggested_quantity": suggestion["quantity"], "sum": suggestion["sum_text"],
           "forecast_model": snap.forecast.model, "mode": snap.forecast.mode,
           **_both_forecasts(snap, index), "reasons": [r["text"] for r in view["reasons"]]}
    decided = {"action": action, "final_quantity": int(quantity),
               "is_request_for_approval": user.role == "regional_officer" or suggestion["kind"] == "early_delivery"}
    with session() as conn:
        open_one = conn.execute("SELECT decision_id FROM decision WHERE as_of = ? AND series_id = ? "
                                "AND withdrawn_at IS NULL", (as_of, view["id"])).fetchone()
        if open_one:
            raise HTTPException(status_code=409, detail="A decision is already recorded for this group today.")
        cursor = conn.execute(
            "INSERT INTO decision (created_at, user_id, username, display_name, role, as_of, series_id, facility_id, "
            "component, blood_group, suggestion_kind, for_date, status_seen, suggested_quantity, action, "
            "final_quantity, reason_code, note, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now(), user.user_id, user.username, user.display_name, user.role, as_of, view["id"], row["facility_id"],
             row["component"], row["blood_group"], suggestion["kind"], suggestion["for_date"], view["status"],
             suggestion["quantity"], action, int(quantity), body.get("reason_code"),
             (body.get("note") or "").strip() or None, snap.forecast.mode))
        decision_id = cursor.lastrowid
        _audit(conn, user, "decision", facility_id=row["facility_id"], series_id=view["id"], as_of=as_of,
               saw=saw, decided={**decided, "decision_id": decision_id},
               reason_code=body.get("reason_code"), note=(body.get("note") or "").strip() or None)
        saved = dict(conn.execute("SELECT * FROM decision WHERE decision_id = ?", (decision_id,)).fetchone())
    return {**mode_info(snap), "decision": _decision_card(saved),
            "undo_seconds": access["undo_seconds"]}


def undo_decision(user: User, decision_id: int) -> dict:
    """Withdraw a decision just made. The audit log keeps both the decision and the withdrawal."""
    seconds = config.load_settings("access")["undo_seconds"]
    with session() as conn:
        row = conn.execute("SELECT * FROM decision WHERE decision_id = ?", (decision_id,)).fetchone()
        if row is None or row["user_id"] != user.user_id:
            raise HTTPException(status_code=404, detail="That decision was not found.")
        if row["withdrawn_at"] is not None:
            raise HTTPException(status_code=409, detail="That decision was already undone.")
        if datetime.now() - datetime.fromisoformat(row["created_at"]) > timedelta(seconds=seconds + 5):
            raise HTTPException(status_code=409, detail="The undo window has passed. Record a new decision instead.")
        conn.execute("UPDATE decision SET withdrawn_at = ? WHERE decision_id = ?", (now(), decision_id))
        _audit(conn, user, "decision_withdrawn", facility_id=row["facility_id"], series_id=row["series_id"],
               as_of=row["as_of"], decided={"decision_id": decision_id})
    return {**mode_info(), "undone": True}


def _audit(conn, user: User | None, event: str, *, facility_id=None, series_id=None, as_of=None,
           saw=None, decided=None, reason_code=None, note=None) -> None:
    conn.execute(
        "INSERT INTO audit_log (at, user_id, username, role, event, facility_id, series_id, as_of, saw, decided, "
        "reason_code, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (now(), user.user_id if user else None, user.username if user else None, user.role if user else None,
         event, facility_id, series_id, as_of, json.dumps(saw) if saw is not None else None,
         json.dumps(decided) if decided is not None else None, reason_code, note))


def audit(user: User | None, event: str, **fields) -> None:
    with session() as conn:
        _audit(conn, user, event, **fields)


def list_decisions(user: User, facility_id: str | None, action: str | None) -> dict:
    allowed = scope(user)
    if user.role == "regional_officer":
        allowed = allowed + [user.facility_id]            # their own centre's drive decisions
    if facility_id is not None:
        allowed = [facility_id if facility_id in allowed else require_facility(user, facility_id)]
    marks = ",".join("?" for _ in allowed)
    sql = f"SELECT * FROM decision WHERE facility_id IN ({marks})"
    params: list = list(allowed)
    if action:
        sql += " AND action = ?"
        params.append(action)
    rows = read(sql + " ORDER BY decision_id DESC LIMIT 500", tuple(params)).to_dict("records")
    names = get_world().facility["name"]
    labels = {r["code"]: r["label"] for kind in config.load_settings("access")["reason_codes"].values() for r in kind}
    items = []
    for row in rows:
        card = _decision_card(row)
        card["facility_name"] = names[row["facility_id"]]
        card["reason_label"] = labels.get(row["reason_code"]) if row["reason_code"] else None
        card["withdrawn"] = card["withdrawn_at"] is not None
        items.append(card)
    return {**mode_info(), "decisions": items}


def audit_entries(user: User, limit: int = 200) -> dict:
    """The raw audit trail for the user's hospitals (and their own sign-ins)."""
    allowed = scope(user) + ([user.facility_id] if user.role == "regional_officer" else [])
    marks = ",".join("?" for _ in allowed)
    rows = read(f"SELECT * FROM audit_log WHERE facility_id IN ({marks}) OR (facility_id IS NULL AND user_id = ?) "
                "ORDER BY audit_id DESC LIMIT ?", (*allowed, user.user_id, limit)).to_dict("records")
    for row in rows:
        for key in ("saw", "decided"):
            row[key] = json.loads(row[key]) if isinstance(row[key], str) else None
        for key, value in list(row.items()):
            if isinstance(value, float) and np.isnan(value):
                row[key] = None
    return {**mode_info(), "entries": rows}


def accuracy() -> dict:
    out: dict = {**mode_info(), "forecast": [], "alerts": [], "models": [], "test_period": None}
    if not table_exists("backtest_metric"):
        return out
    settings = config.load_settings("thresholds")
    out["test_period"] = {"first": str(settings["backtest"]["first_origin"]),
                          "last": str(settings["backtest"]["last_origin"]),
                          "horizon_days": settings["forecast"]["horizon_days"]}
    out["models"] = [{"name": name, "label": getattr(module, "LABEL", name)}
                     for name, module in models.REGISTRY.items()]
    metrics = read("SELECT * FROM backtest_metric")
    out["forecast"] = json.loads(metrics.to_json(orient="records"))
    if table_exists("alert_metric"):
        out["alerts"] = json.loads(read("SELECT * FROM alert_metric").to_json(orient="records"))
        out["alert_rule_cover_days"] = settings["alerts"]["baseline_rule_cover_days"]
    out["supply"] = json.loads(read("SELECT * FROM supply_metric").to_json(orient="records")) \
        if table_exists("supply_metric") else []
    out["rare_note"] = dict(read("SELECT key, value FROM model_note").to_numpy()) if table_exists("model_note") else None
    return out
