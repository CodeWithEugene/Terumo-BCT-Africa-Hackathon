"""The baseline forecast and the backtest harness."""
import numpy as np
import pandas as pd

from backend.engine import backtest, baseline
from backend.engine.demand import load_panel


def test_panel_has_every_hospital_component_and_group(db_path):
    panel = load_panel(db_path)
    assert len(panel.series) == 32 * 3 * 8
    assert panel.requested.shape == (365, 768)
    assert panel.requested.sum() > 30_000


def test_baseline_is_the_same_weekday_average(db_path):
    panel = load_panel(db_path)
    origin = pd.Timestamp("2026-08-03")
    out = baseline.forecast(panel, origin, 14)
    cut = panel.position(origin)
    expected_day1 = panel.requested[[cut - 7, cut - 14, cut - 21, cut - 28]].mean(axis=0)
    assert np.allclose(out["p50"][0], expected_day1)
    assert np.allclose(out["p50"][7], expected_day1)          # day 8 is the same weekday
    assert (out["p10"] <= out["p50"] + 1e-9).all() and (out["p50"] <= out["p90"] + 1e-9).all()
    assert (out["p10"] >= 0).all()


def test_baseline_never_sees_the_future(db_path):
    panel = load_panel(db_path)
    origin = pd.Timestamp("2026-08-03")
    before = baseline.forecast(panel, origin, 14)
    cut = panel.position(origin)
    panel.requested[cut:] += 100          # change everything from the forecast date on
    after = baseline.forecast(panel, origin, 14)
    for key in ("p10", "p50", "p90"):
        assert np.allclose(before[key], after[key])


def test_backtest_scores_every_segment(db_path):
    metrics = backtest.run("baseline", db_path=db_path, write_docs=False, verbose=False)
    assert set(metrics["segment_type"]) == {"all", "component", "group rarity", "facility type", "region"}
    everything = metrics[metrics["segment_type"] == "all"].iloc[0]
    assert everything["mae"] > 0 and 0.5 < everything["mase"] < 1.5
    assert len(backtest.origins()) == 16
