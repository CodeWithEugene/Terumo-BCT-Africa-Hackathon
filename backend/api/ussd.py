"""The USSD menu for *384*11400#. A phone with no data connection can read the morning brief.

How Africa's Talking USSD works (the part that shapes this file):
- Every key press is a new HTTP POST to one callback. The server keeps no screen state for us.
  `text` holds everything the user has typed in this session joined by `*`, for example `2*1*3`.
- Our reply is plain text. It must start with `CON ` (keep the session open) or `END ` (close it).
- A screen should stay under about 180 characters, and the whole reply must come back within a few seconds.

So this file rebuilds the screen from the typed path each time. `0` goes back one step and `00` goes home.

Who sees what:
- A phone listed in SP_STAFF_PHONES is a signed-in officer. It sees its own hospital (or, for a regional centre
  officer, the hospitals the centre supplies) and may accept a suggested order, which is logged like any other decision.
- Any other phone gets a view-only look-up when SP_USSD_OPEN is on (the demo setting). It cannot record anything.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend import config
from backend.api import at_gateway as gateway
from backend.api import service
from backend.api.auth import User, find_user, scope
from backend.db.core import read
from backend.engine import words
from backend.engine.brief import summary_sentence
from backend.engine.projection import morning_list
from backend.engine.world import get_world

PAGE = 5
SCREEN_LIMIT = 182
MORE = "98"


@dataclass
class Caller:
    phone: str
    user: User | None          # set for staff phones
    open_demo: bool = False    # a view-only visitor

    @property
    def can_decide(self) -> bool:
        return self.user is not None


def identify(phone: str) -> Caller | None:
    username = gateway.staff_phones().get(gateway.normalise(phone))
    if username:
        row = find_user(username=username)
        if row is not None:
            return Caller(phone, User(row["user_id"], row["username"], row["display_name"], row["role"],
                                      row["facility_id"]))
    return Caller(phone, None, open_demo=True) if gateway.open_lookup() else None


# --- Replies -------------------------------------------------------------------------

def con(text: str) -> str:
    return "CON " + _fit(text)


def end(text: str) -> str:
    return "END " + _fit(text)


def _fit(text: str) -> str:
    return text if len(text) <= SCREEN_LIMIT else text[:SCREEN_LIMIT - 1].rstrip() + "…"


def short(name: str) -> str:
    for cut in (" County Referral Hospital", " Teaching and Referral Hospital", " Level 5 Hospital",
                " Sub-County Hospital", " County Hospital", " Referral Hospital", " Mission Hospital",
                " Private Hospital", " Hospital"):
        name = name.replace(cut, "")
    return name


# --- Reading the typed path --------------------------------------------------------------

def steps(text: str) -> list[str]:
    """Turn `1*2*0*3` into the path the user is really on: `0` goes back one step, `00` goes home."""
    path: list[str] = []
    for token in text.split("*") if text else []:
        token = token.strip()
        if token == "00":
            path.clear()
        elif token == "0":
            if path:
                path.pop()
        elif token:
            path.append(token)
    return path


def pick(options: list, path: list[str], title: str, line) -> tuple[str, object, list[str]]:
    """Show a numbered, paged list and read the choice.

    Returns ("screen", reply, []) to show, ("chosen", option, rest_of_path) once a choice is made,
    or ("bad", reply, []) when the key pressed is not on the screen.
    """
    page, rest = 0, list(path)
    while rest and rest[0] == MORE:
        page += 1
        rest.pop(0)
    last = max(0, (len(options) - 1) // PAGE)
    page = min(page, last)
    shown = options[page * PAGE:(page + 1) * PAGE]
    if not rest:
        lines = [title] + [f"{n}. {line(o)}" for n, o in enumerate(shown, 1)]
        if page < last:
            lines.append(f"{MORE}. More")
        lines.append("0. Back")
        return "screen", con("\n".join(lines)), []
    if rest[0].isdigit() and 1 <= int(rest[0]) <= len(shown):
        return "chosen", shown[int(rest[0]) - 1], rest[1:]
    return "bad", con("That choice is not on the screen.\n0. Back"), []


# --- The menu ----------------------------------------------------------------------------

def handle(phone: str, text: str) -> str:
    """The whole USSD conversation. Always returns a CON or END string, even when something goes wrong."""
    try:
        caller = identify(phone)
        if caller is None:
            return end("This number is not registered for Providus. Ask your blood bank lead to add it.")
        return _route(caller, steps(text))
    except Exception:  # noqa: BLE001  (a menu must never show a stack trace to a phone)
        return end("Providus is not available right now. Please try again, or open the app.")


def _route(caller: Caller, path: list[str]) -> str:
    world = get_world()
    user = caller.user
    if user is not None and user.role == "hospital_officer":
        return _hospital(caller, user.facility_id, path)

    hospitals = scope(user) if user is not None else sorted(world.facility[world.facility["kind"] == "hospital"].index)
    if user is not None and not path:
        return con(f"Providus {short(world.facility.at[user.facility_id, 'name'])}\n1. Hospitals needing action\n"
                   "2. Choose a hospital")
    if user is None:
        return _choose_hospital(caller, hospitals, path)
    if path[0] == "1":
        return _needing_action(caller, hospitals, path[1:])
    if path[0] == "2":
        return _choose_hospital(caller, hospitals, path[1:])
    return con("That choice is not on the screen.\n0. Back")


def _choose_hospital(caller: Caller, hospitals: list[str], path: list[str]) -> str:
    names = world_names()
    kind, value, rest = pick(hospitals, path, "Choose a hospital" if caller.user else "Providus (demo, view only)\nChoose a hospital",
                             lambda f: short(names[f])[:26])
    return _hospital(caller, value, rest) if kind == "chosen" else value


def _needing_action(caller: Caller, hospitals: list[str], path: list[str]) -> str:
    snap = service.snapshot(None)
    names = world_names()
    flagged = []
    for facility in hospitals:
        views = [v for v in morning_list(snap, facility, "RBC") if v["held"]]
        act = sum(v["status"] == "act" for v in views)
        watch = sum(v["status"] == "watch" for v in views)
        if act or watch:
            flagged.append((facility, act, watch))
    if not flagged:
        return con("No hospital needs action or watching today.\n0. Back")
    flagged.sort(key=lambda r: (-r[1], -r[2]))
    kind, value, rest = pick(flagged, path, "Needing action (Act/Watch)",
                             lambda r: f"{short(names[r[0]])[:18]} {r[1]}A {r[2]}W")
    return _hospital(caller, value[0], rest) if kind == "chosen" else value


def world_names():
    return get_world().facility["name"]


# --- One hospital ----------------------------------------------------------------------------

def _hospital(caller: Caller, facility: str, path: list[str]) -> str:
    name = short(world_names()[facility])
    if not path:
        return con(f"{name[:30]}\n1. Today's alert\n2. Cover by blood group\n3. Suggested orders\n4. Text me the alert\n0. Back")
    first, rest = path[0], path[1:]
    if first == "1":
        return _alert(facility, rest)
    if first == "2":
        return _cover(facility, rest)
    if first == "3":
        return _orders(caller, facility, rest)
    if first == "4":
        return _text_me(caller, facility)
    return con("That choice is not on the screen.\n0. Back")


def _alert(facility: str, rest: list[str]) -> str:
    snap = service.snapshot(None)
    views = morning_list(snap, facility, "RBC")
    held = [v for v in views if v["held"]]
    if not held:
        return con("This hospital does not hold red cells. Requests are filled from the regional centre.\n0. Back")
    act = [v["blood_group_label"] for v in held if v["status"] == "act"]
    watch = [v["blood_group_label"] for v in held if v["status"] == "watch"]
    lines = [words.day(snap.as_of), summary_sentence(views)]
    if act:
        lines.append("ACT: " + " ".join(act))
    if watch:
        lines.append("WATCH: " + " ".join(watch))
    delivery = next((v["next_delivery"]["label"] for v in held if v.get("next_delivery")), None)
    if delivery:
        lines.append(f"Next delivery {delivery}")
    lines.append("0. Back")
    return con("\n".join(lines))


def _cover(facility: str, rest: list[str]) -> str:
    snap = service.snapshot(None)
    products = config.load_settings("blood")["products"]
    held = [c for c in products if (facility, c) in snap.held]
    if not held:
        return con("No blood products are held here.\n0. Back")
    kind, component, rest = pick(held, rest, "Which product?", lambda c: products[c]["label"])
    if kind != "chosen":
        return component
    views = [v for v in morning_list(snap, facility, component) if v["held"]]
    order = {g: n for n, g in enumerate(config.load_settings("blood")["blood_groups"])}
    views.sort(key=lambda v: order[v["blood_group"]])
    kind, view, rest = pick(views, rest, f"{products[component]['label']} cover (days)", _cover_line)
    if kind != "chosen":
        return view
    return con(_group_detail(view))


def _cover_line(v: dict) -> str:
    cover = "none" if v["cover_days"] is None else ("14+d" if v.get("cover_capped") else f"{v['cover_days']:.1f}d")
    return f"{v['blood_group_label']} {v['status_label']} {cover}"


def _group_detail(v: dict) -> str:
    cover = "no use expected" if v["cover_days"] is None else (
        "14+ days of cover" if v.get("cover_capped") else f"{words.days(v['cover_days'])} of cover")
    lines = [f"{v['blood_group_label']} {v['component_label']}: {v['status_label']}",
             f"{words.units(v['units_on_shelf'])} on shelf, {cover}"]
    if v.get("stockout_date"):
        lines.append(f"Likely short from {words.day(v['stockout_date'])}")
    if v.get("next_delivery"):
        lines.append(f"Next delivery {v['next_delivery']['label']}")
    s = v.get("suggestion")
    if s and s.get("quantity"):
        lines.append(f"Suggested: {words.units(s['quantity'])}")
    lines.append("0. Back")
    return "\n".join(lines)


def _orders(caller: Caller, facility: str, rest: list[str]) -> str:
    snap = service.snapshot(None)
    views = [v for v in morning_list(snap, facility, "RBC")
             if v["held"] and v["status"] in ("act", "watch") and v.get("suggestion") and v["suggestion"]["quantity"]]
    if not views:
        return con("No order is suggested today.\n0. Back")
    kind, view, rest = pick(views, rest, "Suggested orders (red cells)",
                            lambda v: f"{v['blood_group_label']} {words.units(v['suggestion']['quantity'])}")
    if kind != "chosen":
        return view
    s = view["suggestion"]
    already = read("SELECT action FROM decision WHERE as_of = ? AND series_id = ? AND withdrawn_at IS NULL",
                   (view["as_of"], view["id"]))
    if not rest:
        head = f"{view['blood_group_label']}: {s['title']}\n{s['sum_text']}"
        if len(already):
            return con(f"{head}\nAlready decided today.\n0. Back")
        if not caller.can_decide:
            return con(f"{head}\nView only. Sign in to the app to decide.\n0. Back")
        return con(f"{head}\n1. Accept {words.units(s['quantity'])}\n0. Back")
    if rest[0] == "1" and caller.can_decide:
        return _accept(caller, view)
    return con("That choice is not on the screen.\n0. Back")


def _accept(caller: Caller, view: dict) -> str:
    from fastapi import HTTPException

    try:
        done = service.record_decision(caller.user, {"series_id": view["id"], "as_of": view["as_of"], "action": "accept"})
    except HTTPException as error:
        return end(str(error.detail)[:150])
    service.audit(caller.user, "ussd_decision", facility_id=view["facility_id"], series_id=view["id"],
                  as_of=view["as_of"], note=f"phone {gateway.mask(caller.phone)}")
    quantity = done["decision"]["final_quantity"]
    return end(f"Recorded: {words.units(quantity)} of {view['blood_group_label']}. Change or undo it in the app.")


def _text_me(caller: Caller, facility: str) -> str:
    if not gateway.configured():
        return end("SMS is not set up on this server yet.")
    if not gateway.allow_send(caller.phone):
        return end("You have asked for several texts already. Try again in an hour.")
    from backend.api.sms import alert_text

    text = alert_text(facility)
    if text is None:
        return end("This hospital does not hold red cells, so there is no alert to send.")
    result = gateway.send_sms([caller.phone], text)
    service.audit(caller.user, "sms_alert_requested_by_ussd", facility_id=facility,
                  note=f"{gateway.mask(caller.phone)}: {'sent' if result['ok'] else 'not sent'}")
    return end("The alert is on its way to your phone." if result["ok"] else "The text could not be sent. Try again later.")
