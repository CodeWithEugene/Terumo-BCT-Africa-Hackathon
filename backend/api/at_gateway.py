"""Africa's Talking: reading what it sends us, and sending text messages back.

No extra package is needed. Messages go out with the standard library.
Settings (put them in `.env` locally and in the Render dashboard when hosted, never in code):

- AT_API_KEY            the key from the Africa's Talking dashboard
- AT_USERNAME           your app username. Use `sandbox` while testing in the simulator.
- AT_SENDER_ID          optional alphanumeric sender id or short code approved for your account
- AT_CALLBACK_TOKEN     optional long random text. If set, every callback must end in `?token=<this text>`
- SP_STAFF_PHONES       who may use staff features by phone, for example `254712345678=amina,254700000001=grace`
- SP_USSD_OPEN          `1` lets any phone look up a hospital in view-only mode (demo). `0` allows staff phones only.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque

from fastapi import HTTPException, Request

log = logging.getLogger("providus.at")

LIVE_URL = "https://api.africastalking.com/version1/messaging"
SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
SMS_LIMIT = 160


def configured() -> bool:
    return bool(os.environ.get("AT_API_KEY") and os.environ.get("AT_USERNAME"))


async def form(request: Request) -> dict[str, str]:
    """Africa's Talking posts `application/x-www-form-urlencoded`. Read it without an extra dependency."""
    raw = (await request.body()).decode("utf-8", errors="replace")
    return {k: v[-1] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


def check_callback(request: Request) -> None:
    """Refuse callbacks that do not carry our secret token (when one is set)."""
    expected = os.environ.get("AT_CALLBACK_TOKEN", "")
    if expected and request.query_params.get("token") != expected:
        raise HTTPException(status_code=403, detail="Not allowed.")


# --- Phone numbers -------------------------------------------------------------------

def normalise(phone: str) -> str:
    """'+254 712 345 678', '0712345678' and '254712345678' all become '254712345678' (Kenya)."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9:
        digits = "254" + digits
    return digits


def mask(phone: str) -> str:
    """For logs and the audit trail: no full numbers are kept."""
    digits = normalise(phone)
    return f"{digits[:5]}***{digits[-2:]}" if len(digits) > 7 else "***"


def staff_phones() -> dict[str, str]:
    """Phone number -> username, read from SP_STAFF_PHONES. Held in settings, never in the database."""
    out: dict[str, str] = {}
    for item in os.environ.get("SP_STAFF_PHONES", "").split(","):
        if "=" in item:
            phone, username = item.split("=", 1)
            if normalise(phone) and username.strip():
                out[normalise(phone)] = username.strip().lower()
    return out


def open_lookup() -> bool:
    return os.environ.get("SP_USSD_OPEN", "1") != "0"


# --- Sending ---------------------------------------------------------------------------

_recent: dict[str, deque] = defaultdict(deque)


def allow_send(phone: str, limit: int = 4, window: int = 3600) -> bool:
    """A small guard so nobody can run up the SMS bill by dialling over and over."""
    key = normalise(phone)
    recent = _recent[key]
    while recent and time.time() - recent[0] > window:
        recent.popleft()
    if len(recent) >= limit:
        return False
    recent.append(time.time())
    return True


def send_sms(to: list[str], message: str) -> dict:
    """Send one text. Never raises: a gateway outage must not stop the app.

    Returns {"sent": n, "ok": bool, "note": str, "message_ids": [...]}.
    """
    if len(message) > SMS_LIMIT:
        message = message[:SMS_LIMIT - 3] + "..."
    if not configured():
        return {"sent": 0, "ok": False, "note": "SMS is not set up on this server.", "message_ids": []}
    username = os.environ["AT_USERNAME"]
    fields = {"username": username, "to": ",".join("+" + normalise(p) for p in to), "message": message}
    if os.environ.get("AT_SENDER_ID"):
        fields["from"] = os.environ["AT_SENDER_ID"]
    request = urllib.request.Request(
        SANDBOX_URL if username == "sandbox" else LIVE_URL,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"apiKey": os.environ["AT_API_KEY"], "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode())
    except (OSError, ValueError) as error:
        log.warning("SMS gateway failed: %s", type(error).__name__)
        return {"sent": 0, "ok": False, "note": "The message was not sent. The SMS gateway did not answer.",
                "message_ids": []}
    recipients = body.get("SMSMessageData", {}).get("Recipients", [])
    good = [r for r in recipients if str(r.get("status", "")).lower() == "success"
            or r.get("statusCode") in (100, 101, 102)]
    return {"sent": len(good), "ok": len(good) == len(to) and bool(good),
            "note": "Sent." if good else "The gateway refused the message.",
            "message_ids": [r.get("messageId") for r in good if r.get("messageId")]}
