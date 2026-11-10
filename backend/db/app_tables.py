"""Tables the app writes to: users, decisions, the audit log and settings.

These are created once and survive a rebuild of the data tables.
The audit log is append-only: the database itself refuses updates and deletes.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

from backend import config
from backend.db.core import session

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision (
    decision_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    as_of TEXT NOT NULL,
    series_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    component TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    suggestion_kind TEXT NOT NULL,
    for_date TEXT,
    status_seen TEXT NOT NULL,
    suggested_quantity INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('accept', 'change', 'reject')),
    final_quantity INTEGER NOT NULL,
    reason_code TEXT,
    note TEXT,
    mode TEXT NOT NULL,
    withdrawn_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    user_id INTEGER,
    username TEXT,
    role TEXT,
    event TEXT NOT NULL,
    facility_id TEXT,
    series_id TEXT,
    as_of TEXT,
    saw TEXT,
    decided TEXT,
    reason_code TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS app_setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'The audit log is append-only.'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'The audit log is append-only.'); END;
"""


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def check_password(password: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected)


def ensure_app_tables(db_path: Path | None = None) -> None:
    """Create the app tables and the test log-ins if they are not there yet."""
    access = config.load_settings("access")
    with session(db_path) as conn:
        conn.executescript(SCHEMA)
        for user in access["demo_users"]:
            if conn.execute("SELECT 1 FROM app_user WHERE username = ?", (user["username"],)).fetchone():
                continue
            salt = secrets.token_hex(16)
            conn.execute(
                "INSERT INTO app_user (username, display_name, role, facility_id, salt, password_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user["username"], user["display_name"], user["role"], user["facility_id"], salt,
                 hash_password(user["demo_password"], salt)))
        if not conn.execute("SELECT 1 FROM app_setting WHERE key = 'session_secret'").fetchone():
            conn.execute("INSERT INTO app_setting VALUES ('session_secret', ?)", (secrets.token_hex(32),))
        conn.execute("INSERT OR IGNORE INTO app_setting VALUES ('force_baseline', '0')")


def get_setting(key: str, default: str = "", db_path: Path | None = None) -> str:
    with session(db_path) as conn:
        row = conn.execute("SELECT value FROM app_setting WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str, db_path: Path | None = None) -> None:
    with session(db_path) as conn:
        conn.execute("INSERT INTO app_setting VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value))
