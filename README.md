# MediBora: Sanguis Providus warns a blood service which blood groups will run short, where, and in how many days

Terumo BCT Africa Hackathon 2026 · Challenge area: forecasting and stock-out early warning

> Build in progress. Sections marked "to come" are filled in as each step of `docs/BUILD_PLAN.md` is finished.
> All data is the organisers' synthetic starter dataset. Nothing here describes a real hospital, donor or patient.

## The problem
A hospital blood bank officer finds out a blood group has run out when a request cannot be filled. The fix is
then an emergency call to the regional centre. In the starter dataset (numbers from `docs/DATA_FACTS.md`,
computed by our pipeline):

- 12.9% of requests were not fully met, and 43.8% of O negative units requested were never issued.
- An emergency resupply took a median of 5.2 hours.
- 23.2% of red cell and whole blood units were wasted, while other shelves were empty.
- Collections were 37.4% lower in school breaks than in term time.

Our users are the **hospital blood bank officer**, who needs to know each morning which groups will run short
before the next delivery, and the **regional centre officer**, who needs the same view across every hospital
they supply.

## What we built
- What works now:
  - One command builds a local database from the raw files and writes the data facts.
  - A baseline forecast (same weekday, last 4 weeks) with a backtest over 16 weekly dates.
  - A 14-day stock projection per hospital, product and blood group, with days of cover, a range,
    a status (Act, Watch, Steady), plain-language reasons and a suggested order shown as a sum.
  - A supply forecast for red cells: cleared units per regional centre from the drive schedule, what each
    hospital will receive, and regional centre stock, each compared with a simple baseline.
  - An alert check against what really happened, compared with a simple cover rule (`docs/RESULTS.md`).
  - An API with three test log-ins, role-based access, Accept / Change / Reject, and an append-only audit log.
  - A sign-in screen with three one-tap test accounts and the morning brief: one plain sentence, then the eight
    blood groups with days of cover, a cover bar and a status. It keeps the last brief in the browser and
    shows it with a banner if the server cannot be reached. It works at 360, 768 and 1280 pixels wide.
  - A detail view per blood group: the 14-day projection with its range, delivery markers and the point where
    stock runs out, the reasons, compatible stock (information only), and the suggestion with its sum.
    Accept, Change or Reject; Change and Reject need a reason. A 10-second undo. A Decisions page lists the log.
    A switch shows what really happened next, which the forecast never sees.
  - A pooled forecast model (gradient boosting, trained across all hospitals) compared with the baseline on the
    same test dates, and an Accuracy page that shows both sets of numbers, a table by kind of hospital and the
    fallback switch.
  - A regional view for the regional centre officer: every hospital and blood group in one grid, the supply
    outlook for 4 weeks, the gap against demand by blood group, suggestions for extra collections (each with
    Accept, Change or Reject), and a "what if we add a drive" try-out that saves nothing.
  - If the forecast model is missing or fails, the API serves the baseline and says so in every response.
- What is mocked or not finished:
  - The privacy screen, the standards endpoints (FHIR, DHIS2), the offline switch and the landing page are
    still to come.
  - Drive suggestions are requests to a drive planner. Nothing is booked and no donor is contacted.
  - The "View as FHIR" link on an accepted order comes with the standards step.
  - Units exposed to a warm fridge cannot be dated from the data, so they are not removed from projected stock.
  - School terms, public holidays and malaria months are approximate settings in `config/calendar_ke.yaml`.

Demo video (3 minutes or less): to come
Live demo: to come · Test log-ins (demo only): `amina` / `thika-demo`, `joseph` / `maternity-demo`,
`grace` / `nairobi-demo`

## How to run it
You need Python 3.11 or newer and Node.js 20 or newer.

**1. Get the code and set up Python** (run from the repo folder)

Windows (Git Bash):
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux or macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Build the database from the raw files** (about 15 seconds; prints the data facts)
```bash
python -m backend.pipeline.build
```

**3. Run the tests**
```bash
python -m pytest
```

**4. See the morning list for one hospital**
```bash
python -m backend.engine.brief --facility HSP-006 --as-of 2026-10-05
```

**5. Start the app** (backend on port 8000, frontend on port 5173; the first run installs the frontend packages)
```bash
python scripts/dev.py
```
Open http://localhost:5173. Stop with Ctrl+C.

## Architecture
To come (Step 11). The planned data flow is in section 5 of `docs/BUILD_PLAN.md`.

## AI and data
All numbers below are computed by `python -m backend.pipeline.build` and written to `docs/RESULTS.md`.
Test period: 16 Mondays from 6 July to 19 October 2026. On each date the forecasts see only earlier days.

- What the AI or data feature does: forecasts demand per hospital, product and blood group for 14 days;
  forecasts red cell supply per regional centre for 4 weeks from the drive schedule; projects each shelf
  forward and warns before a shortage.
- Baseline we compared against: the average of the same weekday over the last 4 weeks (demand); the average
  of the last 4 weeks (supply); "cover under 3 days on the 28-day average" (alerts).
- Result:
  - Supply (cleared red cell units per centre and week): baseline 58% error vs ours 26%.
  - Demand (7-day totals): baseline 71.3% error vs ours 67.9%. A small gain: demand is nearly flat all year.
  - Early warning: the simple rule warned before 65% of real shortages, ours before 76%, with about the same
    share of false alarms (27% and 28% of warnings were followed by a real shortage).
- How a user sees the reason for a recommendation: two or three short sentences beside each alert, built by
  templates from computed numbers, and the suggested quantity shown as a sum of its parts.
- Who approves it (Accept / Change / Reject): the signed-in officer. Change and Reject need a reason.
  Every decision is written to an append-only audit log with what the person was shown.
- What happens if the AI is wrong or offline: a switch on the Accuracy page, or any failure of the model,
  makes every screen use the 4-week average and say so. The last brief is kept in the browser for offline use.

## Data
The organisers' synthetic starter dataset, in `data/raw/`. Tables used: facilities, routes, drives, donations,
units, transfers, requests, daily_stock, power_outages, temperature_logs.
The donor table is deliberately not in this repo and is never loaded. No real donor, patient or facility data.

## African conditions
To come (Steps 5 and 9): offline use, slow connections, phones, languages and settings for another country.

## AI tools we used
To come (Step 11).

## Team
| Name | Role | Country | Presenting Friday (in person / online) |
|------|------|---------|-----------------------------------------|
| To come | | | |

## Known limits and next steps
To come.
