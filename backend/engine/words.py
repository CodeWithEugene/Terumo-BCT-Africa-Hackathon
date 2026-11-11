"""Small helpers that turn values into plain words."""
from __future__ import annotations

import pandas as pd

GROUP_WORDS = {"+": "positive", "-": "negative"}


def group_words(group: str) -> str:
    """'O-' -> 'O negative'."""
    return f"{group[:-1]} {GROUP_WORDS[group[-1]]}"


def group_symbol(group: str) -> str:
    """'O-' -> 'O−' with a true minus sign."""
    return group.replace("-", "−")


def day(date) -> str:
    """'Fri 7 Aug'."""
    date = pd.Timestamp(date)
    return f"{date:%a} {date.day} {date:%b}"


def units(value: float) -> str:
    """'1 unit', '3 units', '2.5 units'."""
    rounded = round(float(value), 1)
    text = f"{rounded:.0f}" if abs(rounded - round(rounded)) < 1e-9 else f"{rounded:.1f}"
    return f"{text} unit" if text == "1" else f"{text} units"


def days(value: float) -> str:
    rounded = round(float(value), 1)
    text = f"{rounded:.0f}" if abs(rounded - round(rounded)) < 1e-9 else f"{rounded:.1f}"
    return f"{text} day" if text == "1" else f"{text} days"


PRODUCT_WORDS = {"RBC": "red cells", "FFP": "plasma", "PLT": "platelets"}
