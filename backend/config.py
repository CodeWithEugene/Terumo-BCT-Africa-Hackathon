"""Paths and settings shared by the whole backend.

Country- and site-specific settings live in YAML files under ``config/`` so the
tool can be set up for another country without changing code.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Read KEY=value lines from a local .env file, if there is one.

    Values already set in the environment win. The file is never printed or logged.
    """
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()
RAW_DIR = ROOT / "data" / "raw"
CONFIG_DIR = ROOT / "config"
DOCS_DIR = ROOT / "docs"
DB_PATH = Path(os.environ.get("SP_DB_PATH", ROOT / "data" / "app.db"))

APP_NAME = "Providus"


@lru_cache(maxsize=None)
def load_settings(name: str) -> dict[str, Any]:
    """Read ``config/<name>.yaml`` once and return it as a dictionary."""
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def calendar_settings() -> dict[str, Any]:
    """The calendar file named in ``config/site.yaml``."""
    return load_settings(load_settings("site").get("calendar_file", "calendar_ke"))
