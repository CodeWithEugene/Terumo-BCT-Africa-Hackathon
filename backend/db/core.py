"""Small helpers around the local SQLite database (the system of record)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd

from backend import config


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, always close."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def read(sql: str, params: tuple | dict = (), parse_dates: list[str] | None = None,
         path: Path | None = None) -> pd.DataFrame:
    """Run a query and return a DataFrame."""
    with session(path) as conn:
        return pd.read_sql_query(sql, conn, params=params, parse_dates=parse_dates)


def table_exists(name: str, path: Path | None = None) -> bool:
    if not (path or config.DB_PATH).exists():
        return False
    with session(path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    return row is not None
