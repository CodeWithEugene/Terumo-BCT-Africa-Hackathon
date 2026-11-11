"""The pooled forecast model (M1)."""
import numpy as np
import pandas as pd
import pytest

from backend.engine import forecasting, model_m1
from backend.engine.demand import load_panel

ORIGIN = pd.Timestamp("2026-09-28")


@pytest.fixture(scope="module")
def panel(db_path):
    return load_panel(db_path)


def test_forecast_has_a_sensible_shape_and_range(panel):
    out = model_m1.forecast(panel, ORIGIN, 14)
    assert out["p50"].shape == (14, 768)
    for name in ("p10", "p50", "p90"):
        assert np.isfinite(out[name]).all() and (out[name] >= 0).all()
    assert (out["p10"] <= out["p50"] + 1e-9).all() and (out["p50"] <= out["p90"] + 1e-9).all()
    cut = panel.position(ORIGIN)
    recent_week = panel.requested[cut - 28:cut].sum() / 4
    assert 0.7 * recent_week < out["p50"][:7].sum() < 1.3 * recent_week


def test_model_never_sees_the_future(panel):
    cut = panel.position(ORIGIN)
    before = model_m1.forecast(panel, ORIGIN, 14)["p50"].copy()
    saved = panel.requested[cut:].copy()
    try:
        panel.requested[cut:] += 100
        model_m1._CACHE.clear()
        after = model_m1.forecast(panel, ORIGIN, 14)["p50"]
    finally:
        panel.requested[cut:] = saved
        model_m1._CACHE.clear()
    assert np.allclose(before, after)


def test_rare_series_use_the_baseline(panel):
    from backend.engine import baseline

    cut = panel.position(ORIGIN)
    rare = model_m1.rare_series(panel, cut)
    assert 0.5 < rare.mean() < 0.95
    out = model_m1.forecast(panel, ORIGIN, 14)
    simple = baseline.forecast(panel, ORIGIN, 14)
    assert np.allclose(out["p50"][:, rare], simple["p50"][:, rare])
    assert not np.allclose(out["p50"][:, ~rare], simple["p50"][:, ~rare])


def test_the_app_uses_the_model_when_it_works(panel):
    made = forecasting.make(panel, ORIGIN, 14, "auto")
    assert made.mode == "model" and made.model == "m1"
    forced = forecasting.make(panel, ORIGIN, 14, "baseline")
    assert forced.mode == "fallback" and forced.model == "baseline"
