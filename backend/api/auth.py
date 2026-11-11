"""Sign-in, the signed session cookie, and who may see which hospital."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from backend import config
from backend.db.app_tables import check_password, get_setting
from backend.db.core import session
from backend.engine.world import get_world

COOKIE = "sp_session"


@dataclass
class User:
    user_id: int
    username: str
    display_name: str
    role: str
    facility_id: str

    @property
    def role_label(self) -> str:
        return config.load_settings("access")["roles"][self.role]["label"]


def _secret() -> bytes:
    # An environment value wins; otherwise a random secret made when the database was created.
    return (os.environ.get("SP_SESSION_SECRET") or get_setting("session_secret")).encode()


def _sign(body: str) -> str:
    return hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()


def make_cookie(user_id: int) -> str:
    hours = config.load_settings("access")["session_hours"]
    body = base64.urlsafe_b64encode(json.dumps({"u": user_id, "exp": int(time.time()) + hours * 3600}).encode()).decode()
    return f"{body}.{_sign(body)}"


def read_cookie(value: str | None) -> int | None:
    if not value or "." not in value:
        return None
    body, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(_sign(body), signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("exp", 0) < time.time():
        return None
    return int(data["u"])


def find_user(*, user_id: int | None = None, username: str | None = None):
    with session() as conn:
        if user_id is not None:
            return conn.execute("SELECT * FROM app_user WHERE user_id = ?", (user_id,)).fetchone()
        return conn.execute("SELECT * FROM app_user WHERE username = ?", (username,)).fetchone()


def authenticate(username: str, password: str) -> User | None:
    row = find_user(username=username.strip().lower())
    if row is None or not check_password(password, row["salt"], row["password_hash"]):
        return None
    return User(row["user_id"], row["username"], row["display_name"], row["role"], row["facility_id"])


def current_user(request: Request) -> User:
    """FastAPI dependency: the signed-in user, or a 401."""
    user_id = read_cookie(request.cookies.get(COOKIE))
    row = find_user(user_id=user_id) if user_id is not None else None
    if row is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return User(row["user_id"], row["username"], row["display_name"], row["role"], row["facility_id"])


def scope(user: User) -> list[str]:
    """The hospitals this user may see. Enforced on every data request."""
    facility = get_world().facility
    if user.role == "regional_officer":
        hospitals = facility[(facility["kind"] == "hospital") & (facility["supply_centre_id"] == user.facility_id)]
        return sorted(hospitals.index)
    return [user.facility_id]


def require_facility(user: User, facility_id: str | None) -> str:
    """Return a hospital the user may see, or refuse."""
    allowed = scope(user)
    if facility_id is None:
        return allowed[0]
    if facility_id not in allowed:
        raise HTTPException(status_code=403, detail="You do not have access to that hospital.")
    return facility_id
