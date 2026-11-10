"""Jael's feature list: stock-out chance, usable stock, dual risk, what-if, call-out draft, apheresis hint, cost."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables
from backend.engine import allocation
from backend.engine.simulate import stockout_probability

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def signed_in(username: str) -> TestClient:
    client = TestClient(app)
    client.post("/api/login", json={"username": username, "password": PASSWORDS[username]})
    return client


def test_stockout_chance_behaves_like_a_probability():
    days, zero = 14, np.zeros(14)
    demand = np.full(days, 2.0)
    empty = stockout_probability(0, zero, zero, demand, demand + 2, [3, 7])
    full = stockout_probability(500, zero, zero, demand, demand + 2, [3, 7])
    some = stockout_probability(10, zero, zero, demand, demand + 2, [3, 7])
    assert empty[7] > 0.95 and full[7] == 0.0
    assert 0 <= some[3] <= some[7] <= 1                  # a longer window can only be riskier
    assert stockout_probability(0, zero, zero, zero, zero, [7])[7] == 0.0     # no demand, no stock-out


def test_every_held_series_reports_both_risks_and_usable_stock():
    for user in ("amina", "joseph"):
        for view in signed_in(user).get("/api/brief").json()["series"]:
            assert 0 <= view["stockout_chance_before_delivery"] <= 1 and 0 <= view["stockout_chance_7_days"] <= 1
            assert 0 <= view["usable_units"] <= view["units_on_shelf"]
            assert view["waste_level"] in ("none", "watch", "high") and view["waste_units_14_days"] >= 0


def test_what_if_surge_and_delay_raise_the_risk_and_save_nothing():
    joseph = signed_in("joseph")
    path = "/api/series/HSP-003|RBC|A+"
    base = joseph.get(path).json()["series"]
    worse = joseph.get(path, params={"surge_units": 12, "delay_days": 3}).json()["series"]
    assert worse["scenario"] == {"delay_days": 3, "surge_units": 12.0} and base["scenario"] is None
    assert worse["stockout_chance_7_days"] >= base["stockout_chance_7_days"]
    assert worse["projection"][0]["demand"] > base["projection"][0]["demand"]
    assert joseph.get(path).json()["series"]["projection"] == base["projection"]
    assert joseph.get(path, params={"delay_days": 99}).status_code == 422


def test_cancelled_drive_lowers_supply():
    grace = signed_in("grace")
    base = grace.get("/api/region", params={"as_of": "2026-10-05"}).json()
    less = grace.get("/api/region", params={"as_of": "2026-10-05", "extra_donors": -150, "extra_date": "2026-10-12"}).json()
    assert sum(w["expected_cleared"] for w in less["weeks"]) < sum(w["expected_cleared"] for w in base["weeks"])
    assert all(w["expected_cleared"] >= 0 for w in less["weeks"])


def test_call_out_draft_and_apheresis_hint_are_drafts_with_stated_assumptions():
    view = signed_in("grace").get("/api/region", params={"as_of": "2026-10-05"}).json()
    for item in view["drive_suggestions"]:
        assert "STOP" in item["call_out_draft"] and len(item["call_out_draft"]) <= 300
    hint = view["apheresis"]
    assert hint and len(hint["days"]) == 7 and "Assumption" in hint["note"]
    assert hint["week_donors_busy"] >= hint["week_donors"] >= 0


def test_protected_minimum_brings_a_hospital_up_first():
    shelf, daily, ok = np.array([0.0, 0.0]), np.array([4.0, 1.0]), np.array([True, True])
    plain = allocation.fair_share(8, shelf, daily, ok)
    kept = allocation.fair_share(8, shelf, daily, ok, protected_days=np.array([0.0, 7.0]))
    assert kept.sum() == plain.sum() == 8 and kept[1] >= 7 > plain[1]


def test_backtest_reports_the_stockout_versus_waste_cost(db_path):
    from backend.engine import backtest

    metrics = backtest.run("baseline", db_path=db_path, write_docs=False, verbose=False)
    overall = metrics[metrics["segment_type"] == "all"].iloc[0]
    assert overall["asymmetric_cost"] > overall["wape_7day"]        # shortfalls are weighted five times
