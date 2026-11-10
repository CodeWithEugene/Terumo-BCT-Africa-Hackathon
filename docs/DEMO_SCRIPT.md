# Demo script (3 minutes)

Run `python scripts/dev.py` and open http://localhost:5173 at 1280px wide or more. Leave the date on
**Mon 28 Sep 2026**. Every number below is on screen; read it from the screen, not from this page.
Say once, early: "This is the organisers' synthetic dataset, not real hospitals."

| Time | Screen | Say |
| --- | --- | --- |
| 0:00 | Landing page, top. Scroll slowly through the three beats. | "A blood bank officer finds out a group has run out when a request cannot be filled. In this dataset, 1 in 8 requests is not fully met, and an emergency delivery takes a median of 5.2 hours. Demand is almost flat all year. Supply is what swings: collections fall by over a third when schools close." |
| 0:25 | Scroll to the cards and click **Open as Joseph O.** (City Maternity Hospital). | "This is Joseph's morning brief. One sentence first: three groups are worth watching before Wednesday's delivery. Then eight blood groups. The big number is days of cover. The tube shows it; the tick is the next delivery. If the fill stops before the tick, that is a shortage you can see." |
| 0:55 | Click **B+**. Point at the chart, then **Why**. | "The line is expected stock, the band is the range from a quiet to a busy spell. Here it runs out before Friday. The reasons are plain sentences built from the numbers: requests for B positive are up, and what the centre is expected to deliver. Red cells and whole blood are counted together, because whole blood fills red cell requests here." |
| 1:15 | Press **Show what really happened next**. | "The data is historical, so we can check. This was hidden from the forecast." |
| 1:25 | **Change**, add 2 units, pick a reason, save. Then **View as FHIR**. Open **Decisions**. | "The tool suggests an order and shows its sum. Joseph changes it and must say why. It is logged with what he was shown, and the log cannot be edited. The order is also a FHIR SupplyRequest that another system can read." |
| 1:45 | Sign out. **Open as Grace M.** → **Regional view**. Scroll to **Fair share**. | "Grace runs the regional centre. One grid shows every hospital and group. Here is what we found in the data: on 61% of the days a hospital ran short, another hospital in its region had spare units of that group. The blood was enough; it was on the wrong shelf. So the tool proposes sharing this week's units by days of cover. The lowest cover goes from half a day to nearly seven. It is a proposal: moving blood needs authorisation, so she requests approval." |
| 2:10 | **Accuracy**. | "Honest numbers, on 16 Mondays the model never saw. Supply forecast: error falls from 58 to 26 units per 100. Demand: 71 to 68, a small gain, because demand is flat. Warnings came before 76% of real shortages, against 65% for a simple rule, but most warnings are still false alarms and we say so. And the replay: with the same blood, fair share cuts what hospital shelves could not supply by a third. The best-stocked hospitals give up cover, and we show that too. This switch falls back to the 4-week average if the model looks wrong, and every screen says which is in use." |
| 2:35 | Flip **Simulate offline** on the Brief. Then **Data & privacy**. | "With no connection, the last brief is still there, with a banner. It runs on one device with a local database. We never load the donor table; unit labels are scrambled; each role sees only its own hospitals. School terms and thresholds are settings files, so another country changes settings, not code." |
| 2:50 | Back to the Brief. | "It suggests. A person decides. Sanguis Providus, from team MediBora." |

## The quick way: the guided tour

Press **Take the guided tour** on the landing page. It signs in as Joseph, walks through 13 steps, switches
to Grace by itself for the regional steps, and outlines the part of the screen each step is about. Use the
right arrow key to move on; every control still works, so you can stop and click at any step. The tour's
text matches this script.

## Before recording

- Rebuild first: `python -m backend.pipeline.build`. To clear old demo decisions, delete `data/app.db` before the build.
- Zoom the browser to 100%. Close other tabs. Hide bookmarks.
- If the Change step fails with "already recorded", pick another blood group or another date.
