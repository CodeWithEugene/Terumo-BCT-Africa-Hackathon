# Demo recording script (under 3 minutes)

Start the app (`python scripts/dev.py`), open http://localhost:5173 in a wide window at 100% zoom, and
start recording on the landing page. Read the **Say** column aloud. It is about 380 words, which is
2 minutes 45 seconds at a calm pace. The right arrow key moves the tour on.

## Part 1: the landing page (about 35 seconds)

| Do | Say |
| --- | --- |
| Landing page, top. Pause two seconds. | "We are team MediBora, and this is Providus. It runs on the hackathon's synthetic dataset." |
| Scroll to **The problem**. | "One in eight requests for blood is not fully met. When a shelf runs out, the emergency delivery takes a median of 5.2 hours. Today the officer finds out when the request arrives." |
| Scroll to **Seeing it coming**. | "We found that demand is steady. Supply is what swings: collections fall by over a third when schools close. So we forecast both, and walk every shelf 14 days forward." |
| Scroll to **A person decides**. Press **Take the guided tour**. | "And the tool only suggests. A person decides." |

## Part 2: the guided tour (about 2 minutes 10 seconds)

| Step | Say |
| --- | --- |
| 1. The answer comes first | "This is Joseph, a blood bank officer at a maternity hospital. His morning starts with one sentence: which groups need action before the next delivery." |
| 2. Eight blood groups | "Eight blood groups, one number each: days of cover. The tick on the tube is the next delivery. A fill that stops before the tick is a shortage he can see." |
| 3. Fourteen days ahead | "Opening B positive shows 14 days ahead, with a busy-to-quiet range, each delivery, and the day it runs out." |
| 4. Two risks | "Shortage and wastage come from the same shelf, so he sees both: the chance of running out, and the units likely to expire." |
| 5. What if? | "He can test a mass-casualty event or a late delivery. Nothing is saved." |
| 6. It suggests | "The suggested order is a sum he can check, with plain reasons. He accepts, changes or rejects it, and a change needs a reason." |
| 7. On the record | "Every decision is logged with what he was shown, and the log cannot be edited. An order opens as a FHIR SupplyRequest for other systems." |
| 8. How well is this working? | "Every result sits beside a simple baseline, on 16 dates the models never saw. The supply forecast cuts error from 58 to 26 percent. Warnings came before 76 percent of real shortages. One switch falls back to the 4-week average." |
| 9. The regional centre | "Now Grace, at the Nairobi regional centre. Every hospital and blood group in one grid, most urgent first." |
| 10. The right shelves | "Here is our key finding. On 61 percent of the days a hospital ran short, another hospital in its region held spare units. The blood was enough. It was on the wrong shelf. Sharing by days of cover, with the same blood, cuts shortages by 32 percent in our replay, and wastage falls too. Grace requests approval; nothing moves on its own." |
| 11. Plan collections | "Four weeks ahead, the tool shows the supply gap, suggests extra drives with a draft donor call-out, and says how many platelet apheresis donors to book." |
| 12. No identities | "No donor or patient identities are ever loaded. Each role sees only its own hospitals. A central copy sits in Oracle Autonomous Database." |
| 13. Works offline | "It runs on one computer and keeps working with no connection. Providus: it suggests, a person decides. Thank you." |

## Before recording
- Rebuild first: `python -m backend.pipeline.build`. For a clean decisions log, delete `data/app.db` before the build.
- Leave the date on **Mon 28 Sep 2026**. Close other tabs and hide the bookmarks bar.
- Do one silent run of the tour first, so every screen is loaded and moves quickly.
- If you run long, shorten steps 5 and 7 to their first sentence. Never cut step 10.
