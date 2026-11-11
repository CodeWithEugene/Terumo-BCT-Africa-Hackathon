# USSD and SMS on Vercel (no Render needed)

The functions in `frontend/api/` answer Africa's Talking directly from Vercel. They take priority over the
`/api/*` forward to Render in `frontend/vercel.json`, so these three addresses work with no Render involved:

- `/api/ussd` for `*384*11400#`
- `/api/sms/incoming` for texts sent to us
- `/api/sms/delivery` for delivery reports

## How it works
Vercel cannot run the forecast engine, so `python scripts/export_ussd_data.py` runs it once and saves the answers for the
default date in `frontend/api/_data/ussd-data.js`. The functions read that file. The menu and the SMS commands match
`docs/AFRICAS_TALKING.md`, with two differences. Accepting an order is not possible by USSD (there is no database here), so it says to
open the app. And the numbers only change when someone reruns the export script and pushes.

## Settings (Vercel, Project, Settings, Environment Variables, then redeploy)
`AT_API_KEY`, `AT_USERNAME`, `AT_CALLBACK_TOKEN`, `SP_STAFF_PHONES`, `SP_USSD_OPEN`, and optionally `AT_SENDER_ID`.
Meanings are the same as in `docs/AFRICAS_TALKING.md`.

## Going live
Deployment Protection on Vercel blocks preview addresses, and Africa's Talking cannot sign in. So the code must be on the branch
the Vercel project uses for Production (Settings, Git, Production Branch).
