# Build plan — Sanguis Providus (Team MediBora)

Hackathon: Terumo BCT Africa Hackathon 2026. Challenge area: **forecasting and stock-out early warning**.
Submission closes **Wednesday 11 Nov, 12:00 EAT**. Demo video should be recorded by 10:00.
Working rules are in `CLAUDE.md`. Design rules are in `docs/DESIGN.md`.

## 1. What we are building

**One line:** the tool tells a blood service which blood groups will run short, where, and in how many
days, early enough to change an order or plan a drive instead of making an emergency call.

**Users (two roles):**
- **Hospital blood bank officer** — opens the app each morning, sees which groups need attention before
  the next delivery, approves or changes the suggested order.
- **Regional centre officer** — sees every hospital they supply, the supply coming from drives over the
  next four weeks, and suggestions for where and when to add a drive.

**The problem, in the data** (synthetic, never present as facts about real hospitals):
13% of requests are not fully met, about 23% of red cells and whole blood are wasted, an emergency
resupply takes a median of about 5 hours, 6 in 10 donors are students so supply drops in school
holidays (November to early January, April, August). Compute our own versions of these numbers in
Step 1 and use ours.

**The workflow (must run end to end):**
forecast demand → project stock forward → warn with days of cover, a range and reasons →
suggest an order (or a drive) → a person accepts, changes or rejects → decision is logged.

## 2. What the judges score (design every step against this)

| Criterion | Weight | What we must show |
| --- | --- | --- |
| Working prototype | 25 | The workflow runs on the data, shown working in the demo |
| Technical depth and architecture | 20 | Clean data flow, diagram, we know where it can fail |
| AI and data approach | 15 | Beats a simple baseline with both numbers shown, explains itself, person in control, fallback |
| Blood-system problem and user | 15 | Named user, correct blood terms |
| African conditions and scale | 15 | Works offline and on slow links, settings not code for another country, connects to existing systems |
| Demo and readiness | 10 | Clear 3-minute video |

**Required in every submission:** working prototype of one workflow; one AI/data feature compared with a
baseline (both numbers); Accept / Change / Reject on any recommendation; a fallback that works if the AI is
wrong or offline; an architecture diagram; README from the template; demo video of 3 minutes or less.

**The brief's five rules. AI must never:**
1. Release a unit for transfusion or decide blood group compatibility without a qualified person.
2. Override a laboratory result or a quarantine.
3. Contact a donor or patient with a message no person has approved.
4. Rank patients for blood on anything other than clinical need.
5. Present a guess as a fact. Every prediction shows its uncertainty.

## 3. Domain rules the code must respect

- Demand is per **facility × component × blood group**. Never one total for "blood".
- Train on **`units_requested`**, never `units_issued`. Issued is capped by what was on the shelf.
- Join on **`facility_id`**, never `facility_name_raw` (14% are mistyped on purpose).
- Shelf life: red cells (RBC) 42 days, whole blood (WB) 35, platelets (PLT) 5, plasma (FFP) and cryo 1 year.
- A donation is not stock until `tested_date`, and only if `screening_result` is `non_reactive`.
- Units with `temp_excursion_exposed` true are not safe stock.
- Temperature readings of -99.0, 99.9 and 0.0 are sensor glitches. Drop them.
- Transfers with no `received_at` are "not confirmed arrived".
- Red cell compatibility (information only, never auto-applied): O- can go to anyone; O+ to any positive
  group; A-/B- to their own letter and AB, either sign; negative patients receive negative only.
  Plasma runs the other way (AB plasma to anyone). Show compatible cover as a second, clearly labelled
  number. Never suggest substituting.
- Moving blood between facilities needs Ministry of Health authorisation. Any transfer or emergency
  delivery we suggest is a **request for approval**.
- Requests ask for RBC, PLT or FFP. Stock also holds WB and CRYO. Check in Step 1 how WB is used to
  fill RBC requests in the data, and report what you find before deciding how to treat it.

## 4. Data

Raw files are already in `data/raw/` and committed: `facilities, routes, drives, donations, units,
transfers, requests, daily_stock, power_outages, temperature_logs` (.csv). The organisers' `README.md`
and `DATA_DICTIONARY.md` are in `docs/dataset/`. **Read both dataset documents first.**
`donors.csv` is deliberately not in the repo and is never loaded. The dataset's generator script is also
left out on purpose: learn from the data, not from how it was made. Data covers 1 Nov 2025 to 31 Oct 2026: 6 regional centres (RBTC),
9 satellites (SAT), 32 hospitals (HSP).

**The demo clock.** The data is historical, so the app has an **"as of" date**. Everything up to that
date is history the model may use. Everything after is hidden. This lets the demo show a warning and
then show what really happened. Default as-of date: **Monday 3 August 2026** (the week before the
August school holiday). The date is changeable in the UI from a list of prepared dates.

## 5. Architecture

```
data/raw/*.csv
   │  pipeline (clean, aggregate)                    backend/pipeline/
   ▼
SQLite  data/app.db  ── local-first system of record  backend/db/
   │        ▲
   │        └── audit log, decisions, users
   ▼
forecast (baseline + model)  →  stock projection  →  alerts + suggestions     backend/engine/
   ▼
FastAPI  /api/...   /fhir/...   /export/dhis2                                  backend/api/
   ▼
React app (offline-tolerant, caches last brief)                                frontend/
   ┆
   ┆ optional one-way sync of aggregates + audit log
   ▼
Oracle Autonomous Database (central copy)                                      backend/sync/
```

Repo layout: `backend/`, `frontend/`, `data/raw/` (committed CSVs), `data/app.db` (ignored, rebuilt by one
command), `docs/`, `tests/`, `scripts/`, `README.md`, `CLAUDE.md`, `.env.example`, `.gitignore`.

One command rebuilds everything from raw data: `python -m backend.pipeline.build`.
One command runs the app: backend on port 8000, frontend on 5173.

## 6. Steps

Times are budgets, not promises. Each step ends with a checkpoint (see `CLAUDE.md`).
If a step passes double its budget, stop and offer the cut line.

---
### Step 0 — Scaffold (30 min)
- Create the repo layout. A `.gitignore` already exists; keep its entries (`data/*.db`, `.env`, `wallet/`,
  `node_modules/`, `__pycache__/`, `.venv/`, `data/raw/donors.csv`) and add to it as needed, `.env.example`, `requirements.txt`, Vite + React + TS +
  Tailwind app, pytest set up, `README.md` started from `docs/README_TEMPLATE.md`.
- Add the test `tests/test_privacy.py`: fails if any Python file under `backend/` references `donors.csv`.
- **Verify:** backend `/api/health` returns ok; frontend shows a blank styled page with the app name.
- **Commit:** `Scaffold backend, frontend and tests`

### Step 1 — Data pipeline and data facts (60 min)
- Load the allowed CSVs, clean them (rules in section 3), write tidy tables to SQLite:
  `facility`, `route`, `demand_daily` (facility, component, group, date, units_requested, units_issued,
  requests, unmet_units, emergency_requests), `stock_daily`, `delivery` (confirmed and unconfirmed
  routine/emergency arrivals per facility, group, component, day), `drive`, `supply_daily`
  (collecting site, date, attempts, collected, cleared units by group and available date), `calendar`
  (date, school_in_session, public_holiday, days_to_next_school_break, malaria_season by region).
- Calendar: school holidays per the dataset README (November to early January, April, August). Put the
  dates in `config/calendar_ke.yaml`. This file is the "settings not code" example for another country.
- Write `docs/DATA_FACTS.md` from code: fill rate, unmet units by group, stock-out days by facility and
  group, wastage rate, median emergency resupply hours, share of zero-demand days per series, how WB
  relates to RBC requests. These numbers go in the README and the pitch.
- Tests: no `facility_name_raw` joins, row counts sane, no glitch temperatures, privacy test passes.
- **Verify:** `python -m backend.pipeline.build` finishes in under 3 minutes and prints the data facts.
- **Cut line:** skip `supply_daily` and malaria flags now; add them in Step 8.
- **Commit:** `Add data pipeline and data facts`

### Step 2 — Baseline forecast and backtest harness (60 min)
- Forecast target: **daily units requested per facility × component × group, 14 days ahead**.
- Baseline B0: average of the same weekday over the previous 4 weeks. This is "what a manager does in
  their head".
- Backtest harness: rolling weekly origins from **6 Jul 2026 to 19 Oct 2026** (covers the August school
  holiday and term 3). For each origin, forecast 14 days using only data before the origin.
- Metrics, by segment (all, by component, common vs rare groups, by facility type, by region):
  MAE, WAPE (total units off ÷ total demand), MASE (below 1 beats naive). **Never MAPE** (zeros).
- Store every forecast in `forecast` (origin, facility, component, group, target_date, model, p10, p50, p90).
  For B0, p10/p90 come from the spread of its past errors.
- **Verify:** `python -m backend.engine.backtest --model baseline` prints a results table and writes
  `docs/RESULTS.md`.
- **Commit:** `Add baseline forecast and backtest`

### Step 3 — Stock projection and alert engine (75 min)
- For an as-of date, for each facility × component × group, project 14 days:
  `stock[t+1] = stock[t] − forecast_demand[t] − units_expiring[t] + expected_delivery[t]`.
  - Expected deliveries: learn each hospital's usual delivery weekdays and usual quantity per group
    from confirmed routine transfers before the as-of date.
  - Expiring units: use `units.csv` where it can be done reliably as of the date. **Timebox 40 minutes.**
    If unit location as-of cannot be reconstructed, skip it, say so, and list it under known limits.
- Outputs per series: units on shelf, **days of cover** (stock ÷ expected daily use), worst-case days
  (using p90), next delivery date, projected stock-out date (if any), status:
  - **Act** — projected to run out before the next delivery, or cover below the emergency lead time.
  - **Watch** — runs out before the next delivery in the worst case only, or cover under a set threshold.
  - **Steady** — otherwise.
  Thresholds live in `config/thresholds.yaml`, including a **staff-set minimum stock per group** that no
  forecast can lower (O- floor on by default).
- Suggested order: enough to restore cover to the target through the next delivery cycle, in whole
  units, bounded by a maximum so we do not push wastage up. Show the sum, never a bare number.
- **Reasons**: 2 to 3 short sentences built by templates from computed values only. Examples:
  "Schools close in 5 days; collections at your regional centre fell 58% during the April break."
  "Requests for O negative are up 30% on the last 4 weeks." "4 units expire before Friday."
- Alert backtest: over the same origins, did a stock-out (zero stock day or unmet request) happen within
  7 days? Compare our alert against the baseline rule "cover below X days using the 28-day average".
  Report **recall, precision, median warning lead time in days**. Append to `docs/RESULTS.md`.
- Compatible cover: for RBC, compute stock of compatible groups as an information-only field.
- **Verify:** CLI prints the morning list for one hospital as of 3 Aug 2026.
- **Commit:** `Add stock projection, alerts and suggestions`

### Step 4 — API, users, decisions, audit log (60 min)
- Seed users (shown on the sign-in screen as test log-ins): one hospital officer for a county referral
  hospital, one for a small maternity or sub-county hospital, one regional officer. Passwords hashed.
  Simple signed-cookie session. Role decides scope: hospital officer sees one facility; regional officer
  sees the facilities their centre supplies. Enforce scope on the server, with a test.
- Endpoints: `GET /api/brief` (morning list for the user's scope and as-of date), `GET /api/series/{id}`
  (projection, range, reasons, suggestion, compatible cover), `POST /api/decisions` (accept / change /
  reject, quantity, reason code, free-text note), `GET /api/decisions`, `GET /api/accuracy`,
  `GET /api/asof-dates`, `POST /api/fallback` (switch model ↔ baseline), `GET /api/health`.
- `audit_log` table: who, role, when, what they saw (baseline value, model value, suggestion), what they
  decided, reason. Append-only. Changing or rejecting requires a reason code.
- If the model's forecasts are missing or loading them fails, the API serves baseline forecasts and
  sets `"mode": "fallback"` in every response. Test this.
- **Verify:** `pytest` green; `curl` examples in the checkpoint.
- **Commit:** `Add API, roles, decisions and audit log`

### Step 5 — Interface: sign-in and the morning brief (120 min)
Follow `docs/DESIGN.md` exactly. This is the screen the judges see first.
- Sign-in with the three test accounts as one-tap cards.
- App shell: quiet left rail (Brief, Decisions, Accuracy, Data & privacy; Regional view for the regional
  role), top bar with facility name, as-of date picker, and a mode chip (Model / Fallback).
- **Morning brief**: one plain sentence summarising the day, then the blood-group rack
  (8 groups for the selected component, RBC by default), attention first.
- Loading, empty ("all steady") and error states designed, not default.
- Caches the last brief in the browser; if the API is unreachable, shows the cached brief with a
  "Showing last synced" banner.
- Works at 360px wide.
- **Verify:** sign in as each user, change the as-of date, switch component.
- **Cut line:** ship RBC only on the rack, components as a later tab.
- **Commit:** `Add sign-in and morning brief`

### Step 6 — Interface: detail, decision, decisions log (90 min)
- Detail panel for a group: 14-day projection with the range band, delivery markers, the stock-out
  point if any, reasons, compatible cover (labelled "Information only. Issue decisions stay with
  qualified staff."), and the suggestion with a quantity stepper.
- **Accept / Change / Reject**. Change and Reject need a reason from a short list plus an optional note.
  After a decision the card settles into a "decided" state with who and when.
- On Accept, a "View as FHIR" link shows the order as a FHIR `SupplyRequest` JSON (Step 9 fills it).
- Decisions page: the audit log as a clean, filterable list.
- Regional officers see the same panel but the action reads "Request approval" for transfers.
- **Verify:** full flow from alert to logged decision in under three clicks plus the reason.
- **Commit:** `Add detail panel, decisions and audit view`

### Step 7 — The model, and the comparison (90 min)
- Model M1: one pooled gradient-boosting model (scikit-learn `HistGradientBoostingRegressor`) trained
  across all hospitals on weekly demand per facility × component × group, with quantile loss for
  p10 / p50 / p90. Split weekly forecasts to days with each series' weekday profile.
- Features: lags and rolling means of requested units (1, 2, 4, 8 weeks), share of zero weeks,
  facility type, KEPH level, beds, region, component, group, week of year, `school_in_session`,
  `days_to_next_school_break`, public holiday, malaria season for the facility's region,
  recent share of emergency requests.
- Rare series (most weeks zero): do **not** chase precision. Use the regional forecast shared out by the
  hospital's usual proportion, or the baseline, whichever backtests better, and rely on the minimum
  stock floor. Say which was used.
- Run the same backtest as Step 2 and Step 3. Update `docs/RESULTS.md` with baseline vs model side by
  side: MAE, WAPE, MASE, and alert recall, precision, lead time, **by segment and by facility type**
  (the facility-type table is our bias check: no group of hospitals should be served clearly worse).
- **If the model does not beat the baseline, say so plainly.** Do not tune on the test window. Report the
  honest numbers; we then present where it helps (for example holiday weeks) and where it does not.
- **Accuracy page** in the UI: "How well is this working?" Baseline vs model, plain-language captions,
  the facility-type table, and the fallback switch with an explanation of what it does.
- **Verify:** `python -m backend.engine.backtest --model m1`; Accuracy page shows the same numbers.
- **Cut line:** skip quantile models; use p50 model plus error-spread ranges.
- **Commit:** `Add pooled forecast model and accuracy page`

### Step 8 — Regional view and collection planning (75 min)
This is the idea from the team's application: prevent the shortage upstream.
- Regional screen: a compact grid of the centre's hospitals × blood groups coloured by status, sorted
  by urgency; click through to the same detail panel.
- **Supply outlook, 4 weeks**: expected cleared units per week from scheduled drives =
  expected turnout by venue type × pass rate at screening × non-reactive rate, shifted by the testing
  wait. Learn all three rates from data before the as-of date.
- **Gap view**: forecast regional demand vs expected supply per group per week.
- **Drive suggestions** when a gap is projected 2 to 4 weeks out: which week, roughly how many usable
  units are needed, and which venue types still yield during school holidays (from the data). Each is a
  suggestion with Accept / Change / Reject and goes to the audit log.
- What-if: "add a drive of N expected donors on date D" updates the gap view. Nothing is saved until
  accepted.
- **Cut line:** grid + supply outlook only; drive suggestions as a static, clearly labelled next step.
- **Commit:** `Add regional view and collection planning`

### Step 9 — Standards, privacy page, offline proof (60 min)
- `GET /fhir/SupplyRequest/{decision_id}`: FHIR R4-shaped JSON for an accepted order (requester,
  supplier, item component + blood group, quantity, priority, occurrence date). Check the field names
  against the HL7 FHIR R4 SupplyRequest page before writing; if you cannot reach it, say so and mark the
  payload "FHIR-shaped, not validated".
- `GET /export/dhis2`: `dataValueSets`-shaped JSON of monthly stock-out days, fill rate and wastage per
  facility. Mark as illustrative mapping; we do not have real DHIS2 element IDs.
- `docs/STANDARDS.md`: a table mapping our tables to FHIR resources, ISBT 128 (the dataset's `unit_id`
  is a stand-in for a donation identification number) and DHIS2.
- **Data & privacy page** in the UI, plain language, with these blocks:
  1. *What we use and what we never load* (table list; donors table crossed out).
  2. *Who can see what* (the role scopes, read from the same config the server enforces).
  3. *Where it is stored* (this device first; central copy in a hosted database; region stated honestly).
  4. *If something leaks* (what could leak: stock counts by facility, no identities; who is told; the
     72-hour report to the regulator; access review from the audit log).
  5. *A data-flow diagram* drawn in SVG.
  6. A short privacy notice in English and Swahili. Flag the Swahili for a human check by a teammate.
- Offline proof: a "Simulate offline" switch in the top bar that blocks API calls so the judges can see
  the cached brief and the banner. An "SMS preview" showing the day's alerts as a 160-character message,
  labelled "Demo, not sent".
- **Commit:** `Add standards endpoints, privacy page and offline mode`

### Step 10 — Oracle Autonomous Database sync (45 min, only when Linet says the DB is ready)
- `python -m backend.sync.oracle` pushes the aggregate tables and the audit log to Oracle using
  `oracledb` in thin mode with the wallet (mTLS). Config from `.env`:
  `ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN, ORACLE_WALLET_DIR, ORACLE_WALLET_PASSWORD`.
- The app never needs Oracle to run. If the variables are missing, the sync command prints a clear
  message and exits cleanly. No raw request rows and nothing patient-level is synced.
- Show "Last synced to central database: <time>" on the Data & privacy page.
- **Cut line:** document the sync in the architecture and README as designed, not built.
- **Commit:** `Add optional Oracle sync`

### Step 11 — README, diagram, clean-clone test, then deployment if approved (75 min)
- README complete against the template: problem with our numbers, what works, **what is mocked**,
  how to run in under 10 minutes, architecture diagram (SVG in `docs/`), AI and data section with
  baseline vs ours on the stated test period, African conditions, **AI tools we used** (list Claude Code
  and what for, honestly), team table with a named data lead, known limits and next steps
  (DPIA, ODPC registration, processor agreements, penetration testing, real DHIS2 mapping).
- Clean-clone test: fresh folder, follow the README exactly, confirm it runs.
- `docs/DEMO_SCRIPT.md`: a 3-minute script. 0:00 the user and the problem with one number; 0:25 morning
  brief; 0:55 open an alert, reasons and range; 1:25 change and accept, audit log; 1:45 regional view and
  a drive suggestion; 2:10 accuracy vs baseline and the fallback switch; 2:35 offline, privacy, standards;
  2:50 close.
- **Deployment:** stop and ask Linet. Do nothing until she says "deploy" and names the target.
- **Commit:** `Complete README, architecture diagram and demo script`

## 7. Order of sacrifice if time runs short

Keep, in this order: Steps 0–6 (the workflow, end to end) → Step 7 (model vs baseline) → Step 11 (README,
video) → Step 9 → Step 8 → Step 10. A finished small thing beats an unfinished large one; the brief says
"build less and make it work".
## 8. Design references (from Linet) — these override docs/DESIGN.md on colour and type

Linet's references, with what was measured on each page on 10 Nov 2026:

| Reference | Take this | Measured |
| --- | --- | --- |
| https://www.sightmd.com/about-us/ (**the favourite, main reference**; a little plain, so lift it with the next one) | Clean, bright and clinical. Navy and sky blue on white. Pale blue bands for navigation and section headers. Paired solid buttons, each with an icon. Clear, friendly structure. | Navy #141B4D, sky #71C5E8, pale blue #D4EEF8, grey text #595959, page grey #F2F2F2. Headings in Acumin Pro 500 to 600, body in Montserrat light. |
| https://demophorius.com/ (what makes it interesting: character, motion and the blood theme) | Very large light headline. Scroll-driven movement: pinned headline, layered images that move at different speeds, soft blurred blue glow. Capitalised section labels with thin rules. One strong accent used rarely. Red appears only as the blood itself. | Black on white, accent #003CFF. Trivia Sans. 10px radius. |
| https://www.instituteofhealth.com/ (a supporting reference) | Stats as rows: small label, large number, hairline between. Generous editorial spacing. Translucent "glass" buttons. | Charcoal #242424, off-white #F1F1F1. Lay Grotesk 500, slightly tight letter-spacing. 5px radius. |

### Resulting direction (use these instead of the colour and type tokens in docs/DESIGN.md)

- **Mood:** SightMD's clean navy-and-sky clinical look as the base. Make it more interesting with
  Demophorius's large type, soft glow and motion. Use Institute of Health's stat rows and spacing
  for the numbers.
- **Type:** Hanken Grotesk (free, self-hosted with @fontsource/hanken-grotesk) in place of the paid
  fonts above. Weight 600 for headings, 500 for key numbers and labels, 400 for body.
  Letter-spacing -0.01em on large sizes. Tabular numbers everywhere.
- **Colour tokens:**
  - `bg` #FFFFFF, `bg-alt` #F2F2F2 (alternate sections), `surface` #FFFFFF, `line` #E3E5E8
  - `ink` #141B4D (navy, for headings and key numbers), `body` #595959 (body text), `muted` #6B7280
  - `primary` #141B4D (navy: primary buttons, selected nav, focus ring), white text on it
  - `sky` #71C5E8 (secondary button background with navy text, chart line, selected states)
  - `sky-soft` #D4EEF8 (navigation band, section header bands, forecast range band, the soft glow)
  - Status colours stay as in docs/DESIGN.md: steady green, watch amber, act brick red.
- **Layout moves to borrow:**
  - A pale blue (`sky-soft`) band for the top navigation and for section headers, as on SightMD.
  - Primary (navy) and secondary (sky) buttons side by side, each with a small icon.
  - The brief line is a large left-set headline in navy with generous space around it.
  - Present the blood groups as **hairline stat rows or tiles**: small label, large number
    (days of cover), thin rule.
  - Small capitalised section labels with a thin rule.
  - One soft blurred sky-blue glow behind the brief line. Nothing else decorative in the app.
  - Corner radius 6 to 10px. Hairlines instead of shadows.
- **The blood theme:** inside the working app, red is only for the "Act" status and the stock-out
  marker. The blood imagery lives on the landing page (below).

### Looking at the references, and at your own work

- Before Step 5, try to open each link and take your own screenshots to study. Save nothing from
  those sites into the repo. If your environment cannot reach a site, say so and use the notes above.
  Do not guess beyond them.
- Then tell Linet in five lines what you will build and wait for her OK before starting the interface.
- **Check your own build with screenshots.** After each interface step, run the app, capture every
  screen at 360px, 768px and 1280px wide, look at the images, and fix what is off before the
  checkpoint. Say in the checkpoint that you did this and what you fixed.
- Take the feel and the direction. Do not copy layouts, images, logos or text from these sites.
- Keep every docs/DESIGN.md rule that is not about colour or type: accessibility and contrast
  checks, plain wording, the cover bar, the answer-first brief line, never colour alone.

### Responsive: a hard requirement for every screen

- Phone (360 to 480px): one column, bottom navigation bar, detail opens as a full page, tables turn
  into stacked rows, touch targets at least 44px, no sideways scrolling anywhere.
- Tablet (768 to 1024px): two columns for the blood groups, navigation collapsed to icons.
- Desktop (1280px and up): full navigation, four columns for the blood groups, detail as a side
  panel. Content stops growing at 1120px wide and stays centred on very large screens.
- Use fluid type and spacing (CSS clamp) so nothing jumps between sizes. Charts redraw to the
  container width and keep their labels readable on a phone.

### Step 7b — Landing page with depth and scroll (60 min, after Step 7, never before)

Linet wants the 3D and scroll character of demophorius.com. It lives on a public landing page that
leads into sign-in. The working screens (brief, detail, decisions, regional, accuracy) stay still
and fast: people use them every morning, sometimes on 3G.

- A short scroll story, four beats: (1) the problem in one line with one number from
  docs/DATA_FACTS.md; (2) how the tool sees a shortage coming; (3) a person decides; (4) sign in.
- **Depth and motion with light techniques only:** CSS 3D transforms, perspective and layered
  parallax driven by scroll (Framer Motion `useScroll` / `useTransform`). A blood bag or tube drawn
  in SVG with shading for depth, which tilts slightly and **fills as the reader scrolls**, ending at
  a "days of cover" mark. A pinned headline that changes per beat. The soft sky glow drifts slowly.
- **No WebGL and no three.js or other 3D engine.** Ask Linet before adding any animation
  dependency beyond Framer Motion.
- The landing page is code-split so none of its code or images load inside the app after sign-in.
  Budget: under 150KB extra, images lazy-loaded.
- Respect `prefers-reduced-motion`: show the same content as a plain, still page.
- On a phone the story becomes simple stacked sections with gentle fades. No pinning, no parallax.
- The deep red of the blood in this illustration is the one place red is used outside "Act".
- **Cut line:** a still hero with the illustration and the sign-in cards. Skip the scroll story.
- **Commit:** `Add landing page`
- Order of sacrifice: this step is dropped before anything in Steps 0 to 7, 9 or 11.

### Imagery Linet likes on demophorius.com: 3D test tubes and blood bags

- **Test tubes with depth, floating in the background.** Build our own: a few tubes drawn in SVG
  with glass highlights, a rounded base and a liquid level, placed at different depths with CSS
  perspective, slightly blurred when further back, drifting and rotating a few degrees on scroll.
  Use them behind the landing page story (Step 7b) and, very faintly and without motion, in the
  sign-in screen background. Never behind data in the working app.
- **Blood bags.** One clean illustrated blood bag in the same SVG style (bag outline, label, tubing,
  deep red fill with a soft highlight) as the hero object on the landing page. It is the object that
  fills as the reader scrolls.
- **The tube motif inside the app, kept quiet.** The cover bar for each blood group may be drawn as
  a slim horizontal tube: rounded glass outline, fill in the status colour, a tick for the next
  delivery. This ties the landing page to the product without adding decoration.
- **Do not use demophorius.com's images, or any other site's.** Everything is drawn by us in SVG
  and CSS. If a photograph is wanted, use only an openly licensed one, and record its source and
  licence in the README under "Data". Ask Linet before adding any photo.
- Keep all of it light: SVG and CSS only, no 3D engine, no video. Still images when
  `prefers-reduced-motion` is set.

## 9. Amendments agreed on 10 Nov (these override the sections above where they differ)

From Linet's and the pipeline's look at the data (numbers in `docs/DATA_FACTS.md`):

1. **The value is on the supply side.** Weekly demand is nearly flat (549 to 749 units a week, median
   655). Weekly collections swing from 345 to 2,230. The weekly unmet rate follows regional centre
   red cell stock (correlation -0.82) and routine deliveries (-0.73). A 4-week average will be hard
   to beat on demand alone, and we will say so if it is not beaten.
   - **New Step 4b: supply forecast (75 min), before Step 5.**
     - Forecast cleared red cell units per regional centre per week, 4 weeks ahead, from the drive
       schedule, the school calendar, venue-type yield, pass rates and the testing wait.
       Baseline: 4-week average of cleared units. Same weekly origins as the demand backtest.
     - Project regional centre red cell stock forward from that.
     - Project what each hospital will actually receive: its usual delivery scaled by how well the
       centre can supply. Baseline: the hospital's 4-week average of routine units received.
     - Feed the projected deliveries into the stock projection and rerun the alert check.
     - Report baseline against model for supply, for deliveries received and for alerts, in
       `docs/RESULTS.md`, next to the demand results. Add a supply reason to the alert reasons.
     - **Cut line:** centre-level supply forecast and its comparison only; hospital deliveries stay
       on the usual quantity.
   - Step 7 keeps the demand model and its comparison. Step 8 reuses the Step 4b supply forecast.
2. **What counts as a shortage.** Hospitals sit at zero stock for a group on a large share of days,
   so zero stock is not the event. The event we warn about is a request that was not fully met, or
   that needed an emergency delivery, within 7 days. Alerts are evaluated against that.
   The stricter "not fully met only" result is reported beside it.
3. **Demo dates.** Default as-of date is **Monday 28 Sep 2026** (the week before the October
   deterioration). Monday 30 Mar 2026 (before the April holiday) is a second prepared date.
   August is not a shortage month in this data. The backtest window stays 6 Jul to 19 Oct 2026.
4. **Red cell cover** counts red cell units and whole blood together (6,349 of 27,273 units issued
   for red cell requests were whole blood). Hospitals hold no platelets; platelet demand is shown
   without a stock projection.

