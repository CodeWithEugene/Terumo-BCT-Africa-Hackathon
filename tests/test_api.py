"""The API: sign-in, scope, decisions, the audit log and the fallback."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}
THIKA_O_POS = "HSP-006|RBC|O+"


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def client_for(username: str | None) -> TestClient:
    client = TestClient(app)
    if username:
        reply = client.post("/api/login", json={"username": username, "password": PASSWORDS[username]})
        assert reply.status_code == 200
    return client


def test_data_needs_a_sign_in():
    client = client_for(None)
    for path in ("/api/brief", "/api/decisions", "/api/accuracy", "/api/me", f"/api/series/{THIKA_O_POS}"):
        assert client.get(path).status_code == 401
    assert client.post("/api/login", json={"username": "amina", "password": "wrong"}).status_code == 401


def test_a_forged_cookie_is_refused():
    client = TestClient(app)
    client.cookies.set("sp_session", "eyJ1IjogMSwgImV4cCI6IDk5OTk5OTk5OTl9.deadbeef")
    assert client.get("/api/me").status_code == 401


def test_passwords_are_stored_hashed(db_path):
    rows = sqlite3.connect(db_path).execute("SELECT password_hash, salt FROM app_user").fetchall()
    assert len(rows) == 3
    for stored, salt in rows:
        assert len(stored) == 64 and stored not in PASSWORDS.values() and len(salt) == 32


def test_hospital_officer_sees_only_their_hospital():
    amina = client_for("amina")
    brief = amina.get("/api/brief").json()
    assert brief["facility"]["facility_id"] == "HSP-006" and len(brief["series"]) == 8
    assert amina.get("/api/brief", params={"facility_id": "HSP-003"}).status_code == 403
    assert amina.get("/api/series/HSP-003|RBC|O+").status_code == 403
    assert amina.post("/api/decisions", json={"series_id": "HSP-003|RBC|O+", "action": "accept"}).status_code == 403
    assert [f["facility_id"] for f in amina.get("/api/me").json()["user"]["facilities"]] == ["HSP-006"]


def test_regional_officer_sees_only_hospitals_their_centre_supplies():
    grace = client_for("grace")
    facilities = {f["facility_id"] for f in grace.get("/api/me").json()["user"]["facilities"]}
    assert {"HSP-003", "HSP-006"} <= facilities and "HSP-012" not in facilities
    assert grace.get("/api/brief", params={"facility_id": "HSP-003"}).status_code == 200
    assert grace.get("/api/brief", params={"facility_id": "HSP-012"}).status_code == 403
    overview = grace.get("/api/overview").json()
    assert {f["facility_id"] for f in overview["facilities"]} == facilities


def test_every_response_says_which_mode_is_in_use():
    amina = client_for("amina")
    for path in ("/api/brief", "/api/decisions", "/api/accuracy", "/api/me", "/api/asof-dates",
                 f"/api/series/{THIKA_O_POS}", "/api/overview", "/api/health"):
        assert amina.get(path).json()["mode"] in ("model", "fallback"), path


def test_series_detail_has_projection_reasons_and_what_happened():
    detail = client_for("amina").get(f"/api/series/{THIKA_O_POS}").json()["series"]
    assert len(detail["projection"]) == 14 and detail["status_line"]
    assert detail["actual"]["days"] and "compatible_cover" in detail
    assert detail["forecast_compare"]["baseline_7_days"] >= 0


def test_only_prepared_dates_are_served():
    amina = client_for("amina")
    assert amina.get("/api/brief", params={"as_of": "2026-08-03"}).status_code == 200
    assert amina.get("/api/brief", params={"as_of": "2026-08-04"}).status_code == 400


def test_change_and_reject_need_a_reason_and_everything_is_logged(db_path):
    amina = client_for("amina")
    series = amina.get("/api/brief").json()["series"]
    targets = [s for s in series if s["suggestion"]][:3]
    first, second, third = (t["id"] for t in targets)

    no_reason = amina.post("/api/decisions", json={"series_id": first, "action": "reject"})
    assert no_reason.status_code == 422
    bad = amina.post("/api/decisions", json={"series_id": first, "action": "change", "quantity": 4,
                                             "reason_code": "made_up"})
    assert bad.status_code == 422

    accepted = amina.post("/api/decisions", json={"series_id": first, "action": "accept"}).json()["decision"]
    assert accepted["final_quantity"] == accepted["suggested_quantity"]
    assert accepted["summary"].startswith("Accepted by Amina W.")
    again = amina.post("/api/decisions", json={"series_id": first, "action": "accept"})
    assert again.status_code == 409

    quantity = targets[1]["suggestion"]["quantity"] + 2
    changed = amina.post("/api/decisions", json={"series_id": second, "action": "change", "quantity": quantity,
                                                 "reason_code": "event_expected", "note": "Clinic day"}).json()
    assert changed["decision"]["final_quantity"] == quantity

    rejected = amina.post("/api/decisions", json={"series_id": third, "action": "reject",
                                                  "reason_code": "already_ordered"}).json()["decision"]
    assert rejected["final_quantity"] == 0

    listed = amina.get("/api/decisions").json()["decisions"]
    assert {d["action"] for d in listed} == {"accept", "change", "reject"}
    assert amina.get("/api/decisions", params={"action": "change"}).json()["decisions"][0]["reason_label"]
    shown = {s["id"]: s["decision"] for s in amina.get("/api/brief").json()["series"]}
    assert shown[first]["action"] == "accept" and shown[second]["action"] == "change"

    entries = amina.get("/api/audit").json()["entries"]
    decision_entries = [e for e in entries if e["event"] == "decision"]
    assert len(decision_entries) == 3
    saw = decision_entries[0]["saw"]
    assert {"baseline_7_days", "model_7_days", "suggested_quantity", "status"} <= set(saw)
    assert decision_entries[0]["username"] == "amina" and decision_entries[0]["role"] == "hospital_officer"

    undone = amina.post(f"/api/decisions/{rejected['decision_id']}/undo")
    assert undone.status_code == 200
    events = [e["event"] for e in amina.get("/api/audit").json()["entries"]]
    assert "decision_withdrawn" in events and events.count("decision") == 3   # nothing was erased

    joseph = client_for("joseph")
    assert joseph.get("/api/decisions").json()["decisions"] == []
    assert all(e["facility_id"] in (None, "HSP-003") for e in joseph.get("/api/audit").json()["entries"])


def test_the_audit_log_cannot_be_edited(db_path):
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_log SET note = 'changed'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_log")
    conn.close()


def test_fallback_switch_serves_the_baseline_and_says_so():
    amina = client_for("amina")
    on = amina.post("/api/fallback", json={"use_baseline": True}).json()
    assert on["mode"] == "fallback" and on["fallback_forced"] is True
    brief = amina.get("/api/brief").json()
    assert brief["mode"] == "fallback" and brief["model"] == "baseline"
    assert all(s["mode"] == "fallback" for s in brief["series"])
    off = amina.post("/api/fallback", json={"use_baseline": False}).json()
    assert off["fallback_forced"] is False


def test_api_falls_back_when_the_model_fails(monkeypatch):
    from backend.api import service
    from backend.engine import models

    class Broken:
        NAME = "m1"
        LABEL = "Broken model"

        @staticmethod
        def forecast(*args, **kwargs):
            raise RuntimeError("could not load the model")

    monkeypatch.setitem(models.REGISTRY, "m1", Broken)
    service._snapshot.cache_clear()
    try:
        brief = client_for("amina").get("/api/brief").json()
        assert brief["mode"] == "fallback" and brief["model"] == "baseline"
        assert len(brief["series"]) == 8 and brief["sentence"]
    finally:
        service._snapshot.cache_clear()
