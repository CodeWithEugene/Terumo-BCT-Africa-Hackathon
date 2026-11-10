"""Print the morning list for one hospital.

Run from the repo root:
    python -m backend.engine.brief --facility HSP-005 --as-of 2026-08-03
"""
from __future__ import annotations

import argparse

from backend import config
from backend.engine import words
from backend.engine.projection import build_snapshot, morning_list
from backend.engine.world import get_world


def summary_sentence(views: list[dict]) -> str:
    """The answer-first line at the top of the brief."""
    held = [v for v in views if v["held"]]
    act = [v for v in held if v["status"] == "act"]
    watch = [v for v in held if v["status"] == "watch"]
    deliveries = sorted({v["next_delivery"]["date"]: v["next_delivery"]["label"]
                         for v in held if v.get("next_delivery")}.items())
    before = f" before {deliveries[0][1]}'s delivery" if deliveries else ""
    count = {1: "One group", 2: "Two groups", 3: "Three groups", 4: "Four groups", 5: "Five groups",
             6: "Six groups", 7: "Seven groups", 8: "All eight groups"}
    if act:
        text = f"{count[len(act)]} {'needs' if len(act) == 1 else 'need'} action{before}"
        if watch:
            text += f", and {count[len(watch)].lower()} {'is' if len(watch) == 1 else 'are'} worth watching"
        return text + "."
    if watch:
        return f"{count[len(watch)]} {'is' if len(watch) == 1 else 'are'} worth watching{before}. Nothing needs action yet."
    if not held:
        return "This product is not held here."
    through = f" through {deliveries[0][1]}" if deliveries else ""
    return f"All {len(held)} groups are steady{through}."


def print_brief(facility_id: str, as_of: str, component: str = "RBC", model: str = "auto") -> None:
    world = get_world()
    snap = build_snapshot(world, as_of, model)
    views = morning_list(snap, facility_id, component)
    name = world.facility.at[facility_id, "name"]
    print(f"\n{name} · {views[0]['component_label']} · as of {words.day(snap.as_of)} {snap.as_of.year}")
    print(f"Forecast: {snap.forecast.model} ({snap.forecast.note})\n")
    print(summary_sentence(views) + "\n")
    print(f"{'Group':<6}{'Status':<8}{'Shelf':>6}{'Cover':>10}{'If busy':>10}  {'Next delivery':<14}{'Suggestion'}")
    for v in views:
        if not v["held"]:
            print(f"{v['blood_group']:<6}{v['status_label']}")
            continue
        cover = "no use" if v["cover_days"] is None else (
            "14+ d" if v["cover_capped"] else f"{v['cover_days']:.1f} d")
        worst = "" if v["worst_cover_days"] is None else f"{v['worst_cover_days']:.1f} d"
        delivery = v["next_delivery"]["label"] if v["next_delivery"] else "none"
        s = v["suggestion"]
        suggestion = "" if s is None else (
            f"{s['title']}: {s['quantity']} (usual {s['usual_quantity']})  [{s['sum_text']}]")
        print(f"{v['blood_group']:<6}{v['status_label']:<8}{v['units_on_shelf']:>6}{cover:>10}{worst:>10}  "
              f"{delivery:<14}{suggestion}")
    print()
    for v in views:
        if v["held"] and v["status"] != "steady":
            print(f"{v['blood_group']} · {v['status_label']}: {v['status_line']}")
            for reason in v["reasons"]:
                print(f"   - {reason['text']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print the morning list for one hospital.")
    parser.add_argument("--facility", default="HSP-005")
    parser.add_argument("--as-of", default=str(config.load_settings("site")["default_as_of"]))
    parser.add_argument("--component", default="RBC", choices=["RBC", "FFP", "PLT"])
    parser.add_argument("--model", default="auto")
    args = parser.parse_args()
    print_brief(args.facility, args.as_of, args.component, args.model)
