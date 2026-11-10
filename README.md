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
  - If the forecast model is missing or fails, the API serves the baseline and says so in every response.
- What is mocked or not finished:
  - The interface (Steps 5 to 9) is not built yet. The frontend is a starter page.
  - The trained forecast model (Step 7) is not built yet, so the app currently runs in fallback mode.
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
In progress. The baseline and the alert check are built; results are in `docs/RESULTS.md`.
The trained model and the side-by-side comparison come in Step 7.

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
