"""Write docs/RESULTS.md from the scores saved in the database."""
from __future__ import annotations

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


def render(db_path: Path | None = None) -> str:
    settings = config.load_settings("thresholds")
    metrics = read("SELECT * FROM backtest_metric", path=db_path)
    names = [m for m in models.REGISTRY if m in set(metrics["model"])]
    lines = [
        "# Results",
        "",
        "Written by `python -m backend.engine.backtest`. Do not edit by hand.",
        "All data is the organisers' synthetic starter dataset.",
        "",
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
    ]
    if table_exists("supply_metric", db_path):
        from backend.engine.supply_backtest import results_section as supply_section

        lines += supply_section(db_path)
    if table_exists("alert_metric", db_path):
        from backend.engine.alert_backtest import results_section

        lines += results_section(db_path)
    return "\n".join(lines)


def write_results(db_path: Path | None = None, write_docs: bool = True) -> str:
    text = render(db_path)
    if write_docs:
        (config.DOCS_DIR / "RESULTS.md").write_text(text + "\n", encoding="utf-8")
    return text
