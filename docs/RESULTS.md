# Results

Written by `python -m backend.engine.backtest`. Do not edit by hand.
All data is the organisers' synthetic starter dataset.

## Demand forecast

**Test:** weekly forecast dates from 2026-07-06 to 2026-10-19 (16 Mondays, covering the August school holiday and term 3). On each date the forecast sees only earlier days and predicts units requested for the next 14 days, for every hospital, component and blood group (32 hospitals x 3 components x 8 groups = 768 series).

**Models:** `baseline` = The usual way (4-week average); `m1` = Our forecast (pooled gradient boosting).

**How to read the scores.** Lower is better for all but the last.
- MAE: average units off, per series and day.
- WAPE: total units off divided by total units requested. Daily demand per series is mostly zero, so daily WAPE is high for any method.
- MASE: error divided by the error of "same as this weekday last week". Below 1 beats that naive rule.
- 7-day WAPE: the same, on totals for the first 7 days. Orders follow delivery cycles, so this is closer to how the forecast is used.
- Range hit: share of days where real demand fell inside the forecast's p10 to p90 range. A well-set range hits about 80%.

### All series

| segment | units requested | MAE (baseline) | WAPE (baseline) | MASE (baseline) | 7-day WAPE (baseline) | range hit (baseline) | MAE (model) | WAPE (model) | MASE (model) | 7-day WAPE (model) | range hit (model) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all series | 20,679 | 0.164 | 135.6% | 0.93 | 71.3% | 95% | 0.160 | 132.8% | 0.91 | 67.9% | 96% |

### By component

| segment | units requested | MAE (baseline) | WAPE (baseline) | MASE (baseline) | 7-day WAPE (baseline) | range hit (baseline) | MAE (model) | WAPE (model) | MASE (model) | 7-day WAPE (model) | range hit (model) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FFP | 1,031 | 0.035 | 192.7% | 0.95 | 170.9% | 97% | 0.035 | 194.1% | 0.96 | 170.2% | 97% |
| PLT | 815 | 0.027 | 187.8% | 1.08 | 138.3% | 99% | 0.026 | 180.2% | 1.04 | 134.5% | 99% |
| RBC | 18,833 | 0.430 | 130.2% | 0.92 | 63.0% | 88% | 0.420 | 127.4% | 0.90 | 59.4% | 92% |

### Common against rare blood groups

| segment | units requested | MAE (baseline) | WAPE (baseline) | MASE (baseline) | 7-day WAPE (baseline) | range hit (baseline) | MAE (model) | WAPE (model) | MASE (model) | 7-day WAPE (model) | range hit (model) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| common (O+, A+, B+) | 18,867 | 0.384 | 130.8% | 0.91 | 63.6% | 90% | 0.375 | 127.6% | 0.89 | 60.2% | 94% |
| rare (all others) | 1,812 | 0.032 | 186.3% | 1.02 | 152.2% | 97% | 0.032 | 186.9% | 1.03 | 148.6% | 98% |

### By facility type (our fairness check: no kind of hospital should be served clearly worse)

| segment | units requested | MAE (baseline) | WAPE (baseline) | MASE (baseline) | 7-day WAPE (baseline) | range hit (baseline) | MAE (model) | WAPE (model) | MASE (model) | 7-day WAPE (model) | range hit (model) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| county_hospital | 1,589 | 0.112 | 150.3% | 0.92 | 86.2% | 96% | 0.112 | 150.8% | 0.93 | 80.2% | 97% |
| county_referral | 11,333 | 0.144 | 142.8% | 0.91 | 75.1% | 95% | 0.142 | 140.4% | 0.89 | 72.1% | 97% |
| maternity_hospital | 858 | 0.224 | 139.5% | 0.97 | 70.7% | 92% | 0.210 | 130.8% | 0.91 | 63.3% | 94% |
| mission_hospital | 452 | 0.139 | 164.3% | 1.01 | 104.7% | 95% | 0.139 | 164.2% | 1.01 | 95.3% | 96% |
| national_referral | 4,933 | 0.484 | 105.1% | 0.93 | 47.9% | 89% | 0.472 | 102.3% | 0.90 | 47.0% | 93% |
| private_hospital | 1,040 | 0.149 | 153.7% | 1.05 | 92.7% | 94% | 0.144 | 148.5% | 1.01 | 83.2% | 96% |
| sub_county_hospital | 474 | 0.140 | 158.1% | 1.00 | 97.1% | 95% | 0.130 | 146.6% | 0.93 | 90.3% | 96% |

### By region

| segment | units requested | MAE (baseline) | WAPE (baseline) | MASE (baseline) | 7-day WAPE (baseline) | range hit (baseline) | MAE (model) | WAPE (model) | MASE (model) | 7-day WAPE (model) | range hit (model) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Eldoret | 2,867 | 0.173 | 129.5% | 0.96 | 69.6% | 94% | 0.167 | 125.0% | 0.93 | 65.7% | 96% |
| Embu | 2,122 | 0.122 | 153.7% | 0.98 | 86.3% | 95% | 0.118 | 148.3% | 0.95 | 81.4% | 97% |
| Kisumu | 3,306 | 0.145 | 140.8% | 0.91 | 70.6% | 95% | 0.142 | 137.7% | 0.89 | 67.2% | 97% |
| Mombasa | 2,732 | 0.170 | 133.0% | 0.86 | 70.6% | 95% | 0.167 | 131.2% | 0.85 | 67.2% | 96% |
| Nairobi | 7,139 | 0.211 | 126.5% | 0.91 | 63.5% | 94% | 0.209 | 125.3% | 0.90 | 60.6% | 96% |
| Nakuru | 2,513 | 0.140 | 149.5% | 0.97 | 84.5% | 95% | 0.136 | 145.2% | 0.94 | 81.1% | 96% |

### Did the model beat the baseline?

- MAE: baseline 0.164, model 0.160 (2.1% better).
- WAPE: baseline 135.6%, model 132.8% (2.1% better).
- 7-day WAPE: baseline 71.3%, model 67.9% (4.9% better).

**Plainly:** the model beats the 4-week average on demand, by a small margin. Demand in this dataset is nearly flat through the year, so there is little for any model to find. The larger gain is in the supply forecast below.

### Rare series

A series is rare when at least three quarters of its last 26 weeks had no request (82% of series). We do not chase precision on these. On 4 dates before the test window, the baseline had MAE 0.0250 on rare series and the pooled model 0.0269, so rare series use the **baseline**. The staff-set minimum stock protects these groups.

## Supply forecast (red cells and whole blood)

Demand is nearly flat through the year and supply is what swings, so this is where a forecast can add most. **Test:** the same 16 Mondays, 1 to 4 weeks ahead, all blood groups added up. The model uses the drive schedule (never emergency appeals, which are not planned), the usual yield per kind of venue, the share of collections that become usable units, and the testing wait, all learned from days before each forecast date.

- MAE: average units off per place and week. WAPE: total units off divided by the real total.
- Bias: average of forecast minus real. Below zero means the forecast runs low.

### Cleared units per regional centre and week

Baseline: average of the last 4 weeks.

| weeks ahead | checks | MAE (baseline) | MAE (model) | WAPE (baseline) | WAPE (model) | bias (baseline) | bias (model) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all weeks ahead | 348 | 69.4 | 31.2 | 58% | 26% | +7.7 | -25.8 |
| 1 week ahead | 96 | 65.0 | 27.1 | 55% | 23% | +5.9 | -23.3 |
| 2 weeks ahead | 90 | 69.2 | 31.5 | 58% | 27% | +7.3 | -25.4 |
| 3 weeks ahead | 84 | 69.6 | 32.8 | 58% | 27% | +7.7 | -27.0 |
| 4 weeks ahead | 78 | 75.0 | 34.1 | 63% | 29% | +10.4 | -28.3 |

### Routine units received per hospital and week

Baseline: the hospital's average of the last 4 weeks.

| weeks ahead | checks | MAE (baseline) | MAE (model) | WAPE (baseline) | WAPE (model) | bias (baseline) | bias (model) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all weeks ahead | 1856 | 8.5 | 8.0 | 46% | 44% | +0.3 | -1.9 |
| 1 week ahead | 512 | 8.3 | 7.8 | 45% | 43% | +0.3 | -1.4 |
| 2 weeks ahead | 480 | 8.6 | 7.9 | 47% | 43% | +0.3 | -1.8 |
| 3 weeks ahead | 448 | 8.5 | 8.3 | 46% | 44% | +0.1 | -2.4 |
| 4 weeks ahead | 416 | 8.8 | 8.1 | 48% | 44% | +0.6 | -2.3 |

### Regional centre stock at the end of the week

Baseline: stock stays as it is today.

| weeks ahead | checks | MAE (baseline) | MAE (model) | WAPE (baseline) | WAPE (model) | bias (baseline) | bias (model) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all weeks ahead | 348 | 84.1 | 63.7 | 47% | 36% | +4.8 | -29.1 |
| 1 week ahead | 96 | 51.1 | 37.6 | 29% | 21% | +3.2 | -12.5 |
| 2 weeks ahead | 90 | 81.0 | 61.1 | 46% | 35% | +6.3 | -23.4 |
| 3 weeks ahead | 84 | 101.3 | 75.5 | 57% | 42% | +6.3 | -35.3 |
| 4 weeks ahead | 78 | 109.9 | 85.9 | 61% | 48% | +3.6 | -49.6 |

## Stock-out early warning

**Test:** the same 16 Mondays. For every series a hospital holds (red cells and plasma; hospitals hold no platelets): in the next 7 days, was a request not fully met, or did one need an emergency delivery? A zero-stock day is not counted as a shortage on its own, because many shelves are often empty in this dataset.

- Recall: of the real shortages, the share that had a warning. Higher is better.
- Precision: of the warnings, the share followed by a real shortage. Higher means fewer false alarms.
- Lead: median days from the warning to the first such request.

### All held series

| segment | method | real shortages | warnings | recall | precision | lead (days) |
| --- | --- | --- | --- | --- | --- | --- |
| all held series | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 485 | 1302 | 73% | 27% | 2 |
| all held series | Our alert (Act only), deliveries from the supply forecast, forecast: baseline | 485 | 431 | 42% | 48% | 1 |
| all held series | Our alert (Act or Watch), usual deliveries, forecast: baseline | 485 | 1276 | 72% | 27% | 1 |
| all held series | Simple rule (cover under 3 days on the 28-day average) | 485 | 1186 | 65% | 27% | 1 |
| all held series | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 485 | 1314 | 76% | 28% | 2 |
| all held series | Our alert (Act only), deliveries from the supply forecast, forecast: m1 | 485 | 435 | 45% | 50% | 1 |
| all held series | Our alert (Act or Watch), usual deliveries, forecast: m1 | 485 | 1288 | 74% | 28% | 2 |

### Stricter check: only requests that were not fully met

| segment | method | real shortages | warnings | recall | precision | lead (days) |
| --- | --- | --- | --- | --- | --- | --- |
| all held series | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 272 | 1302 | 81% | 17% | 1 |
| all held series | Our alert (Act only), deliveries from the supply forecast, forecast: baseline | 272 | 431 | 45% | 29% | 1 |
| all held series | Our alert (Act or Watch), usual deliveries, forecast: baseline | 272 | 1276 | 79% | 17% | 1 |
| all held series | Simple rule (cover under 3 days on the 28-day average) | 272 | 1186 | 72% | 16% | 1 |
| all held series | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 272 | 1314 | 82% | 17% | 1 |
| all held series | Our alert (Act only), deliveries from the supply forecast, forecast: m1 | 272 | 435 | 48% | 30% | 1 |
| all held series | Our alert (Act or Watch), usual deliveries, forecast: m1 | 272 | 1288 | 80% | 17% | 1 |

### By component

| segment | method | real shortages | warnings | recall | precision | lead (days) |
| --- | --- | --- | --- | --- | --- | --- |
| FFP | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 0 | 25 | n/a | 0% | n/a |
| FFP | Simple rule (cover under 3 days on the 28-day average) | 0 | 40 | n/a | 0% | n/a |
| FFP | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 0 | 24 | n/a | 0% | n/a |
| RBC | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 485 | 1277 | 73% | 28% | 2 |
| RBC | Simple rule (cover under 3 days on the 28-day average) | 485 | 1146 | 65% | 28% | 1 |
| RBC | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 485 | 1290 | 76% | 29% | 2 |

### By facility type

| segment | method | real shortages | warnings | recall | precision | lead (days) |
| --- | --- | --- | --- | --- | --- | --- |
| county_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 35 | 123 | 63% | 18% | 2 |
| county_hospital | Simple rule (cover under 3 days on the 28-day average) | 35 | 99 | 37% | 13% | 2 |
| county_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 35 | 129 | 66% | 18% | 2 |
| county_referral | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 368 | 920 | 77% | 31% | 1 |
| county_referral | Simple rule (cover under 3 days on the 28-day average) | 368 | 856 | 71% | 31% | 1 |
| county_referral | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 368 | 924 | 80% | 32% | 1 |
| maternity_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 14 | 49 | 64% | 18% | 3 |
| maternity_hospital | Simple rule (cover under 3 days on the 28-day average) | 14 | 48 | 57% | 17% | 2 |
| maternity_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 14 | 46 | 64% | 20% | 3 |
| mission_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 5 | 34 | 20% | 3% | 3 |
| mission_hospital | Simple rule (cover under 3 days on the 28-day average) | 5 | 28 | 0% | 0% | n/a |
| mission_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 5 | 34 | 20% | 3% | 3 |
| national_referral | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 15 | 59 | 40% | 10% | 4 |
| national_referral | Simple rule (cover under 3 days on the 28-day average) | 15 | 60 | 47% | 12% | 4 |
| national_referral | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 15 | 65 | 53% | 12% | 4 |
| private_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 38 | 91 | 76% | 32% | 2 |
| private_hospital | Simple rule (cover under 3 days on the 28-day average) | 38 | 73 | 61% | 32% | 2 |
| private_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 38 | 93 | 79% | 32% | 2 |
| sub_county_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: baseline | 10 | 26 | 40% | 15% | 1 |
| sub_county_hospital | Simple rule (cover under 3 days on the 28-day average) | 10 | 22 | 30% | 14% | 1 |
| sub_county_hospital | Our alert (Act or Watch), deliveries from the supply forecast, forecast: m1 | 10 | 23 | 40% | 17% | 1 |

