"""FHIR and DHIS2 shaped outputs, the privacy facts and the SMS preview."""
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.api.main import app
from backend.db.app_tables import ensure_app_tables

PASSWORDS = {u["username"]: u["demo_password"] for u in config.load_settings("access")["demo_users"]}
FHIR_R4_FIELDS = {"resourceType", "id", "meta", "identifier", "status", "category", "priority", "itemCodeableConcept",
                  "quantity", "occurrenceDateTime", "authoredOn", "requester", "supplier", "reasonCode",
                  "deliverFrom", "deliverTo"}


@pytest.fixture(scope="module", autouse=True)
def tables(db_path):
    ensure_app_tables(db_path)


def signed_in(username: str) -> TestClient:
    client = TestClient(app)
    assert client.post("/api/login", json={"username": username, "password": PASSWORDS[username]}).status_code == 200
    return client


def test_accepted_order_is_served_as_a_fhir_supply_request():
    joseph = signed_in("joseph")
    series = [s for s in joseph.get("/api/brief", params={"as_of": "2026-07-13"}).json()["series"]
              if s["suggestion"] and s["suggestion"]["quantity"] > 0]
    made = joseph.post("/api/decisions", json={"series_id": series[0]["id"], "as_of": "2026-07-13", "action": "accept"})
    decision = made.json()["decision"]
    resource = joseph.get(f"/fhir/SupplyRequest/{decision['decision_id']}").json()
    assert set(resource) <= FHIR_R4_FIELDS and resource["resourceType"] == "SupplyRequest"
    assert resource["status"] == "active" and resource["priority"] in ("routine", "urgent", "asap", "stat")
    assert resource["quantity"]["value"] == decision["final_quantity"]
    assert resource["deliverTo"]["reference"] == "Organization/HSP-003"
    assert "Joseph" not in str(resource)                       # no person is named in the order
    assert signed_in("amina").get(f"/fhir/SupplyRequest/{decision['decision_id']}").status_code == 404
    assert TestClient(app).get(f"/fhir/SupplyRequest/{decision['decision_id']}").status_code == 401


def test_dhis2_export_is_scoped_and_aggregate_only():
    export = signed_in("joseph").get("/export/dhis2").json()
    assert export["dataValues"] and {v["orgUnit"] for v in export["dataValues"]} == {"HSP-003"}
    assert set(export["dataValues"][0]) == {"dataElement", "period", "orgUnit", "value"}
    assert all(len(v["period"]) == 6 for v in export["dataValues"])
    assert "Illustrative" in export["note"]


def test_privacy_facts_come_from_the_enforced_settings():
    facts = signed_in("grace").get("/api/privacy").json()
    assert "donors" in facts["never_loaded"] and "donors" not in facts["tables_used"]
    assert {r["role"] for r in facts["roles"]} == set(config.load_settings("access")["roles"])
    assert "donor_id" in facts["columns_never_read"]["donations"]
    assert len(facts["your_scope"]) == 8


def test_sms_preview_fits_one_message():
    for user in ("amina", "joseph"):
        brief = signed_in(user).get("/api/brief").json()
        assert brief["sms_preview"] and len(brief["sms_preview"]) <= 160
