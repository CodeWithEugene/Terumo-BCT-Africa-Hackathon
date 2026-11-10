"""Stock projection, status rules, suggestions and reasons."""
import numpy as np
import pandas as pd
import pytest

from backend import config
from backend.engine import forecasting
from backend.engine.brief import summary_sentence
from backend.engine.projection import _reconcile, build_snapshot, morning_list, series_view
from backend.engine.simulate import cumulative_range, days_of_cover, simulate
from backend.engine.world import get_world

AS_OF = "2026-10-05"


@pytest.fixture(scope="module")
def snap(db_path):
    return build_snapshot(get_world(db_path), AS_OF, "auto")


def test_simulate_follows_the_stock_equation():
    demand = np.array([2.0, 2.0, 2.0, 2.0])
    arrivals = np.array([0.0, 0.0, 5.0, 0.0])
    path = simulate([(1, 3.0)], demand, arrivals)       # 3 units that expire at the end of day 1
    assert list(path.stock_end) == [1.0, 0.0, 3.0, 1.0]
    assert list(path.short) == [0.0, 1.0, 0.0, 0.0]
    assert path.expired.sum() == 0


def test_units_past_their_date_are_removed_not_used():
    path = simulate([(0, 4.0)], np.array([1.0, 1.0]), np.zeros(2))
    assert path.expired[0] == 3.0 and path.short[1] == 1.0


def test_days_of_cover():
    assert days_of_cover([(99, 5.0)], np.full(14, 2.0)) == (2.5, False)
    assert days_of_cover([(99, 50.0)], np.full(14, 2.0)) == (14.0, True)
    assert days_of_cover([(99, 5.0)], np.zeros(14)) == (None, False)
    assert days_of_cover([], np.full(14, 2.0)) == (0.0, False)


def test_range_of_a_running_total_is_narrower_than_adding_daily_ranges():
    p50, p10, p90 = np.full(7, 2.0), np.full(7, 1.0), np.full(7, 4.0)
    low, high = cumulative_range(p10, p50, p90)
    assert p50.sum() < high.sum() < p90.sum()
    assert p10.sum() < low.sum() < p50.sum()


def test_shelf_count_wins_over_unit_records():
    assert sum(u for _, u in _reconcile([(3, 2.0), (9, 2.0)], 3.0)) == 3.0
    assert sum(u for _, u in _reconcile([(3, 2.0)], 5.0)) == 5.0


def test_snapshot_uses_nothing_from_the_as_of_date_onwards(db_path):
    world = get_world(db_path)
    before = series_view(build_snapshot(world, AS_OF, "baseline"), 3)
    cut = world.panel.position(AS_OF)
    saved = world.panel.requested[cut:].copy()
    try:
        world.panel.requested[cut:] += 50
        after = series_view(build_snapshot(world, AS_OF, "baseline"), 3)
    finally:
        world.panel.requested[cut:] = saved
    assert before["status"] == after["status"] and before["projection"] == after["projection"]


def test_every_held_series_has_status_line_and_a_sum(snap):
    views = morning_list(snap, "HSP-006", "RBC", detail=True)
    assert len(views) == 8
    assert [v["status_rank"] for v in views] == sorted(v["status_rank"] for v in views)
    for view in views:
        assert view["status"] in ("act", "watch", "steady")
        assert view["status_line"]
        assert len(view["projection"]) == 14
        for day in view["projection"]:
            assert day["stock_low"] <= day["stock"] + 1e-6 <= day["stock_high"] + 2e-6
        if view["suggestion"]:
            assert view["suggestion"]["sum_text"] and view["suggestion"]["quantity"] >= 0
        if view["status"] != "steady":
            assert 1 <= len(view["reasons"]) <= 3
    assert summary_sentence(views).endswith(".")


def test_staff_minimum_cannot_be_lowered_by_the_forecast(snap):
    floor = config.load_settings("thresholds")["minimum_stock"]["RBC"]["O-"]
    for view in (v for f in ("HSP-001", "HSP-006", "HSP-023") for v in morning_list(snap, f, "RBC")):
        if view["blood_group"] == "O-" and view["units_on_shelf"] < floor:
            assert view["status"] in ("watch", "act")


def test_platelets_are_marked_not_held(snap):
    views = morning_list(snap, "HSP-006", "PLT")
    assert all(v["status"] == "not_held" and v["suggestion"] is None for v in views)


def test_compatible_cover_is_information_only(snap):
    series = snap.world.panel.series
    index = series.index[(series["facility_id"] == "HSP-001") & (series["component"] == "RBC")
                         & (series["blood_group"] == "AB+")][0]
    cover = series_view(snap, index)["compatible_cover"]
    assert {g["blood_group"] for g in cover["groups"]} == {"AB-", "A+", "A-", "B+", "B-", "O+", "O-"}
    assert "Information only" in cover["note"]
    o_neg = series.index[(series["facility_id"] == "HSP-001") & (series["component"] == "RBC")
                         & (series["blood_group"] == "O-")][0]
    assert series_view(snap, o_neg)["compatible_cover"]["groups"] == []


def test_falls_back_to_the_baseline_when_the_model_fails(db_path, monkeypatch):
    from backend.engine import models

    class Broken:
        NAME = "m1"

        @staticmethod
        def forecast(*args, **kwargs):
            raise RuntimeError("model file missing")

    monkeypatch.setitem(models.REGISTRY, "m1", Broken)
    world = get_world(db_path)
    made = forecasting.make(world.panel, pd.Timestamp(AS_OF), 14, "auto")
    assert made.mode == "fallback" and made.model == "baseline"
    assert np.isfinite(made.p50).all()


def test_alert_check_reports_recall_and_precision(db_path):
    from backend.engine import alert_backtest

    flags = alert_backtest.collect("baseline", db_path, origin_dates=[pd.Timestamp(AS_OF)])
    metrics = alert_backtest.score(flags)
    everything = metrics[(metrics["segment_type"] == "all") & (metrics["rule"] == "ours")].iloc[0]
    assert everything["events"] > 0 and 0 <= everything["recall"] <= 1 and 0 <= everything["precision"] <= 1
