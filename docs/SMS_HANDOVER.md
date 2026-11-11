# SMS alerts: handover note for Eugene

> Update: the Africa's Talking USSD menu and SMS are now built. See `docs/AFRICAS_TALKING.md`. The rules below still apply.

What exists today is a **preview only**. The Brief page shows the day's alerts as one text message of at most
160 characters, labelled "Demo, not sent". The regional view shows a draft donor call-out, also never sent.
No message leaves the app and no phone numbers are stored.

## Where the code is

| What | Where |
| --- | --- |
| The staff alert text | `sms_preview()` in `backend/api/service.py` (returned as `sms_preview` by `GET /api/brief`) |
| The donor call-out draft | `call_out_draft` in `backend/engine/region.py` (returned by `GET /api/region`) |
| Where both are shown | `frontend/src/pages/BriefPage.tsx` and `frontend/src/pages/RegionPage.tsx` |
| Wording shown to users | `frontend/src/i18n/en.ts` (`sms` and `region.callOut`) |
| Tests | `tests/test_standards.py` (160-character limit), `tests/test_risk.py` (draft checks) |

## Rules that must hold when sending is added

1. **A person approves every message.** The brief's rules say AI must never contact a donor or patient with a
   message no person has approved. Add an Approve step, and log who approved, what text, and when, in the
   audit log (`_audit()` in `backend/api/service.py`).
2. **Staff alerts and donor messages are different.** A staff alert goes to a blood bank officer's work
   phone. A donor call-out needs donor contact details and consent, which this tool deliberately does not
   hold. Send it through the donor system, not from here.
3. **No identities in this database.** Keep staff phone numbers in settings or the gateway account, not in
   `data/app.db`, unless the privacy page and `docs/SECURITY.md` are updated first.
4. **Secrets stay out of the repo.** Gateway keys go in `.env` (see `.env.example`), never in code or commits.
5. **Keep it to 160 characters** per message, plain text, with the hospital name and the date.
6. **It must fail quietly.** If the gateway is down, the app still works and says the message was not sent.

## A sensible first step

Add `POST /api/sms/send` that takes the facility and date, rebuilds the text on the server (never trust text
from the browser), requires the signed-in officer to confirm, sends through one gateway (for example
Africa's Talking), and writes an audit entry. Add the gateway as an optional dependency, like `oracledb`.
Any new dependency should be agreed with the team first.
