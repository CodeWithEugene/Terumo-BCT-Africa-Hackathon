"""Build the calendar table from the settings file (school terms, holidays, malaria season)."""
from __future__ import annotations

import pandas as pd

from backend import config


def school_breaks(settings: dict | None = None) -> pd.DataFrame:
    settings = settings or config.calendar_settings()
    breaks = pd.DataFrame(settings["school_breaks"])
    breaks["start"] = pd.to_datetime(breaks["start"])
    breaks["end"] = pd.to_datetime(breaks["end"])
    breaks["days"] = (breaks["end"] - breaks["start"]).dt.days + 1
    return breaks


def build_calendar(regions: list[str], settings: dict | None = None) -> pd.DataFrame:
    """One row per date and region.

    Columns: date, region, school_in_session, school_break_name, public_holiday,
    holiday_name, days_to_next_school_break, malaria_season.
    """
    settings = settings or config.calendar_settings()
    days = pd.DataFrame({"date": pd.date_range(str(settings["first_date"]), str(settings["last_date"]))})

    breaks = school_breaks(settings)
    days["school_break_name"] = None
    for row in breaks.itertuples():
        inside = days["date"].between(row.start, row.end)
        days.loc[inside, "school_break_name"] = row.name
    days["school_in_session"] = days["school_break_name"].isna().astype(int)

    # Count down to the next long break. Zero while inside one.
    long_breaks = breaks[breaks["days"] >= settings.get("min_break_days_for_countdown", 14)]
    countdown = []
    for date in days["date"]:
        if ((long_breaks["start"] <= date) & (date <= long_breaks["end"])).any():
            countdown.append(0)
            continue
        ahead = long_breaks.loc[long_breaks["start"] > date, "start"]
        countdown.append(int((ahead.min() - date).days) if len(ahead) else 999)
    days["days_to_next_school_break"] = countdown

    holidays = pd.DataFrame(settings["public_holidays"])
    holidays["date"] = pd.to_datetime(holidays["date"])
    days = days.merge(holidays.rename(columns={"name": "holiday_name"}), on="date", how="left")
    days["public_holiday"] = days["holiday_name"].notna().astype(int)

    malaria = settings.get("malaria_season_months", {})
    frames = []
    for region in regions:
        frame = days.copy()
        frame["region"] = region
        frame["malaria_season"] = frame["date"].dt.month.isin(malaria.get(region, [])).astype(int)
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    return out[["date", "region", "school_in_session", "school_break_name", "public_holiday",
                "holiday_name", "days_to_next_school_break", "malaria_season"]]
