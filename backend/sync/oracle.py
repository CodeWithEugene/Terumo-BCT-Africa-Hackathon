"""Optional one-way copy of aggregates and the audit log to Oracle Autonomous Database.

Run from the repo root:   python -m backend.sync.oracle

The app never needs this. If the settings are missing, the command says so
and exits cleanly. What is sent:
- weekly demand per hospital, product and blood group (never single requests);
- daily shelf counts per hospital, product and blood group;
- the accuracy scores;
- decisions and the audit log, with staff names replaced by codes.

Settings come from the environment or a local ".env" file (never committed):
ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN, ORACLE_WALLET_DIR, ORACLE_WALLET_PASSWORD.
The connection uses python-oracledb in thin mode with the wallet (mutual TLS).
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from backend import config
from backend.db.app_tables import get_setting, set_setting
from backend.db.core import read, table_exists

REQUIRED = ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN", "ORACLE_WALLET_DIR", "ORACLE_WALLET_PASSWORD")
PREFIX = "SP_"


def staff_code(username: str | None, salt: str) -> str | None:
    """A stable code for a member of staff, so the central copy holds no names."""
    if username is None or (isinstance(username, float) and pd.isna(username)):
        return None
    return "staff_" + hashlib.sha256((salt + str(username)).encode()).hexdigest()[:12]


def prepare_tables(db_path: Path | None = None) -> dict[str, pd.DataFrame]:
    """Everything that would be sent, as tables. Nothing request-level and no names."""
    salt = get_setting("session_secret", "", db_path)        # local only; never sent
    tables: dict[str, pd.DataFrame] = {}
    tables["DEMAND_WEEKLY"] = read(
        "SELECT facility_id, component, blood_group, strftime('%Y-%W', date) AS year_week, "
        "SUM(units_requested) AS units_requested, SUM(units_issued) AS units_issued, "
        "SUM(shortage_requests) AS shortage_requests FROM demand_daily GROUP BY 1, 2, 3, 4", path=db_path)
    tables["STOCK_DAILY"] = read(
        "SELECT date AS stock_date, facility_id, component, blood_group, units FROM stock_daily", path=db_path)
    for name in ("backtest_metric", "supply_metric", "alert_metric"):
        if table_exists(name, db_path):
            tables[name.upper()] = read(f"SELECT * FROM {name}", path=db_path)
    if table_exists("decision", db_path):
        decision = read("SELECT * FROM decision", path=db_path)
        decision["staff_code"] = decision["username"].map(lambda u: staff_code(u, salt))
        tables["DECISION"] = decision.drop(columns=["username", "display_name", "user_id", "note"])
        audit = read("SELECT * FROM audit_log", path=db_path)
        audit["staff_code"] = audit["username"].map(lambda u: staff_code(u, salt))
        tables["AUDIT_LOG"] = audit.drop(columns=["username", "user_id", "note"])
    for frame in tables.values():
        frame.columns = [c.upper().replace(" ", "_") for c in frame.columns]
    return tables


def missing_settings() -> list[str]:
    return [name for name in REQUIRED if not os.environ.get(name)]


def _oracle_type(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series) or pd.api.types.is_float_dtype(series) or pd.api.types.is_bool_dtype(series):
        return "NUMBER"
    longest = int(series.dropna().astype(str).str.len().max()) if series.notna().any() else 1
    return "CLOB" if longest > 2000 else "VARCHAR2(2000)"


def push(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace each central table with the current local copy."""
    import oracledb  # imported here so the app runs without this optional package

    wallet = os.environ["ORACLE_WALLET_DIR"]
    connection = oracledb.connect(
        user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"], dsn=os.environ["ORACLE_DSN"],
        config_dir=wallet, wallet_location=wallet, wallet_password=os.environ["ORACLE_WALLET_PASSWORD"])
    sent: dict[str, int] = {}
    try:
        cursor = connection.cursor()
        for name, frame in tables.items():
            table = PREFIX + name
            columns = ", ".join(f'"{c}" {_oracle_type(frame[c])}' for c in frame.columns)
            try:
                cursor.execute(f"CREATE TABLE {table} ({columns})")
            except oracledb.DatabaseError as error:
                if "ORA-00955" not in str(error):       # 955: the table already exists
                    raise
            cursor.execute(f"DELETE FROM {table}")
            marks = ", ".join(f":{i + 1}" for i in range(len(frame.columns)))
            names = ", ".join(f'"{c}"' for c in frame.columns)
            rows = [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in row)
                    for row in frame.itertuples(index=False, name=None)]
            for start in range(0, len(rows), 5000):
                cursor.executemany(f"INSERT INTO {table} ({names}) VALUES ({marks})", rows[start:start + 5000])
            sent[table] = len(rows)
        connection.commit()
    finally:
        connection.close()
    return sent


def main() -> int:
    missing = missing_settings()
    if missing:
        print("Central database sync is not set up, so nothing was sent. The app works without it.")
        print("To switch it on, set these in your .env file: " + ", ".join(missing))
        return 0
    if not config.DB_PATH.exists():
        print("The local database has not been built yet. Run: python -m backend.pipeline.build")
        return 0
    try:
        import oracledb  # noqa: F401
    except ImportError:
        print("The Oracle driver is not installed. Run: pip install oracledb")
        return 0
    tables = prepare_tables()
    try:
        sent = push(tables)
    except Exception as error:  # noqa: BLE001  (say what failed without printing any setting)
        print(f"The sync failed and nothing was changed locally: {type(error).__name__}: {str(error)[:200]}")
        return 1
    for table, rows in sent.items():
        print(f"  {table:<22}{rows:>9,} rows")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_setting("last_central_sync", stamp)
    print(f"Synced to the central database at {stamp}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
