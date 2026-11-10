"""Write docs/RESULTS.md from the scores saved in the database."""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from backend import config
from backend.db.core import read, table_exists
from backend.engine import models

SEGMENT_TITLES = {
    "component": "By component",
    "group rarity": "Common against rare blood groups",
    "facility type": "By facility type (our fairness check: no kind of hospital should be served clearly worse)",
    "region": "By region",
}


def _label(model_name: str) -> str:
    module = models.REGISTRY.get(model_name)
    return getattr(module, "LABEL", model_name)


def _table(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def forecast_section(metrics: pd.DataFrame) -> list[str]:
    names = [m for m in models.REGISTRY if m in set(metrics["model"])]
    lines: list[str] = []

    def block(rows: pd.DataFrame) -> str:
        out = []
        for segment, group in rows.groupby("segment", sort=False):
            by_model = group.set_index("model")
            first = by_model.iloc[0]
            row = {"segment": segment, "units requested": f"{first['units_requested']:,.0f}"}
            for name in names:
                if name not in by_model.index:
                    continue
                m = by_model.loc[name]
                tag = "baseline" if name == "baseline" else "model"
                row[f"MAE ({tag})"] = f"{m['mae']:.3f}"
                row[f"WAPE ({tag})"] = f"{m['wape'] * 100:.1f}%"
                row[f"MASE ({tag})"] = f"{m['mase']:.2f}"
                row[f"7-day WAPE ({tag})"] = f"{m['wape_7day'] * 100:.1f}%"
                row[f"range hit ({tag})"] = f"{m['range_hit'] * 100:.0f}%"
            out.append(row)
        return _table(pd.DataFrame(out))

    lines += ["### All series", "", block(metrics[metrics["segment_type"] == "all"]), ""]
    for segment_type, title in SEGMENT_TITLES.items():
        lines += [f"### {title}", "", block(metrics[metrics["segment_type"] == segment_type]), ""]
    return lines


def verdict_section(metrics: pd.DataFrame, db_path: Path | None = None) -> list[str]:
    """A plain statement of whether the model beat the baseline, and how rare series are handled."""
    if "m1" not in set(metrics["model"]) or "baseline" not in set(metrics["model"]):
        return []
    everything = metrics[metrics["segment_type"] == "all"].set_index("model")
    b, m = everything.loc["baseline"], everything.loc["m1"]
    def verdict(key: str, name: str, pct: bool) -> str:
        fmt = (lambda v: f"{v * 100:.1f}%") if pct else (lambda v: f"{v:.3f}")
        change = (m[key] - b[key]) / b[key] * 100
        word = "better" if change < -0.5 else ("worse" if change > 0.5 else "about the same")
        return f"- {name}: baseline {fmt(b[key])}, model {fmt(m[key])} ({abs(change):.1f}% {word})."
    lines = ["### Did the model beat the baseline?", "",
             verdict("mae", "MAE", False), verdict("wape", "WAPE", True),
             verdict("wape_7day", "7-day WAPE", True), ""]
    wins = sum((m[k] - b[k]) / b[k] < -0.005 for k in ("mae", "wape_7day"))
    if wins == 2:
        lines.append("**Plainly:** the model beats the 4-week average on demand, by a small margin. Demand in this "
                     "dataset is nearly flat through the year, so there is little for any model to find. "
                     "The larger gain is in the supply forecast below.")
    elif wins == 0:
        lines.append("**Plainly:** the model does not beat the 4-week average on demand. Demand in this dataset is "
                     "nearly flat through the year. The gain is in the supply forecast below.")
    else:
        lines.append("**Plainly:** the result is mixed. The model is better on one measure and not on the other. "
                     "Demand in this dataset is nearly flat through the year; the clearer gain is in the supply "
                     "forecast below.")
    lines.append("")
    if table_exists("model_note", db_path):
        note = read("SELECT key, value FROM model_note", path=db_path).set_index("key")["value"]
        lines += [
            "### Rare series", "",
            f"A series is rare when at least three quarters of its last 26 weeks had no request "
            f"({float(note['rare_share']) * 100:.0f}% of series). We do not chase precision on these. "
            f"On {len(ast.literal_eval(note['dates']))} dates before the test window, the baseline had MAE "
            f"{float(note['mae_baseline']):.4f} on rare series and the pooled model {float(note['mae_model']):.4f}, "
            f"so rare series use the **{note['in_use']}**"
            + ("" if note["in_use"] == note["better"] else f" (the other option, {note['better']}, scored better)")
            + ". The staff-set minimum stock protects these groups.", "",
        ]
    return lines


def render(db_path: Path | None = None) -> str:
    lines = ["# Results", "", "Written by `python -m backend.pipeline.build`. Do not edit by hand.",
             "All data is the organisers' synthetic starter dataset.", ""]
    if table_exists("backtest_metric", db_path):
        lines += demand_section(db_path)
    if table_exists("supply_metric", db_path):
        from backend.engine.supply_backtest import results_section as supply_section

        lines += supply_section(db_path)
    if table_exists("alert_metric", db_path):
        from backend.engine.alert_backtest import results_section

        lines += results_section(db_path)
    if table_exists("allocation_replay", db_path):
        from backend.engine.allocation import results_section as allocation_section

        lines += allocation_section(db_path)
    return "\n".join(lines)


def demand_section(db_path: Path | None = None) -> list[str]:
    settings = config.load_settings("thresholds")
    metrics = read("SELECT * FROM backtest_metric", path=db_path)
    names = [m for m in models.REGISTRY if m in set(metrics["model"])]
    return [
        "## Demand forecast",
        "",
        f"**Test:** weekly forecast dates from {settings['backtest']['first_origin']} to "
        f"{settings['backtest']['last_origin']} (16 Mondays, covering the August school holiday and term 3). "
        f"On each date the forecast sees only earlier days and predicts units requested for the next "
        f"{settings['forecast']['horizon_days']} days, for every hospital, component and blood group "
        "(32 hospitals x 3 components x 8 groups = 768 series).",
        "",
        "**Models:** " + "; ".join(f"`{n}` = {_label(n)}" for n in names) + ".",
        "",
        "**How to read the scores.** Lower is better for all but the last.",
        "- MAE: average units off, per series and day.",
        "- WAPE: total units off divided by total units requested. Daily demand per series is mostly zero, "
        "so daily WAPE is high for any method.",
        "- MASE: error divided by the error of \"same as this weekday last week\". Below 1 beats that naive rule.",
        "- 7-day WAPE: the same, on totals for the first 7 days. Orders follow delivery cycles, so this is "
        "closer to how the forecast is used.",
        "- Range hit: share of days where real demand fell inside the forecast's p10 to p90 range. "
        "A well-set range hits about 80%.",
        "",
        *forecast_section(metrics),
        *verdict_section(metrics, db_path),
    ]


def write_results(db_path: Path | None = None, write_docs: bool = True) -> str:
    text = render(db_path)
    if write_docs:
        (config.DOCS_DIR / "RESULTS.md").write_text(text + "\n", encoding="utf-8")
    return text
