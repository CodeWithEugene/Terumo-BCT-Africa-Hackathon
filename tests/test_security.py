"""Security checks: headers, cross-site requests, password limits, and what the central copy would hold."""
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api import security
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables
from backend.sync import oracle

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def test_every_api_response_carries_security_headers():
    response = TestClient(app).get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


def test_session_cookie_is_http_only_and_same_site():
    client = TestClient(app)
    reply = client.post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    cookie = reply.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_cookie_is_marked_secure_when_served_over_https(monkeypatch):
    monkeypatch.setenv("SP_COOKIE_SECURE", "1")
    reply = TestClient(app).post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    assert "secure" in reply.headers["set-cookie"].lower()


def test_posts_from_another_site_are_refused():
    client = TestClient(app)
    client.post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    evil = client.post("/api/fallback", json={"use_baseline": True}, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    same = client.post("/api/fallback", json={"use_baseline": False}, headers={"Origin": "http://testserver"})
    assert same.status_code == 200
    # The development frontend (port 5173) passes calls on to the API and must be allowed.
    dev = client.post("/api/fallback", json={"use_baseline": False}, headers={"Origin": "http://localhost:5173"})
    assert dev.status_code == 200


def test_sign_in_works_from_the_development_frontend():
    reply = TestClient(app).post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]},
                                 headers={"Origin": "http://localhost:5173", "Host": "127.0.0.1:8000"})
    assert reply.status_code == 200


def test_wrong_passwords_are_limited():
    security._failures.clear()
    client = TestClient(app)
    for _ in range(security.MAX_FAILURES):
        assert client.post("/api/login", json={"username": "grace", "password": "nope"}).status_code == 401
    assert client.post("/api/login", json={"username": "grace", "password": "nope"}).status_code == 429
    assert client.post("/api/login", json={"username": "grace", "password": PASSWORDS["grace"]}).status_code == 429
    security._failures.clear()
    assert client.post("/api/login", json={"username": "grace", "password": PASSWORDS["grace"]}).status_code == 200


def test_sql_shaped_input_is_just_text():
    client = TestClient(app)
    client.post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    assert client.get("/api/series/x' OR '1'='1").status_code == 404
    assert client.get("/api/brief", params={"as_of": "2026-09-28'; DROP TABLE decision;--"}).status_code == 400
    assert client.post("/api/login", json={"username": "' OR 1=1 --", "password": "x"}).status_code == 401
    assert client.get("/api/decisions").status_code == 200


def test_demo_logins_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SP_DEMO_LOGINS", "0")
    assert TestClient(app).get("/api/demo-users").json()["users"] == []


def test_central_copy_holds_no_names_and_no_single_requests(db_path):
    client = TestClient(app)
    client.post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    tables = oracle.prepare_tables(db_path)
    assert {"DEMAND_WEEKLY", "STOCK_DAILY", "AUDIT_LOG", "DECISION"} <= set(tables)
    for name in ("AUDIT_LOG", "DECISION"):
        frame = tables[name]
        assert not ({"USERNAME", "DISPLAY_NAME", "USER_ID", "NOTE"} & set(frame.columns))
        assert frame["STAFF_CODE"].dropna().str.startswith("staff_").all()
        assert "amina" not in frame.to_json().lower()
    assert "YEAR_WEEK" in tables["DEMAND_WEEKLY"].columns and "DATE" not in tables["DEMAND_WEEKLY"].columns


def test_sync_exits_cleanly_when_not_set_up(monkeypatch, capsys):
    for name in oracle.REQUIRED:
        monkeypatch.delenv(name, raising=False)
    assert oracle.main() == 0
    assert "not set up" in capsys.readouterr().out


def test_one_tap_sign_in_never_sends_a_password_to_the_browser(monkeypatch):
    client = TestClient(app)
    listed = client.get("/api/demo-users").json()["users"]
    assert listed and all("demo_password" not in user and "password" not in str(user).lower() for user in listed)
    reply = client.post("/api/demo-login", json={"username": "joseph"})
    assert reply.status_code == 200 and reply.json()["user"]["username"] == "joseph"
    assert client.get("/api/me").status_code == 200
    assert TestClient(app).post("/api/demo-login", json={"username": "someone-else"}).status_code == 403
    monkeypatch.setenv("SP_DEMO_LOGINS", "0")
    assert TestClient(app).post("/api/demo-login", json={"username": "joseph"}).status_code == 403
