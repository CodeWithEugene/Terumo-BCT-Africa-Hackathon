"""The regional view: supply outlook, gap, drive suggestions and the what-if."""
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def signed_in(username: str) -> TestClient:
    client = TestClient(app)
    assert client.post("/api/login", json={"username": username, "password": PASSWORDS[username]}).status_code == 200
    return client


def test_only_regional_officers_see_the_regional_view():
    assert signed_in("amina").get("/api/region").status_code == 403
    assert TestClient(app).get("/api/region").status_code == 401


def test_regional_view_has_four_weeks_eight_groups_and_a_balance():
    view = signed_in("grace").get("/api/region", params={"as_of": "2026-10-05"}).json()
    assert view["centre"]["facility_id"] == "RBTC-NBO"
    assert len(view["weeks"]) == 4 and len(view["groups"]) == 8
    for week in view["weeks"]:
        assert week["expected_cleared"] >= 0 and week["demand"] > 0
    for group in view["groups"]:
        for week in group["weeks"]:
            assert week["short"] >= 0 and week["stock_end"] >= 0
            assert not (week["short"] > 0 and week["stock_end"] > 0)     # cannot be short and hold stock


def test_a_what_if_drive_raises_supply_and_saves_nothing():
    grace = signed_in("grace")
    base = grace.get("/api/region", params={"as_of": "2026-10-05"}).json()
    more = grace.get("/api/region", params={"as_of": "2026-10-05", "extra_donors": 200, "extra_date": "2026-10-12"}).json()
    assert sum(w["expected_cleared"] for w in more["weeks"]) > sum(w["expected_cleared"] for w in base["weeks"])
    assert sum(w["units_short"] for w in more["weeks"]) <= sum(w["units_short"] for w in base["weeks"])
    assert more["what_if"] and not base["what_if"]
    again = grace.get("/api/region", params={"as_of": "2026-10-05"}).json()
    assert again["weeks"] == base["weeks"]
    assert grace.get("/api/region", params={"extra_donors": 50, "extra_date": "2027-03-01"}).status_code == 422


def test_drive_suggestions_can_be_decided_and_are_logged():
    grace = signed_in("grace")
    view = next((v for v in (grace.get("/api/region", params={"as_of": d}).json()
                             for d in ("2026-10-05", "2026-09-28", "2026-10-19", "2026-03-30"))
                 if v["drive_suggestions"]), None)
    assert view is not None, "expected at least one prepared date with a projected gap"
    item = view["drive_suggestions"][0]
    assert item["suggestion"]["sum_text"] and item["suggestion"]["quantity"] > 0
    body = {"series_id": item["id"], "as_of": view["as_of"], "action": "change",
            "quantity": item["suggestion"]["quantity"] + 10}
    assert grace.post("/api/decisions", json=body).status_code == 422          # a change needs a reason
    saved = grace.post("/api/decisions", json={**body, "reason_code": "local_knowledge"}).json()["decision"]
    assert saved["suggestion_kind"] == "drive" and saved["facility_id"] == "RBTC-NBO"
    assert any(d["decision_id"] == saved["decision_id"] for d in grace.get("/api/decisions").json()["decisions"])
    assert any(e["series_id"] == item["id"] for e in grace.get("/api/audit").json()["entries"])
    amina = signed_in("amina")
    assert amina.post("/api/decisions", json={"series_id": item["id"], "action": "accept"}).status_code == 403
    assert all(d["suggestion_kind"] != "drive" for d in amina.get("/api/decisions").json()["decisions"])
