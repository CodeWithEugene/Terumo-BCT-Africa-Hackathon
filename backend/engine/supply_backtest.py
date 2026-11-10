"""Backtest the supply forecast against simple baselines.

Run from the repo root:
    python -m backend.engine.supply_backtest

Same 16 Mondays as the demand backtest. Three things are scored, for red cells
(red cell units plus whole blood), 1 to 4 weeks ahead:
- cleared units per regional centre and week (baseline: average of the last 4 weeks);
- routine units each hospital receives per week (baseline: its own 4-week average);
- regional centre stock at the end of each week (baseline: "stock stays as it is today").
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from backend import config
from backend.engine import backtest, supply
from backend.engine.world import get_world

TARGETS = {
    "cleared": "Cleared units per regional centre and week",
    "received": "Routine units received per hospital and week",
    "centre_stock": "Regional centre stock at the end of the week",
}
BASELINE_LABEL = {
    "cleared": "average of the last 4 weeks",
    "received": "the hospital's average of the last 4 weeks",
    "centre_stock": "stock stays as it is today",
}


def collect(db_path: Path | None = None, origin_dates=None) -> pd.DataFrame:
    """One row per origin, target, place and week ahead (all blood groups added up)."""
    world = get_world(db_path)
    hist = supply.history(world)
    rows = []
    for origin in (origin_dates if origin_dates is not None else backtest.origins()):
        made = supply.forecast(world, origin)
        real = supply.actuals(world, origin, made.weeks)
        stock_now = np.repeat(made.centre_stock_now[..., None], made.weeks, axis=-1)
        sets = {
            "cleared": (hist.centres, made.cleared, made.cleared_baseline),
            "received": (hist.hospitals, made.received, made.received_baseline),
            "centre_stock": (hist.centres, made.centre_stock, stock_now),
        }
        for target, (places, model, baseline) in sets.items():
            actual = real[target].sum(axis=1)
            for p, place in enumerate(places):
                for k in range(made.weeks):
                    if np.isnan(actual[p, k]):
                        continue
                    rows.append({"origin": origin, "target": target, "place": place, "week_ahead": k + 1,
                                 "actual": float(actual[p, k]), "model": float(model[p].sum(axis=0)[k]),
                                 "baseline": float(baseline[p].sum(axis=0)[k])})
    return pd.DataFrame(rows)


def score(data: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def one(target: str, segment: str, part: pd.DataFrame) -> None:
        total = part["actual"].sum()
        for method in ("baseline", "model"):
            error = (part["actual"] - part[method]).abs()
            rows.append({"target": target, "segment": segment, "method": method, "n": len(part),
                         "actual_units": float(total), "mae": float(error.mean()),
                         "wape": float(error.sum() / total) if total else np.nan,
                         "bias": float((part[method] - part["actual"]).mean())})

    for target, part in data.groupby("target"):
        one(target, "all weeks ahead", part)
        for week, by_week in part.groupby("week_ahead"):
            one(target, f"{week} week{'s' if week > 1 else ''} ahead", by_week)
    return pd.DataFrame(rows)


def run(db_path: Path | None = None, write_docs: bool = True, verbose: bool = True) -> pd.DataFrame:
    metrics = score(collect(db_path))
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        metrics.to_sql("supply_metric", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()
    from backend.engine.results import write_results

    write_results(db_path, write_docs=write_docs)
    if verbose:
        print("\n".join(results_section(db_path)))
    return metrics


def results_section(db_path: Path | None = None) -> list[str]:
    from backend.db.core import read

    metrics = read("SELECT * FROM supply_metric", path=db_path)
    lines = [
        "## Supply forecast (red cells and whole blood)",
        "",
        "Demand is nearly flat through the year and supply is what swings, so this is where a forecast can "
        "add most. **Test:** the same 16 Mondays, 1 to 4 weeks ahead, all blood groups added up. "
        "The model uses the drive schedule (never emergency appeals, which are not planned), the usual "
        "yield per kind of venue, the share of collections that become usable units, and the testing wait, "
        "all learned from days before each forecast date.",
        "",
        "- MAE: average units off per place and week. WAPE: total units off divided by the real total.",
        "- Bias: average of forecast minus real. Below zero means the forecast runs low.",
        "",
    ]
    for target, title in TARGETS.items():
        part = metrics[metrics["target"] == target]
        rows = []
        for segment, by_segment in part.groupby("segment", sort=False):
            m = by_segment.set_index("method")
            rows.append({
                "weeks ahead": segment, "checks": int(m.loc["model", "n"]),
                "MAE (baseline)": f"{m.loc['baseline', 'mae']:.1f}", "MAE (model)": f"{m.loc['model', 'mae']:.1f}",
                "WAPE (baseline)": f"{m.loc['baseline', 'wape'] * 100:.0f}%",
                "WAPE (model)": f"{m.loc['model', 'wape'] * 100:.0f}%",
                "bias (baseline)": f"{m.loc['baseline', 'bias']:+.1f}", "bias (model)": f"{m.loc['model', 'bias']:+.1f}",
            })
        table = pd.DataFrame(rows)
        head = "| " + " | ".join(table.columns) + " |"
        rule = "| " + " | ".join("---" for _ in table.columns) + " |"
        body = ["| " + " | ".join(str(v) for v in row) + " |" for row in table.itertuples(index=False)]
        lines += [f"### {title}", "", f"Baseline: {BASELINE_LABEL[target]}.", "", head, rule, *body, ""]
    return lines


if __name__ == "__main__":
    run()
