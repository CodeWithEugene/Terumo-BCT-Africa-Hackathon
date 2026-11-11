"""Text messages through Africa's Talking.

Three jobs:
1. `alert_text` builds the staff alert on the server, from the same words the Brief page previews.
2. `reply_to` answers a staff member who texts us (the incoming-message callback).
3. `send_alert` sends the alert to a hospital's registered staff phones after a signed-in officer approves it.

Rules from docs/SMS_HANDOVER.md that this file keeps: the text is always rebuilt here (never taken from the
browser), a person approves every send, phone numbers are not stored (they come from SP_STAFF_PHONES), at most
160 characters, and a gateway failure only says "not sent". Donor call-outs are not sent from here.
"""
from __future__ import annotations

from backend.api import at_gateway as gateway
from backend.api import service
from backend.api.auth import User, require_facility, scope
from backend.api.ussd import identify, short, world_names
from backend.engine import words
from backend.engine.projection import morning_list

HELP = "Providus SMS. Text ALERT, COVER O-, ORDERS or HOSPITALS. Add a hospital name to look one up, e.g. ALERT Thika."


def alert_text(facility_id: str, component: str = "RBC") -> str | None:
    snap = service.snapshot(None)
    views = morning_list(snap, facility_id, component)
    if not any(v["held"] for v in views):
        return None
    name = service.facility_card(facility_id)["name"]
    return service.sms_preview(name, f"{words.day(snap.as_of)} {snap.as_of.year}", views)


def _find_hospital(user: User | None, query: str, default: str | None) -> tuple[str | None, str | None]:
    """Pick a hospital by name. Returns (facility_id, problem)."""
    names = world_names()
    allowed = scope(user) if user is not None else [f for f in names.index if f.startswith("HSP-")]
    if not query:
        return (default, None) if default else (None, "Add a hospital name, e.g. ALERT Thika.")
    hits = [f for f in allowed if query.lower() in names[f].lower()]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, "No hospital matches that name."
    return None, "Be more specific: " + ", ".join(short(names[f])[:14] for f in hits[:4]) + "."


def reply_to(phone: str, text: str) -> str:
    """The reply to one incoming text. Always under 160 characters."""
    caller = identify(phone)
    if caller is None:
        return "This number is not registered for Providus."
    words_in = text.strip().split()
    command = words_in[0].upper() if words_in else "HELP"
    rest = " ".join(words_in[1:])
    home = caller.user.facility_id if caller.user and caller.user.role == "hospital_officer" else None
    try:
        if command in ("ALERT", "BRIEF", "STATUS"):
            facility, problem = _find_hospital(caller.user, rest, home)
            return problem or alert_text(facility) or "That hospital does not hold red cells."
        if command == "COVER":
            group = next((w.upper() for w in words_in[1:] if w.upper().replace("POS", "+").replace("NEG", "-")
                          in ("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-")), None)
            group = group.replace("POS", "+").replace("NEG", "-") if group else None
            if not group:
                return "Text COVER and a group, e.g. COVER O- or COVER A+ Thika."
            name_part = " ".join(w for w in words_in[1:] if w.upper() != group.upper())
            facility, problem = _find_hospital(caller.user, name_part, home)
            if problem:
                return problem
            return _cover_text(facility, group)
        if command == "ORDERS":
            facility, problem = _find_hospital(caller.user, rest, home)
            return problem or _orders_text(facility)
        if command == "HOSPITALS":
            return _hospitals_text(caller.user)
    except Exception:  # noqa: BLE001
        return "Providus is not available right now. Try again soon."
    return HELP[:160]


def _cover_text(facility: str, group: str) -> str:
    snap = service.snapshot(None)
    view = next((v for v in morning_list(snap, facility, "RBC") if v["blood_group"] == group), None)
    if view is None or not view["held"]:
        return f"{short(world_names()[facility])[:20]} does not hold {group} red cells."
    cover = "no use" if view["cover_days"] is None else ("14+ days" if view.get("cover_capped")
                                                          else words.days(view["cover_days"]))
    text = f"{short(world_names()[facility])[:18]} {view['blood_group_label']}: {view['status_label']}. {view['units_on_shelf']} units, cover {cover}."
    if view.get("next_delivery"):
        text += f" Next delivery {view['next_delivery']['label']}."
    return text[:160]


def _orders_text(facility: str) -> str:
    snap = service.snapshot(None)
    views = [v for v in morning_list(snap, facility, "RBC") if v["held"] and v.get("suggestion")
             and v["suggestion"]["quantity"] and v["status"] in ("act", "watch")]
    if not views:
        return "No order is suggested today."
    items = ", ".join(f"{v['blood_group_label']} {v['suggestion']['quantity']}" for v in views)
    return f"Suggested units: {items}. Open the app to accept or change."[:160]


def _hospitals_text(user: User | None) -> str:
    snap = service.snapshot(None)
    names = world_names()
    allowed = scope(user) if user is not None else [f for f in names.index if f.startswith("HSP-")]
    flagged = []
    for facility in allowed:
        views = [v for v in morning_list(snap, facility, "RBC") if v["held"]]
        act = sum(v["status"] == "act" for v in views)
        if act:
            flagged.append((act, short(names[facility])[:14]))
    flagged.sort(reverse=True)
    if not flagged:
        return "No hospital needs action today."
    return ("Act today: " + ", ".join(f"{n} {a}" for a, n in flagged[:6]))[:160]


def send_alert(user: User, facility_id: str) -> dict:
    """Send the alert to this hospital's registered staff phones. The caller has already approved it."""
    require_facility(user, facility_id)
    text = alert_text(facility_id)
    if text is None:
        return {"sent": False, "text": None, "note": "This hospital does not hold red cells."}
    phones = [p for p, name in gateway.staff_phones().items() if _may_receive(name, facility_id)]
    if not phones:
        result = {"sent": 0, "ok": False, "note": "No staff phone is registered for this hospital."}
    else:
        result = gateway.send_sms(phones, text)
    service.audit(user, "sms_alert_sent" if result["ok"] else "sms_alert_not_sent", facility_id=facility_id,
                  decided={"text": text, "recipients": len(phones), "sent": result["sent"]}, note=result["note"])
    return {"sent": result["ok"], "text": text, "recipients": len(phones), "note": result["note"]}


def _may_receive(username: str, facility_id: str) -> bool:
    from backend.api.auth import find_user

    row = find_user(username=username)
    if row is None:
        return False
    staff = User(row["user_id"], row["username"], row["display_name"], row["role"], row["facility_id"])
    return facility_id in scope(staff)
