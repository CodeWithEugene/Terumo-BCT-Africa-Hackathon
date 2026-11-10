# Design — Providus

The feeling: a clean, quiet, well-lit clinical room. Nothing shouts. A blood bank officer opens it with
their morning tea, knows in five seconds whether today is fine, and acts in three clicks when it is not.
If you have a frontend design skill available, load it, then follow this file where the two differ.

## 1. Principles (in priority order)

1. **Answer first.** Every screen opens with one plain sentence that says what matters now.
   "Two groups need attention before Friday's delivery." Then the detail.
2. **Calm by default, loud only when earned.** Most of the screen is neutral. Colour appears only where
   a person needs to act. A day with no alerts should feel good to look at, not empty.
3. **One number, one meaning.** Days of cover is the main number everywhere. Units are secondary.
4. **Show the doubt.** Every forecast has a range, drawn as a soft band and written in words
   ("3 days, could be 2 if the weekend is busy").
5. **People decide.** The action buttons are the clearest thing on the detail panel. The system's
   suggestion is presented as a suggestion, with its reasons beside it.
6. **Never colour alone.** Every status has a word and an icon as well as a colour.
7. **Fast and light.** No spinners longer than a moment; skeletons that match the final layout; payloads
   small enough for a 3G connection.

What keeps people coming back is not decoration. It is: it is right often enough, it is fast, it never
nags, and "all steady" is a real, restful state. Research on which exact hue is most calming is thin.
Low-saturation blue-greens and generous white space are a safe, widely used choice. The dependable levers
are low clutter, consistent hierarchy and few, trustworthy alerts.

## 2. Colour tokens

Define as CSS variables and Tailwind theme colours. Use these names, not raw hex, in components.

| Token | Hex | Use |
| --- | --- | --- |
| `bg` | `#F5F9F9` | Page background, a cool off-white |
| `surface` | `#FFFFFF` | Cards, panels |
| `line` | `#E4ECED` | Hairlines, bar tracks |
| `ink` | `#12303A` | Primary text, deep slate-teal instead of black |
| `muted` | `#52686F` | Secondary text |
| `primary` | `#0B6E6E` | Primary buttons, links, focus ring, selected nav |
| `primary-soft` | `#E2F2F0` | Selected backgrounds, hover |
| `steady` / `steady-soft` | `#1F6F54` / `#E6F4EE` | Status text / background |
| `watch` / `watch-soft` | `#8A5A0B` / `#FCF1D9` | Status text / background |
| `act` / `act-soft` | `#A8322C` / `#FBE8E6` | Status text / background. A muted brick red. |
| `band` | `#9CC9D6` at 35% | Forecast range band |
| `fill-steady`, `fill-watch`, `fill-act` | `#3FA07E`, `#B8821A`, `#CF5A52` | Cover-bar fills |

Rules:
- Text on its background must reach 4.5:1 contrast; bar fills and icons 3:1. The text pairs above were
  checked. **Verify the three bar fills and adjust darker if any falls short.**
- **Red is rationed.** This is a blood product, so red is tempting. Use `act` only for the Act status
  and the stock-out marker. No red logo, no red headings, no decorative blood drops.
- No pure black, no pure saturated colours, no gradients except a barely visible one on the page
  background if it helps depth. No drop shadows heavier than `0 1px 2px rgba(18,48,58,.06)`.
- Light theme only. Do not spend time on dark mode.

## 3. Type

- Family: **Figtree** for everything (self-hosted with `@fontsource/figtree`), system sans fallback.
- Numbers use `font-variant-numeric: tabular-nums` everywhere so columns do not jitter.
- Scale: 13 / 14 (body) / 16 / 20 / 28 / 40. Line height 1.5 body, 1.15 for large numbers.
- Weights: 400 body, 500 labels, 600 headings and key numbers. Nothing bolder.
- Sentence case for all labels and headings. No all-caps except the blood group symbols.
- Blood groups are set large and proud: `O−`, `AB+`. Use the true minus sign (−), not a hyphen.

## 4. Layout

- 8px spacing grid. Cards have 20–24px padding and a 14px radius. Hairline borders, not shadows.
- Desktop: a narrow left rail (icons with labels, 208px), content max width 1120px, generous margins.
- Phone (360px): rail becomes a bottom bar; rack becomes one column; detail panel becomes a full page.
- Density is "comfortable", never cramped. If a screen feels busy, remove something.

## 5. Signature components

**The brief line.** Top of the home screen, 28px, one sentence, generated from the data:
"Good morning. Two groups need attention before Friday's delivery." or "All eight groups are steady
through Friday." Under it, a quiet line: as-of date, next delivery day, mode.

**The rack.** Eight tiles, one per blood group, like tubes in a rack. Each tile shows:
- the group symbol, large;
- **days of cover** as the main number ("3.2 days");
- a **cover bar**: a horizontal track whose fill is days of cover, with a small tick where the next
  delivery falls. If the fill ends before the tick, the shortage is visible at a glance, no legend needed.
  A lighter extension shows the worst case;
- units on shelf, small;
- status word with icon: Steady, Watch, Act.
Tiles needing attention come first and carry their soft status background. Steady tiles stay white.
Hover or focus lifts the tile by one pixel of border colour, nothing more.

**The projection chart.** In the detail panel. A 14-day line of projected stock with the range band,
vertical dashed markers for deliveries, a small marker where stock reaches zero, weekend shading barely
visible. Hand-built SVG. Axis labels in words ("Fri 7", "Mon 10"). Direct labels on the line instead of
a legend. No gridlines except a zero line.

**Reasons.** Two or three short sentences, each with a small neutral icon. No percentages without what
they are a percentage of.

**The decision bar.** Suggested quantity with a stepper, then three buttons:
`Accept` (primary, filled), `Change` (outline), `Reject` (text). Changing or rejecting opens a short
reason list inline, not a modal. After deciding, the bar collapses to "Accepted by Amina W., 08:14"
with a small undo window of 10 seconds.

**The regional grid.** Hospitals down, blood groups across, each cell a small rounded square in the
status colour with the days of cover inside. Sorted by urgency. It should read like a calm heat strip,
not a spreadsheet. Row hover reveals the hospital's next delivery.

**The accuracy page.** Title: "How well is this working?" Two plain cards side by side: "The usual way
(4-week average)" and "Our forecast", each with one headline number and a sentence that explains it.
Then the by-facility-type table. Then the fallback switch with one sentence on what it does.

**Empty and all-clear states.** A small, soft line illustration (a simple rack outline, drawn in SVG,
`line` colour) and one sentence. No stock photos, no emoji.

## 6. Motion

Small and purposeful. 150–200ms ease-out. Cover bars fill once on load (300ms). Panels slide 8px and
fade. Status changes cross-fade. Respect `prefers-reduced-motion`. No bouncing, no pulsing alerts.

## 7. Words

- Plain, kind, specific. "Runs out Thursday afternoon" beats "Stock-out risk: HIGH".
- Say "suggested", never "recommended by AI" or "AI decided".
- Units of blood are "units". Days are "days of cover".
- Dates in words: "Fri 7 Aug". 24-hour time.
- Errors say what happened and what to do: "Could not reach the server. Showing this morning's brief."
- The fallback mode chip reads: "Fallback: using the 4-week average".

## 8. Accessibility and reach

- Full keyboard path: Tab through tiles, Enter opens, A / C / R for the three decisions when the panel
  is open (show the hint quietly).
- Visible focus ring in `primary`, 2px, offset 2px.
- Every chart has a text summary beside it and a table view toggle.
- Touch targets at least 44px. Works at 360px wide. Total JS under 300KB gzipped if possible.
- Language strings live in one file (`frontend/src/i18n/en.ts`) so Swahili can be added by settings.

## 9. Do not

- Do not use a generic admin template look: no dark sidebar with white icons, no rainbow KPI tiles,
  no pie or donut charts, no gauge dials, no 3D, no chart with more than two colours plus the band.
- Do not show more than one "Act" style per card.
- Do not use red for anything that is not urgent.
- Do not put a logo-sized blood drop anywhere.
- Do not add a chatbot.
