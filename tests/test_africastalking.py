"""USSD and SMS through Africa's Talking. No real message is ever sent: the gateway call is replaced."""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["SP_STAFF_PHONES"] = "254711000001=amina,254711000002=grace"
os.environ["SP_USSD_OPEN"] = "1"

from backend.api import at_gateway, sms, ussd  # noqa: E402
from backend.api.main import app  # noqa: E402


@pytest.fixture()
def client(db_path):
    return TestClient(app)


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setenv("AT_API_KEY", "test")
    monkeypatch.setenv("AT_USERNAME", "sandbox")
    monkeypatch.setattr(at_gateway, "send_sms",
                        lambda to, text: sent.append((to, text)) or {"sent": len(to), "ok": True, "note": "Sent.", "message_ids": []})
    return sent


def dial(client, phone, text=""):
    response = client.post("/api/ussd", data={"sessionId": "s", "serviceCode": "*384*11400#",
                                              "phoneNumber": phone, "text": text})
    assert response.status_code == 200
    return response.text


def test_every_screen_is_con_or_end_and_short(client):
    for phone in ("+254711000001", "+254711000002", "+254799999999"):
        for text in ("", "1", "2", "1*1", "1*2", "2*1", "2*98", "98", "9", "1*2*1", "1*3", "3", "1*2*1*1"):
            reply = dial(client, phone, text)
            assert reply[:4] in ("CON ", "END "), reply
            assert len(reply) - 4 <= ussd.SCREEN_LIMIT, (text, len(reply))


def test_hospital_officer_lands_on_own_hospital(client):
    assert "Thika" in dial(client, "+254711000001")      # amina is at HSP-006


def test_back_and_home_keys(client):
    assert dial(client, "+254711000001", "1*0") == dial(client, "+254711000001", "")
    assert dial(client, "+254711000001", "2*1*00") == dial(client, "+254711000001", "")


def test_regional_officer_sees_only_the_centre_hospitals(client):
    assert "Hospitals needing action" in dial(client, "+254711000002")
    listing = dial(client, "+254711000002", "2") + dial(client, "+254711000002", "2*98") + dial(client, "+254711000002", "2*98*98")
    assert "Thika" in listing and "Coast" not in listing        # Coast belongs to Mombasa


def test_open_visitor_is_view_only(client, db_path):
    reply = dial(client, "+254799999999", "1*3*1")             # first hospital, suggested orders, first order
    assert "Accept" not in reply
    assert dial(client, "+254799999999", "1*3*1*1").startswith("CON")   # pressing 1 records nothing


def test_closed_lookup_refuses_unknown_phone(client, monkeypatch):
    monkeypatch.setenv("SP_USSD_OPEN", "0")
    assert dial(client, "+254799999999").startswith("END")
    assert dial(client, "+254711000001").startswith("CON")


def test_staff_accept_goes_through_the_normal_decision_path(client, monkeypatch):
    """Replaced here so the shared test database is left untouched for the other tests."""
    from backend.api import service

    calls = []
    monkeypatch.setattr(service, "record_decision",
                        lambda user, body: calls.append((user.username, body)) or {"decision": {"final_quantity": 6}})
    assert "Accept" in dial(client, "+254711000001", "3*1")
    assert dial(client, "+254711000001", "3*1*1").startswith("END Recorded")
    assert calls[0][0] == "amina" and calls[0][1]["action"] == "accept"


def test_text_me_sends_one_alert_to_the_callers_phone(client, outbox):
    assert dial(client, "+254711000001", "4").startswith("END The alert is on its way")
    assert outbox[0][0] == ["+254711000001"] and len(outbox[0][1]) <= 160


def test_incoming_sms_replies_by_text(client, outbox):
    assert client.post("/api/sms/incoming", data={"from": "+254711000001", "text": "COVER O-"}).text == "OK"
    to, text = outbox[0]
    assert to == ["+254711000001"] and "O" in text and len(text) <= 160


def test_sms_commands_stay_inside_160_characters(db_path):
    for text in ("ALERT", "alert", "COVER O-", "COVER A+", "COVER", "ORDERS", "HOSPITALS", "hello", "ALERT nowhere"):
        assert len(sms.reply_to("+254711000001", text)) <= 160
        assert len(sms.reply_to("+254711000002", text)) <= 160


def test_hospital_officer_cannot_look_up_another_hospital_by_sms(db_path):
    assert "No hospital matches" in sms.reply_to("+254711000001", "ALERT Coast")


def test_delivery_report_is_logged_without_a_phone_number(client):
    client.post("/api/demo-login", json={"username": "amina"})
    client.post("/api/sms/delivery", data={"id": "ATXid1", "status": "Success", "phoneNumber": "+254711000001"})
    entries = client.get("/api/audit").json()["entries"]
    assert all("254711000001" not in str(e) for e in entries)


def test_send_needs_a_person_and_a_confirmation(client, outbox):
    assert client.post("/api/sms/send", json={"facility_id": "HSP-006", "confirm": True}).status_code == 401
    client.post("/api/demo-login", json={"username": "amina"})
    assert client.post("/api/sms/send", json={"facility_id": "HSP-006"}).status_code == 422
    assert client.post("/api/sms/send", json={"facility_id": "HSP-003", "confirm": True}).status_code == 403
    done = client.post("/api/sms/send", json={"facility_id": "HSP-006", "confirm": True}).json()
    assert done["sent"] is True and len(done["text"]) <= 160
    assert sorted(outbox[-1][0]) == ["254711000001", "254711000002"]


def test_callback_token_is_enforced_when_set(client, monkeypatch):
    monkeypatch.setenv("AT_CALLBACK_TOKEN", "secret")
    assert client.post("/api/ussd", data={"phoneNumber": "+254711000001", "text": ""}).status_code == 403
    assert client.post("/api/ussd?token=secret", data={"phoneNumber": "+254711000001", "text": ""}).status_code == 200


def test_gateway_outage_does_not_raise(monkeypatch):
    monkeypatch.setenv("AT_API_KEY", "x")
    monkeypatch.setenv("AT_USERNAME", "sandbox")
    monkeypatch.setattr(at_gateway.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert at_gateway.send_sms(["+254711000001"], "hi")["ok"] is False


def test_phone_numbers_are_normalised():
    assert {at_gateway.normalise(p) for p in ("+254 711 000 001", "0711000001", "254711000001")} == {"254711000001"}
