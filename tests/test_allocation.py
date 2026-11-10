"""Fair-share allocation: the rule, the replay and the regional proposal."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables
from backend.engine import allocation

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def test_rule_raises_the_lowest_cover_first_and_keeps_every_unit():
    give = allocation.fair_share(10, np.array([0.0, 20.0, 0.0]), np.array([2.0, 2.0, 0.0]), np.array([True, True, True]))
    assert list(give) == [10, 0, 0]                 # the empty, busy shelf gets them; no use means no units
    even = allocation.fair_share(8, np.array([0.0, 0.0]), np.array([3.0, 1.0]), np.array([True, True]))
    assert even.sum() == 8 and even[0] == 6         # shared in proportion to use when both start empty
    assert allocation.fair_share(5, np.array([0.0]), np.array([1.0]), np.array([False])).sum() == 0


@pytest.fixture(scope="module")
def scores(db_path):
    return allocation.replay(db_path)


def test_replay_moves_no_blood_in_or_out(scores):
    overall = scores[scores["facility_id"] == "ALL"].set_index("policy")
    assert overall.loc["actual", "units_requested"] == overall.loc["fair", "units_requested"]
    for policy in ("actual", "fair"):
        row = overall.loc[policy]
        assert 0 <= row["units_short"] <= row["units_requested"] and row["units_expired"] >= 0
    assert len(scores[scores["facility_id"] != "ALL"]) == 2 * 32


def test_replay_reports_both_policies_for_every_hospital(scores):
    assert set(scores["policy"]) == {"actual", "fair"}
    assert scores["short_pct"].between(0, 100).all()


def test_regional_view_offers_a_fair_share_proposal_that_can_be_decided():
    grace = TestClient(app)
    grace.post("/api/login", json={"username": "grace", "password": PASSWORDS["grace"]})
    plan = grace.get("/api/region", params={"as_of": "2026-10-19"}).json()["allocation"]
    assert len(plan["rows"]) == 8
    assert sum(r["fair_units"] for r in plan["rows"]) == plan["total_units"]
    assert sum(r["change"] for r in plan["rows"] if r["change"] > 0) == plan["units_moved"]
    if plan["units_moved"] > 0:
        saved = grace.post("/api/decisions", json={"series_id": plan["id"], "as_of": "2026-10-19", "action": "accept"})
        assert saved.status_code == 200 and saved.json()["decision"]["suggestion_kind"] == "allocation"
    amina = TestClient(app)
    amina.post("/api/login", json={"username": "amina", "password": PASSWORDS["amina"]})
    assert amina.post("/api/decisions", json={"series_id": plan["id"], "action": "accept"}).status_code == 403
