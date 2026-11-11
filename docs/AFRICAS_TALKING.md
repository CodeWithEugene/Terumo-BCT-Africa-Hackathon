# USSD and SMS through Africa's Talking

The USSD code is `*384*11400#`. Everything here is built into the existing backend. No new package is needed.

## Callback addresses to paste into the Africa's Talking dashboard

The web app on Vercel passes `/api` on to the backend (`frontend/vercel.json`), so the Vercel address works.

| Where in the dashboard | Address |
| --- | --- |
| USSD, callback URL | `https://sanguis-providus.vercel.app/api/ussd?token=YOUR_TOKEN` |
| SMS, incoming messages callback | `https://sanguis-providus.vercel.app/api/sms/incoming?token=YOUR_TOKEN` |
| SMS, delivery reports callback | `https://sanguis-providus.vercel.app/api/sms/delivery?token=YOUR_TOKEN` |

`YOUR_TOKEN` is any long random text you invent. Set the same text as `AT_CALLBACK_TOKEN` on the backend. Africa's
Talking does not sign its callbacks, so this token is what stops anyone else posting to the address.

If the USSD screen is slow, point the USSD callback straight at the Render address instead
(`https://sanguis-providus-api.onrender.com/api/ussd?token=YOUR_TOKEN`). That skips one hop. USSD must answer within a few seconds.

## Settings (Render, Environment tab, and `.env` on your laptop)

| Name | Value |
| --- | --- |
| `AT_API_KEY` | The key from the dashboard. Never commit it. |
| `AT_USERNAME` | Your Africa's Talking app username. Use `sandbox` while testing. |
| `AT_CALLBACK_TOKEN` | The random text above. |
| `AT_SENDER_ID` | Optional. A sender id or short code approved on your account. |
| `SP_STAFF_PHONES` | Staff phones, for example `254712345678=amina,254700000001=grace`. The name is a log-in from `config/access.yaml`. |
| `SP_USSD_OPEN` | `1` (default) lets any phone look up a hospital, view only. `0` allows staff phones only. |

Phone numbers live in settings, not in the database (`docs/SMS_HANDOVER.md`, rule 3).

## The USSD menu

Staff phones go straight to their hospital. A regional officer first sees "Hospitals needing action" and "Choose a hospital".
Other phones (demo) choose a hospital and can only read. `0` goes back one step, `00` goes home, `98` shows more.

```
Hospital menu
1. Today's alert          the morning sentence, groups to Act on and Watch, next delivery
2. Cover by blood group   pick red cells, plasma or platelets, then a group: shelf units, days of cover, likely short date
3. Suggested orders       pick a group, see the sum, then 1 to accept (staff phones only, logged like any decision)
4. Text me the alert      sends the 160 character alert to the caller's own phone (4 an hour per phone)
```

Change and reject need a reason, so they stay in the app.

## SMS

Staff text the number linked to the account. Replies are under 160 characters.

| Text | Reply |
| --- | --- |
| `ALERT` or `ALERT Thika` | The day's alert, the same words as the Brief page preview |
| `COVER O-` or `COVER A+ Thika` | Status, units and days of cover, next delivery |
| `ORDERS` | Suggested units per group |
| `HOSPITALS` | Hospitals with groups to act on, most urgent first |
| anything else | Help text |

A hospital officer can only look up their own hospital. A regional officer can look up any hospital the centre supplies.

Sending from the app: `POST /api/sms/send` with `{"facility_id": "HSP-006", "confirm": true}`. The text is rebuilt on the
server, a signed-in officer must confirm, it goes to the registered staff phones of that hospital, and the audit log records
the text, the number of recipients and the result. If the gateway is down the call says "not sent" and the app carries on.
Donor call-outs are not sent from here (`docs/SMS_HANDOVER.md`, rule 2).

## Test it

1. In the Africa's Talking sandbox, create a USSD code and set the callback above. Set `AT_USERNAME=sandbox`.
2. Open the simulator from the sandbox, enter a phone number and dial the code.
3. Check without Africa's Talking:

```bash
curl -X POST http://localhost:8000/api/ussd -d "phoneNumber=+254711000001" -d "text=1"
```

Tests: `tests/test_africastalking.py`. No real message is sent by the tests.
