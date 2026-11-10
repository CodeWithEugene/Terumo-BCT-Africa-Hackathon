"""The supply forecast for red cells."""
import numpy as np
import pandas as pd

from backend import config
from backend.engine import supply, supply_backtest
from backend.engine.projection import build_snapshot, series_view
from backend.engine.world import get_world

AS_OF = pd.Timestamp("2026-09-28")


def test_forecast_shapes_and_no_negative_supply(db_path):
    world = get_world(db_path)
    made = supply.forecast(world, AS_OF)
    assert made.cleared.shape == (6, 8, 4) and made.received.shape == (32, 8, 4)
    for array in (made.cleared, made.shipped, made.received, made.centre_stock):
        assert np.isfinite(array).all() and (array >= 0).all()
    # A centre cannot ship more than its hospitals are forecast to receive, and the reverse.
    hist = supply.history(world)
    for c in range(6):
        assert made.received[hist.hospital_centre == c].sum() <= made.shipped[c].sum() + 1e-6


def test_emergency_appeals_are_never_treated_as_scheduled(db_path):
    made = supply.forecast(get_world(db_path), pd.Timestamp("2026-08-03"))
    unplanned = config.load_settings("thresholds")["supply"]["unplanned_venues"]
    assert not made.scheduled_drives["venue_type"].isin(unplanned).any()
    assert (made.scheduled_drives["date"] >= pd.Timestamp("2026-08-03")).all()


def test_supply_forecast_sees_nothing_from_the_as_of_date_onwards(db_path):
    world = get_world(db_path)
    before = supply.forecast(world, AS_OF)
    hist = supply.history(world)
    cut = int((AS_OF - hist.dates[0]).days)
    saved = [a[..., cut:].copy() for a in (hist.cleared, hist.received, hist.centre_stock, hist.emergency)]
    saved_drives = world.drive["donations_collected"].copy()
    try:
        for array in (hist.cleared, hist.received, hist.centre_stock, hist.emergency):
            array[..., cut:] += 500
        world.drive.loc[world.drive["date"] >= AS_OF, "donations_collected"] = 9999
        after = supply.forecast(world, AS_OF)
    finally:
        for array, old in zip((hist.cleared, hist.received, hist.centre_stock, hist.emergency), saved):
            array[..., cut:] = old
        world.drive["donations_collected"] = saved_drives
    assert np.allclose(before.cleared, after.cleared) and np.allclose(before.received, after.received)
    assert np.allclose(before.centre_stock, after.centre_stock)


def test_supply_backtest_scores_model_and_baseline(db_path):
    data = supply_backtest.collect(db_path, origin_dates=[AS_OF, pd.Timestamp("2026-10-05")])
    metrics = supply_backtest.score(data)
    assert set(metrics["target"]) == {"cleared", "received", "centre_stock"}
    assert set(metrics["method"]) == {"baseline", "model"}
    assert (metrics["mae"] >= 0).all()


def test_projection_works_with_and_without_the_supply_forecast(db_path):
    world = get_world(db_path)
    series = world.panel.series
    index = series.index[(series["facility_id"] == "HSP-001") & (series["component"] == "RBC")
                         & (series["blood_group"] == "O+")][0]
    with_supply = series_view(build_snapshot(world, AS_OF, "baseline", use_supply=True), index)
    usual = series_view(build_snapshot(world, AS_OF, "baseline", use_supply=False), index)
    assert with_supply["deliveries_from_supply_forecast"] and not usual["deliveries_from_supply_forecast"]
    assert sum(d["delivery"] for d in with_supply["projection"]) > 0
    assert sum(d["delivery"] for d in usual["projection"]) > 0
