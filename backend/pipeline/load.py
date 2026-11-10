"""Read the raw CSV files. Only the files listed here may ever be loaded.

The donor table is deliberately not in this list: the product uses no donor or
patient identities. The donor reference column inside the donations file is
also never read.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend import config

ALLOWED_FILES = (
    "facilities", "routes", "drives", "donations", "units",
    "transfers", "requests", "daily_stock", "power_outages", "temperature_logs",
)

# Columns that identify or describe a person. Dropped at the door.
NEVER_READ = {
    "donations": {"donor_id"},
    "requests": {"patient_sex", "patient_age_band", "clinical_indication", "facility_name_raw"},
}

DATE_COLUMNS = {
    "drives": ["date"],
    "donations": ["collection_date", "tested_date"],
    "units": ["collection_date", "expiry_date", "status_date"],
    "transfers": ["dispatched_at", "received_at"],
    "requests": ["requested_at", "last_unit_available_at"],
    "daily_stock": ["date"],
    "power_outages": ["start_time", "end_time"],
    "temperature_logs": ["recorded_at"],
}


def load(name: str, raw_dir: Path | None = None) -> pd.DataFrame:
    """Load one allowed raw file, without any person-level columns."""
    if name not in ALLOWED_FILES:
        raise ValueError(f"'{name}' is not a file this product is allowed to load.")
    blocked = NEVER_READ.get(name, set())
    return pd.read_csv(
        (raw_dir or config.RAW_DIR) / f"{name}.csv",
        usecols=lambda column: column not in blocked,
        parse_dates=DATE_COLUMNS.get(name, []),
    )
