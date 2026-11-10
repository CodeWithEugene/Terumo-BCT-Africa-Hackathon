"""Everything the engine needs, loaded once from the local database and kept in memory."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend import config
from backend.db.core import read
from backend.engine.demand import DemandPanel, load_panel


@dataclass
class World:
    panel: DemandPanel
    facility: pd.DataFrame          # indexed by facility_id
    stock: pd.DataFrame             # date, facility_id, product, component, blood_group, units
    delivery: pd.DataFrame          # arrivals, with product
    unit: pd.DataFrame              # units with product
    unit_move: pd.DataFrame
    calendar: pd.DataFrame          # indexed by (region, date)
    emergency: pd.DataFrame
    drive: pd.DataFrame
    product_of: dict[str, str]      # stock component -> product it fills
    first_date: pd.Timestamp
    last_date: pd.Timestamp


def product_map() -> dict[str, str]:
    products = config.load_settings("blood")["products"]
    return {component: product for product, spec in products.items() for component in spec["filled_by"]}


def load_world(db_path: Path | None = None) -> World:
    product_of = product_map()
    stock = read("SELECT * FROM stock_daily", parse_dates=["date"], path=db_path)
    stock["product"] = stock["component"].map(product_of)
    delivery = read("SELECT * FROM delivery", parse_dates=["date"], path=db_path)
    delivery["product"] = delivery["component"].map(product_of)
    unit = read("SELECT unit_id, component, blood_group, expiry_date, processed_at_id, status, status_date, "
                "available_date FROM unit", parse_dates=["expiry_date", "status_date", "available_date"],
                path=db_path)
    unit["product"] = unit["component"].map(product_of)
    move = read("SELECT unit_id, to_facility_id, dispatched_at, received_at FROM unit_move",
                parse_dates=["dispatched_at", "received_at"], path=db_path)
    move["at"] = move["received_at"].fillna(move["dispatched_at"])
    calendar = read("SELECT * FROM calendar", parse_dates=["date"], path=db_path).set_index(["region", "date"]).sort_index()
    return World(
        panel=load_panel(db_path),
        facility=read("SELECT * FROM facility", path=db_path).set_index("facility_id"),
        stock=stock, delivery=delivery, unit=unit, unit_move=move.sort_values("at"), calendar=calendar,
        emergency=read("SELECT * FROM emergency_resupply", parse_dates=["date"], path=db_path),
        drive=read("SELECT * FROM drive", parse_dates=["date"], path=db_path),
        product_of=product_of,
        first_date=stock["date"].min(), last_date=stock["date"].max(),
    )


@lru_cache(maxsize=2)
def _cached(path: str, modified: float) -> World:
    return load_world(Path(path))


def get_world(db_path: Path | None = None) -> World:
    """The shared in-memory copy. Reloads if the database file has been rebuilt."""
    path = db_path or config.DB_PATH
    return _cached(str(path), path.stat().st_mtime)
