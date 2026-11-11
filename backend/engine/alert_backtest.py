"""Alert check: did a warning come before a real shortage?

Run from the repo root:
    python -m backend.engine.alert_backtest

For every weekly test date and every series a hospital holds (red cells and
plasma), we ask: in the next 7 days, was a request not fully met, or did one
need an emergency delivery? (A zero-stock day alone is not a shortage.) Then we
compare two ways of warning:
- our alert (status Act or Watch from the stock projection);
- the simple rule: cover under X days, using the 28-day average demand.

Scores: recall (share of real shortages that had a warning), precision (share
of warnings followed by a real shortage) and the median number of days between
the warning and the first unmet request.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from backend import config
from backend.engine import backtest, models
from backend.engine.projection import build_snapshot, series_view
from backend.engine.world import get_world

RULES = {
    "ours": "Our alert (Act or Watch), deliveries from the supply forecast",
    "ours_act": "Our alert (Act only), deliveries from the supply forecast",
    "ours_usual": "Our alert (Act or Watch), usual deliveries",
    "simple": "Simple rule (cover under {x:g} days on the 28-day average)",
}


def collect(model: str, db_path: Path | None = None, origin_dates=None) -> pd.DataFrame:
    """One row per test date and held series: the flags and what really happened."""
    world = get_world(db_path)
    panel = world.panel
    alerts = config.load_settings("thresholds")["alerts"]
    window, rule_days = alerts["event_window_days"], alerts["baseline_rule_cover_days"]
    rows = []
    for origin in (origin_dates if origin_dates is not None else backtest.origins()):
        snap = build_snapshot(world, origin, model, use_supply=True)
        plain = build_snapshot(world, origin, model, use_supply=False)
        cut = panel.position(origin)
        average = panel.requested[cut - 28:cut].mean(axis=0)
        shortage = panel.shortage[cut:cut + window]
        unmet = panel.unmet[cut:cut + window]
        for index, row in panel.series.iterrows():
            if (row["facility_id"], row["component"]) not in snap.held:
                continue
            view = series_view(snap, index, detail=False)
            shelf = snap.shelf.get((row["facility_id"], row["component"], row["blood_group"]), 0.0)
            hit_days = np.nonzero(shortage[:, index] > 0)[0]
            rows.append({
                "origin": origin, "series": index, "component": row["component"],
                "facility type": row["facility_type"],
                "ours": view["status"] in ("act", "watch"), "ours_act": view["status"] == "act",
                "ours_usual": series_view(plain, index, detail=False)["status"] in ("act", "watch"),
                "simple": bool(average[index] > 0 and shelf / average[index] < rule_days),
                "chance": view.get("stockout_chance_7_days", 0.0),
                "event": len(hit_days) > 0,
                "event_unmet_only": bool((unmet[:, index] > 0).any()),
                "lead_days": int(hit_days[0]) if len(hit_days) else np.nan,
            })
    out = pd.DataFrame(rows)
    out["model"] = snap.forecast.model
    return out


def score(flags: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def one(segment_type: str, segment: str, data: pd.DataFrame) -> None:
        events = int(data["event"].sum())
        for rule in RULES:
            alerts = int(data[rule].sum())
            hits = data[data[rule] & data["event"]]
            rows.append({
                "model": data["model"].iloc[0], "rule": rule, "segment_type": segment_type, "segment": segment,
                "checks": len(data), "events": events, "alerts": alerts, "hits": len(hits),
                "recall": len(hits) / events if events else np.nan,
                "precision": len(hits) / alerts if alerts else np.nan,
                "median_lead_days": float(hits["lead_days"].median()) if len(hits) else np.nan,
            })

    one("all", "all held series", flags)
    one("strict", "all held series", flags.assign(event=flags["event_unmet_only"]))
    # Is the stated chance of running out honest? Group checks by the chance given, and count what happened.
    bands = pd.cut(flags["chance"], [-0.01, 0.2, 0.5, 0.8, 1.0], labels=["under 20%", "20 to 50%", "50 to 80%", "over 80%"])
    for band, part in flags.groupby(bands, observed=True):
        rows.append({"model": flags["model"].iloc[0], "rule": "chance", "segment_type": "chance", "segment": str(band),
                     "checks": len(part), "events": int(part["event"].sum()), "alerts": len(part), "hits": int(part["event"].sum()),
                     "recall": float(part["chance"].mean()), "precision": float(part["event"].mean()),
                     "median_lead_days": np.nan})
    for segment_type in ("component", "facility type"):
        for name, group in flags.groupby(segment_type):
            one(segment_type, name, group)
    return pd.DataFrame(rows)


def run(model: str = "auto", db_path: Path | None = None, write_docs: bool = True, verbose: bool = True) -> pd.DataFrame:
    flags = collect(model, db_path)
    metrics = score(flags)
    name = metrics["model"].iloc[0]
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        from backend.db.core import replace_model_rows

        replace_model_rows(conn, "alert_metric", metrics, name)
        conn.commit()
    finally:
        conn.close()
    from backend.engine.results import write_results

    text = write_results(db_path, write_docs=write_docs)
    if verbose:
        print("\n".join(results_section(db_path)))
    return metrics


def _table(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def results_section(db_path: Path | None = None) -> list[str]:
    from backend.db.core import read

    alerts = config.load_settings("thresholds")["alerts"]
    metrics = read("SELECT * FROM alert_metric", path=db_path)
    names = [m for m in models.REGISTRY if m in set(metrics["model"])]
    lines = [
        "## Stock-out early warning",
        "",
        f"**Test:** the same 16 Mondays. For every series a hospital holds (red cells and plasma; hospitals "
        f"hold no platelets): in the next {alerts['event_window_days']} days, was a request not fully met, "
        "or did one need an emergency delivery? A zero-stock day is not counted as a shortage on its own, "
        "because many shelves are often empty in this dataset.",
        "",
        "- Recall: of the real shortages, the share that had a warning. Higher is better.",
        "- Precision: of the warnings, the share followed by a real shortage. Higher means fewer false alarms.",
        "- Lead: median days from the warning to the first such request.",
        "",
    ]

    def fmt(value: float, pct: bool = True) -> str:
        if pd.isna(value):
            return "n/a"
        return f"{value * 100:.0f}%" if pct else f"{value:g}"

    chance = metrics[(metrics["segment_type"] == "chance") & (metrics["model"] == names[-1])]
    if len(chance):
        lines += ["### Is the stated chance of running out honest?", "",
                  f"Each alert states a chance of running out within 7 days (forecast: {names[-1]}). "
                  "If it is honest, the share that really ran short should be close to the chance given.", "",
                  "| chance given | checks | average chance given | really ran short |", "| --- | --- | --- | --- |"]
        for row in chance.itertuples():
            lines.append(f"| {row.segment} | {row.checks:,} | {row.recall * 100:.0f}% | {row.precision * 100:.0f}% |")
        lines.append("")
    for segment_type, title in (("all", "All held series"),
                                ("strict", "Stricter check: only requests that were not fully met"),
                                ("component", "By component"), ("facility type", "By facility type")):
        rows = []
        part = metrics[(metrics["segment_type"] == segment_type) & (metrics["rule"] != "chance")]
        for segment, by_segment in part.groupby("segment", sort=False):
            for name in names:
                for rule, label in RULES.items():
                    if rule == "simple" and name != names[0]:
                        continue                      # the simple rule does not depend on the forecast
                    if rule in ("ours_act", "ours_usual") and segment_type not in ("all", "strict"):
                        continue
                    m = by_segment[(by_segment["model"] == name) & (by_segment["rule"] == rule)]
                    if m.empty:
                        continue
                    m = m.iloc[0]
                    who = label.format(x=alerts["baseline_rule_cover_days"])
                    if rule != "simple":
                        who += f", forecast: {name}"
                    rows.append({"segment": segment, "method": who, "real shortages": int(m["events"]),
                                 "warnings": int(m["alerts"]), "recall": fmt(m["recall"]),
                                 "precision": fmt(m["precision"]),
                                 "lead (days)": fmt(m["median_lead_days"], pct=False)})
        lines += [f"### {title}", "", _table(pd.DataFrame(rows)), ""]
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the alerts against what really happened.")
    parser.add_argument("--model", default="auto")
    run(parser.parse_args().model)
