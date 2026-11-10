"""The web API. Run with: python -m uvicorn backend.api.main:app --port 8000"""
from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend import config
from backend.api import auth, security, service, standards
from backend.api.auth import User, current_user
from backend.config import APP_NAME, DB_PATH
from backend.db.app_tables import ensure_app_tables, set_setting
from backend.db.core import table_exists

app = FastAPI(title=APP_NAME, docs_url="/api/docs", openapi_url="/api/openapi.json")

app.middleware("http")(security.security_middleware)

Component = Literal["RBC", "FFP", "PLT"]


def ready() -> None:
    """Refuse data requests until the database has been built."""
    if not table_exists("demand_daily"):
        raise HTTPException(status_code=503,
                            detail="The database has not been built yet. Run: python -m backend.pipeline.build")
    if not table_exists("app_user"):
        ensure_app_tables()


@app.get("/api/health")
def health() -> dict:
    """Say whether the server is up and whether the local database has been built."""
    built = table_exists("demand_daily")
    info = service.mode_info() if built and table_exists("app_setting") else {"mode": "fallback"}
    return {"status": "ok", "app": APP_NAME, "database_built": built, **info}


@app.get("/api/public-facts", dependencies=[Depends(ready)])
def public_facts() -> dict:
    """A few headline numbers for the landing page, all computed by the pipeline (docs/DATA_FACTS.md)."""
    from backend.db.core import read

    wanted = ("requests", "requests_not_fully_met_pct", "emergency_median_hours", "red_cell_wastage_pct",
              "collections_drop_in_breaks_pct", "hospitals", "first_date", "last_date")
    facts = read("SELECT key, value FROM data_fact").set_index("key")["value"]
    return {key: facts[key] for key in wanted if key in facts.index}


# --- Sign-in ---------------------------------------------------------------------

class Login(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=200)


@app.get("/api/demo-users", dependencies=[Depends(ready)])
def demo_users() -> dict:
    """The test log-ins, shown on the sign-in screen. Demo only; switch off with SP_DEMO_LOGINS=0."""
    if not security.demo_logins_enabled():
        return {**service.mode_info(), "users": []}
    access = config.load_settings("access")
    world_names = service.get_world().facility["name"]
    return {**service.mode_info(), "users": [
        {"username": u["username"], "display_name": u["display_name"], "role": u["role"],
         "role_label": access["roles"][u["role"]]["label"], "facility_name": world_names[u["facility_id"]],
         "demo_password": u["demo_password"]} for u in access["demo_users"]]}


@app.post("/api/login", dependencies=[Depends(ready)])
def login(body: Login, request: Request, response: Response) -> dict:
    if security.too_many_failures(body.username, request):
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Wait 5 minutes and try again.")
    user = auth.authenticate(body.username, body.password)
    if user is None:
        security.record_failure(body.username, request)
        raise HTTPException(status_code=401, detail="That name and password do not match.")
    security.clear_failures(body.username, request)
    hours = config.load_settings("access")["session_hours"]
    response.set_cookie(auth.COOKIE, auth.make_cookie(user.user_id), max_age=hours * 3600,
                        httponly=True, samesite="lax", secure=security.cookie_secure())
    service.audit(user, "sign_in")
    return {**service.mode_info(), "user": service.user_card(user)}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE)
    return {"signed_out": True}


@app.get("/api/me", dependencies=[Depends(ready)])
def me(user: User = Depends(current_user)) -> dict:
    return {**service.mode_info(), "user": service.user_card(user)}


# --- The morning brief -------------------------------------------------------------

@app.get("/api/asof-dates", dependencies=[Depends(ready)])
def asof_dates() -> dict:
    return {**service.mode_info(), **service.as_of_dates()}


@app.get("/api/brief", dependencies=[Depends(ready)])
def brief(as_of: str | None = None, facility_id: str | None = None, component: Component = "RBC",
          user: User = Depends(current_user)) -> dict:
    return service.brief(user, as_of, facility_id, component)


@app.get("/api/overview", dependencies=[Depends(ready)])
def overview(as_of: str | None = None, component: Component = "RBC", user: User = Depends(current_user)) -> dict:
    return service.overview(user, as_of, component)


@app.get("/api/region", dependencies=[Depends(ready)])
def region(as_of: str | None = None, extra_donors: int | None = None, extra_date: str | None = None,
           user: User = Depends(current_user)) -> dict:
    return service.region(user, as_of, extra_donors, extra_date)


@app.get("/api/series/{series_id:path}", dependencies=[Depends(ready)])
def series(series_id: str, as_of: str | None = None, user: User = Depends(current_user)) -> dict:
    return service.series_detail(user, series_id, as_of)


# --- Decisions and the audit log ---------------------------------------------------

class DecisionIn(BaseModel):
    series_id: str
    as_of: str | None = None
    action: Literal["accept", "change", "reject"]
    quantity: int | None = Field(default=None, ge=0, le=500)
    reason_code: str | None = None
    note: str | None = Field(default=None, max_length=500)


@app.get("/api/reason-codes")
def reason_codes() -> dict:
    return config.load_settings("access")["reason_codes"]


@app.post("/api/decisions", dependencies=[Depends(ready)])
def post_decision(body: DecisionIn, user: User = Depends(current_user)) -> dict:
    return service.record_decision(user, body.model_dump())


@app.post("/api/decisions/{decision_id}/undo", dependencies=[Depends(ready)])
def undo_decision(decision_id: int, user: User = Depends(current_user)) -> dict:
    return service.undo_decision(user, decision_id)


@app.get("/api/decisions", dependencies=[Depends(ready)])
def get_decisions(facility_id: str | None = None, action: Literal["accept", "change", "reject"] | None = None,
                  user: User = Depends(current_user)) -> dict:
    return service.list_decisions(user, facility_id, action)


@app.get("/api/audit", dependencies=[Depends(ready)])
def get_audit(user: User = Depends(current_user)) -> dict:
    return service.audit_entries(user)


# --- Accuracy and the fallback switch ------------------------------------------------

@app.get("/api/accuracy", dependencies=[Depends(ready)])
def accuracy(user: User = Depends(current_user)) -> dict:
    return service.accuracy()


class Fallback(BaseModel):
    use_baseline: bool


@app.post("/api/fallback", dependencies=[Depends(ready)])
def fallback(body: Fallback, user: User = Depends(current_user)) -> dict:
    """Switch between the forecast model and the 4-week average. Logged."""
    set_setting("force_baseline", "1" if body.use_baseline else "0")
    service.audit(user, "fallback_switch", decided={"use_baseline": body.use_baseline})
    return service.mode_info()


# --- Standards and privacy ---------------------------------------------------------------

@app.get("/fhir/SupplyRequest/{decision_id}", dependencies=[Depends(ready)])
def fhir_supply_request(decision_id: int, user: User = Depends(current_user)) -> dict:
    """An accepted order as a FHIR R4-shaped SupplyRequest."""
    return standards.supply_request(user, decision_id)


@app.get("/export/dhis2", dependencies=[Depends(ready)])
def export_dhis2(user: User = Depends(current_user)) -> dict:
    """Monthly aggregates in the shape of a DHIS2 dataValueSet (illustrative IDs)."""
    return standards.dhis2_export(user)


@app.get("/api/privacy", dependencies=[Depends(ready)])
def privacy(user: User = Depends(current_user)) -> dict:
    return service.privacy(user)
