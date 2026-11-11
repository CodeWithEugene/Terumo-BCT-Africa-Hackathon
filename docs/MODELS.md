# How the forecasts work

All of this runs on the organisers' synthetic dataset. Every number quoted comes from `docs/RESULTS.md`.

## The idea in one paragraph
Demand for blood in this dataset is steady through the year. Supply is what swings, and it swings with the
school calendar because over half of collections come from school and university drives. So the tool
forecasts supply from the drive schedule, forecasts demand per hospital and blood group, walks every shelf
14 days forward, and then asks one more question: given what the centre will have, which shelf should each
unit go to?

## 1. Supply forecast (4 weeks ahead, per regional centre)
A transparent calculation, not a black box. For each scheduled drive:

`expected usable units = usual collections for that kind of venue × usable units per donation`

then shifted by the testing wait and split by the centre's usual blood group mix.

- **Usual collections per venue** (school, church, workplace...) are learned per centre from past drives.
- **Usable units per donation** covers deferrals and screening: it is learned from donations old enough to
  have been tested.
- **Testing wait** is the real spread of days between collection and release, per collecting site.
- **Emergency appeals are never counted** as planned supply. They are a reaction to a shortage.
- Baseline: the average of the last 4 weeks. Result: 58% error down to 26%.

## 2. Demand forecast (14 days ahead, per hospital, product and blood group)
- **Baseline:** the average of the same weekday over the last 4 weeks. This is what a careful officer does
  in their head.
- **Model:** one gradient-boosting model (scikit-learn `HistGradientBoostingRegressor`) trained across all
  32 hospitals at once, on weekly requests. Pooling lets a small hospital borrow strength from the rest.
  - Inputs: the last 8 weeks of requests and their averages, the share of weeks with no request, the
    hospital's type, level, beds and region, the product and blood group, the week of the year, school in
    session, days to the next school break, public holidays, the malaria season, and the recent share of
    emergency requests, and the recent totals for the hospital and for the blood group across the region.
  - Three models are fitted: one for the expected demand (Poisson loss, which suits counts) and two for the
    range (the 10th and 90th percentiles, by quantile loss).
  - The weekly forecast is shared out over days by each series' own weekday pattern.
- **Rare series** (most weeks have no request: 82% of series) use the baseline, chosen on dates before the
  test period, and are protected by a minimum stock that staff set.
- Result: 71.3% error on 7-day totals down to 67.9%.

## 3. Stock projection and the chance of running out
For each hospital, product and blood group:

`stock tomorrow = stock today + expected delivery − expected use − units expiring`

- Units are issued oldest first, using each unit's real expiry date.
- Deliveries come from the supply forecast: what the centre is expected to ship, times the hospital's recent
  share.
- The **range** treats busy and quiet days as partly cancelling out, so a fortnight's range is narrower than
  14 daily ranges added up.
- The **chance of running out** comes from 400 simulated demand paths drawn as counts around the forecast.
- **Status:** Act if at least one unit short is expected before the next delivery; Watch if that happens only
  in a busy spell, later in the fortnight, or stock is under the staff minimum; otherwise Steady.

## 4. Fair-share allocation
When a centre sends out units of a blood group, each unit goes to the hospital that would otherwise have the
fewest days of cover. Staff can protect a minimum for referral hospitals. Only hospitals with a delivery
that weekday receive, so the delivery rounds stay as they are.

The **replay** takes the test period, keeps the same requests and the same units leaving each centre on the
same days, and walks every shelf forward twice: as it happened, and with the rule. Result: 32% fewer units
that a hospital's own shelf could not supply.

## How it was tested
- **Rolling-origin backtest:** 16 Mondays from 6 July to 19 October 2026. On each date, every model is
  trained from scratch on earlier days only, then compared with what happened next.
- **No tuning on the test period.** The one modelling choice (how to treat rare series) was made on four
  dates in June.
- **Measures:** total units off divided by total units (never a percentage per day, because most days are
  zero), a cost where a unit short counts five times a unit left over, and how often the truth fell inside
  the stated range.
- **Fairness check:** results are reported by kind of hospital, so no group is served clearly worse.

## Oracle Analytics and Oracle Machine Learning
The central copy in Oracle Autonomous Database holds weekly demand, daily stock, the accuracy scores and the
coded decisions log. Two things follow:

- **Oracle Analytics Cloud** can connect to those tables today for national dashboards: stock by region,
  shortage days by blood group, decisions over time. No code change is needed in the tool.
- **Oracle Machine Learning** runs inside the same database. The demand model could be retrained there on
  pooled data from many sites, with each site still forecasting locally and offline. That is a natural next
  step, and it is not built yet.
