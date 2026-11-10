"""Backtest: forecast from many past dates and compare with what really happened.

Run from the repo root:
    python -m backend.engine.backtest --model baseline

For each weekly origin, the model sees only the days before it and forecasts
the next 14 days for every hospital, component and blood group. Forecasts go
to the `forecast` table, scores to `backtest_metric`, and docs/RESULTS.md is
rewritten with every model that has been run.

Scores (never MAPE, because most days have zero demand):
- MAE   average units off per series and day;
- WAPE  total units off divided by total units requested;
- MASE  MAE divided by the error of "same as the same weekday last week" over
        the six months before each origin. Below 1 beats that naive rule;
- WAPE on 7-day totals, because orders are placed per delivery cycle, not per day;
- range hit: share of days where the real demand fell inside the p10 to p90 range.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from backend import config
from backend.db.core import replace_model_rows
from backend.engine import models
from backend.engine.demand import DemandPanel, load_panel

SEGMENT_ORDER = ["all", "component", "group rarity", "facility type", "region"]


def origins() -> pd.DatetimeIndex:
    settings = config.load_settings("thresholds")["backtest"]
    return pd.date_range(str(settings["first_origin"]), str(settings["last_origin"]), freq="7D")


def run_forecasts(panel: DemandPanel, model_name: str, origin_dates=None, horizon: int | None = None) -> pd.DataFrame:
    """Long table of forecasts with the actual demand beside them (NaN past the end of the data)."""
    model = models.get(model_name)
    horizon = horizon or config.load_settings("thresholds")["forecast"]["horizon_days"]
    n_days = len(panel.dates)
    frames = []
    for origin in (origin_dates if origin_dates is not None else origins()):
        cutoff = panel.position(origin)
        out = model.forecast(panel, origin, horizon)
        scale = np.abs(panel.requested[max(cutoff - 182, 7):cutoff]
                       - panel.requested[max(cutoff - 182, 7) - 7:cutoff - 7]).mean(axis=0)
        for h in range(horizon):
            row = cutoff + h
            frames.append(pd.DataFrame({
                "origin": origin, "target_date": origin + pd.Timedelta(days=h), "horizon": h + 1,
                "series": np.arange(len(panel.series)),
                "p10": out["p10"][h], "p50": out["p50"][h], "p90": out["p90"][h],
                "actual": panel.requested[row] if row < n_days else np.nan,
                "naive_scale": scale,
            }))
    result = pd.concat(frames, ignore_index=True)
    result["model"] = model_name
    return result


def _score(group: pd.DataFrame) -> dict[str, float]:
    err = (group["actual"] - group["p50"]).abs()
    total = group["actual"].sum()
    week = group[group["horizon"] <= 7].groupby(["origin", "series"])[["actual", "p50"]].sum()
    week_total = week["actual"].sum()
    costs = config.load_settings("thresholds")["risk"]
    gap = week["actual"] - week["p50"]
    cost = (costs["stockout_cost"] * gap.clip(lower=0) + costs["waste_cost"] * (-gap).clip(lower=0)).sum()
    scale = group["naive_scale"].sum()
    return {
        "n": int(len(group)),
        "units_requested": float(total),
        "mae": float(err.mean()),
        "wape": float(err.sum() / total) if total else np.nan,
        "mase": float(err.sum() / scale) if scale else np.nan,
        "wape_7day": float((week["actual"] - week["p50"]).abs().sum() / week_total) if week_total else np.nan,
        "asymmetric_cost": float(cost / week_total) if week_total else np.nan,
        "range_hit": float(((group["actual"] >= group["p10"] - 1e-9) & (group["actual"] <= group["p90"] + 1e-9)).mean()),
    }


def score(forecasts: pd.DataFrame, panel: DemandPanel) -> pd.DataFrame:
    """Scores for all series and for each segment."""
    common = set(config.load_settings("thresholds")["forecast"]["common_groups"])
    meta = panel.series.copy()
    meta["group rarity"] = np.where(meta["blood_group"].isin(common), "common (O+, A+, B+)", "rare (all others)")
    meta = meta.drop(columns=["region"]).rename(columns={"facility_type": "facility type", "region_name": "region"})
    data = forecasts.dropna(subset=["actual"]).merge(
        meta[["component", "group rarity", "facility type", "region"]], left_on="series", right_index=True)
    rows = [{"segment_type": "all", "segment": "all series", **_score(data)}]
    for segment_type in SEGMENT_ORDER[1:]:
        for name, group in data.groupby(segment_type):
            rows.append({"segment_type": segment_type, "segment": name, **_score(group)})
    out = pd.DataFrame(rows)
    out.insert(0, "model", forecasts["model"].iloc[0])
    return out


def save(forecasts: pd.DataFrame, metrics: pd.DataFrame, panel: DemandPanel, db_path: Path | None = None) -> None:
    model_name = forecasts["model"].iloc[0]
    meta = panel.series[["facility_id", "component", "blood_group"]]
    table = forecasts.merge(meta, left_on="series", right_index=True)[
        ["origin", "facility_id", "component", "blood_group", "target_date", "model", "p10", "p50", "p90"]].copy()
    for column in ("origin", "target_date"):
        table[column] = table[column].dt.strftime("%Y-%m-%d")
    table[["p10", "p50", "p90"]] = table[["p10", "p50", "p90"]].round(3)
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        for name, frame in (("forecast", table), ("backtest_metric", metrics)):
            replace_model_rows(conn, name, frame, model_name)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_forecast ON forecast (model, origin, facility_id)")
        conn.commit()
    finally:
        conn.close()


def store_prepared_dates(panel: DemandPanel, model_name: str, db_path: Path | None = None) -> None:
    """Also store forecasts for the app's prepared dates that are outside the test window.

    They are never scored; they only let the app open those dates without retraining.
    """
    tested = set(origins())
    extra = [pd.Timestamp(str(d["date"])) for d in config.load_settings("site")["as_of_dates"]]
    extra = [d for d in extra if d not in tested]
    if not extra:
        return
    forecasts = run_forecasts(panel, model_name, origin_dates=extra)
    meta = panel.series[["facility_id", "component", "blood_group"]]
    table = forecasts.merge(meta, left_on="series", right_index=True)[
        ["origin", "facility_id", "component", "blood_group", "target_date", "model", "p10", "p50", "p90"]].copy()
    for column in ("origin", "target_date"):
        table[column] = table[column].dt.strftime("%Y-%m-%d")
    table[["p10", "p50", "p90"]] = table[["p10", "p50", "p90"]].round(3)
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        table.to_sql("forecast", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()


def stored_forecast(panel: DemandPanel, model_name: str, as_of, horizon: int, db_path: Path | None = None):
    """Forecast arrays read back from the `forecast` table, or None if they are not there."""
    from backend.db.core import read, table_exists

    if not table_exists("forecast", db_path):
        return None
    rows = read("SELECT facility_id, component, blood_group, target_date, p10, p50, p90 FROM forecast "
                "WHERE model = ? AND origin = ?", (model_name, str(pd.Timestamp(as_of).date())),
                parse_dates=["target_date"], path=db_path)
    if len(rows) != horizon * len(panel.series):
        return None
    rows["series_id"] = rows["facility_id"] + "|" + rows["component"] + "|" + rows["blood_group"]
    order = pd.Series(np.arange(len(panel.series)), index=panel.series["series_id"])
    col = order.reindex(rows["series_id"]).to_numpy()
    row = (rows["target_date"] - pd.Timestamp(as_of)).dt.days.to_numpy()
    out = {}
    for name in ("p10", "p50", "p90"):
        array = np.zeros((horizon, len(panel.series)))
        array[row, col] = rows[name].to_numpy()
        out[name] = array
    return out


def run(model_name: str, db_path: Path | None = None, write_docs: bool = True, verbose: bool = True) -> pd.DataFrame:
    panel = load_panel(db_path)
    forecasts = run_forecasts(panel, model_name)
    metrics = score(forecasts, panel)
    save(forecasts, metrics, panel, db_path)
    store_prepared_dates(panel, model_name, db_path)
    if model_name == "m1":
        from backend.engine import model_m1

        note = model_m1.validate_rare_choice(panel)
        conn = sqlite3.connect(db_path or config.DB_PATH)
        try:
            pd.DataFrame([{"key": k, "value": str(v)} for k, v in note.items()]).to_sql(
                "model_note", conn, if_exists="replace", index=False)
            conn.commit()
        finally:
            conn.close()
    from backend.engine.results import write_results

    text = write_results(db_path, write_docs=write_docs)
    if verbose:
        print(text)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest a forecast model.")
    parser.add_argument("--model", default="baseline", choices=sorted(models.REGISTRY))
    run(parser.parse_args().model)
