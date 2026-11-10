# Data facts

Written by `python -m backend.pipeline.build`. Do not edit by hand.
All data is the organisers' **synthetic** starter dataset. These numbers describe the model dataset, not any real hospital or blood centre.

Period: 2025-11-01 to 2026-10-31. 32 hospitals.

## Headline numbers

- **17,430 requests for 34,242 units.** 12.9% of requests were not fully met. 86.6% of requested units were issued (4,592 units short).
- **O negative patients fare worst:** 43.8% of O negative units requested were not issued, against 16.5% for O positive.
- **Wastage:** 23.2% of red cell and whole blood units were wasted (4,901 expired, 3,719 discarded after a fridge or cool box went out of range).
- **Emergency resupply:** 2,670 requests needed an emergency delivery. Median time from request to last unit at the bedside: 5.2 hours (1 in 10 took more than 14.8 hours).
- **Empty shelves are common:** across hospitals and the 8 groups, the red cell shelf (red cells plus whole blood) was empty at the end of 59.9% of days. There were 1,720 hospital-group-days with a red cell request that was not fully met.
- **School breaks:** collections averaged 868 a week in term time and 544 a week in school breaks (37.4% lower). 56.1% of all collections came from secondary school and university drives.
- **Demand is sparse:** 420 hospital, component and group series had any request. The median series had no request on 98.1% of days, and 71.9% of series ask for less than one unit a week.
- **Whole blood fills red cell requests:** 23.3% of the 27,273 units issued for red cell requests were whole blood. We therefore count red cells and whole blood together as red cell cover.
- **Not flagged:** 2,119 units were transfused after being in a fridge or cool box that went out of range.

## Requests by component

| component | requests | units_requested | unmet_units | unmet % | issued from own shelf % |
| --- | --- | --- | --- | --- | --- |
| FFP | 843 | 1832 | 94 | 5.1 | 50.6 |
| PLT | 378 | 1294 | 655 | 50.6 | 0.0 |
| RBC | 16209 | 31116 | 3843 | 12.4 | 85.9 |

Hospitals in this dataset hold no platelets, so every platelet request waits for a delivery.

## Unmet units by blood group

| blood_group | units_requested | unmet_units | unmet % |
| --- | --- | --- | --- |
| O+ | 15382 | 2537 | 16.5 |
| A+ | 8538 | 815 | 9.5 |
| B+ | 6653 | 644 | 9.7 |
| AB+ | 1350 | 47 | 3.5 |
| O- | 641 | 281 | 43.8 |
| A- | 383 | 94 | 24.5 |
| B- | 359 | 81 | 22.6 |
| AB- | 106 | 29 | 27.4 |
| unknown | 830 | 64 | 7.7 |

## Unmet units by month

| month | units_requested | unmet_units | unmet % |
| --- | --- | --- | --- |
| 2025-11 | 2874 | 985 | 34.3 |
| 2025-12 | 2740 | 779 | 28.4 |
| 2026-01 | 2886 | 522 | 18.1 |
| 2026-02 | 2720 | 98 | 3.6 |
| 2026-03 | 2965 | 192 | 6.5 |
| 2026-04 | 2751 | 396 | 14.4 |
| 2026-05 | 2838 | 232 | 8.2 |
| 2026-06 | 2798 | 251 | 9.0 |
| 2026-07 | 2874 | 291 | 10.1 |
| 2026-08 | 2983 | 198 | 6.6 |
| 2026-09 | 2850 | 202 | 7.1 |
| 2026-10 | 2963 | 446 | 15.1 |

## Red cell stock-outs by blood group (hospitals)

"Empty shelf" counts red cells plus whole blood. A group a hospital never holds counts as empty.

| blood_group | empty-shelf days % | days with an unmet request (all hospitals) |
| --- | --- | --- |
| O+ | 36.8 | 889 |
| A+ | 31.0 | 311 |
| B+ | 28.6 | 245 |
| AB+ | 39.4 | 11 |
| O- | 73.9 | 148 |
| A- | 84.3 | 58 |
| B- | 87.3 | 43 |
| AB- | 97.7 | 15 |

## Red cell stock-outs by hospital

| facility_id | name | facility_type | empty-shelf days % (average of 8 groups) | group-days with an unmet red cell request |
| --- | --- | --- | --- | --- |
| HSP-006 | Thika Level 5 Hospital | county_referral | 85.8 | 176 |
| HSP-005 | Kiambu County Referral Hospital | county_referral | 79.1 | 149 |
| HSP-032 | Garissa County Referral Hospital | county_referral | 91.4 | 123 |
| HSP-004 | Westlands Private Hospital | private_hospital | 61.4 | 120 |
| HSP-003 | City Maternity Hospital | maternity_hospital | 53.6 | 92 |
| HSP-002 | Eastlands County Hospital | county_hospital | 57.6 | 91 |
| HSP-007 | Kajiado County Referral Hospital | county_referral | 89.4 | 85 |
| HSP-028 | Meru Teaching and Referral Hospital | county_referral | 58.9 | 83 |
| HSP-029 | Kitui County Referral Hospital | county_referral | 68.2 | 67 |
| HSP-030 | Isiolo County Referral Hospital | county_referral | 80.5 | 62 |
| HSP-026 | Kericho County Referral Hospital | county_referral | 70.1 | 61 |
| HSP-024 | Narok County Referral Hospital | county_referral | 66.1 | 57 |
| HSP-010 | Msambweni County Referral Hospital | county_referral | 69.5 | 57 |
| HSP-009 | Kilifi County Hospital | county_referral | 57.0 | 52 |
| HSP-023 | Naivasha Sub-County Hospital | sub_county_hospital | 56.0 | 47 |
| HSP-027 | Embu Level 5 Hospital | county_referral | 58.3 | 42 |
| HSP-001 | National Referral Hospital (Nairobi) | national_referral | 16.4 | 40 |
| HSP-017 | Lake Region Mission Hospital | mission_hospital | 59.3 | 35 |
| HSP-025 | Highlands Private Hospital | private_hospital | 63.0 | 32 |
| HSP-031 | Marsabit County Referral Hospital | county_referral | 82.7 | 28 |
| HSP-016 | Migori County Referral Hospital | county_referral | 57.5 | 27 |
| HSP-021 | Lodwar County Referral Hospital | county_referral | 65.8 | 25 |
| HSP-020 | Iten County Hospital | county_hospital | 63.0 | 22 |
| HSP-014 | Siaya County Referral Hospital | county_referral | 57.9 | 22 |
| HSP-008 | Coast Teaching and Referral Hospital | county_referral | 25.7 | 19 |
| HSP-011 | Voi County Hospital | county_hospital | 55.6 | 19 |
| HSP-019 | Kapsabet County Hospital | county_hospital | 63.3 | 18 |
| HSP-012 | Kisumu County Referral Hospital | county_referral | 30.4 | 16 |
| HSP-013 | Homa Bay County Referral Hospital | county_referral | 52.7 | 16 |
| HSP-015 | Busia County Referral Hospital | county_referral | 60.1 | 14 |
| HSP-018 | Western Rift Teaching and Referral Hospital | national_referral | 29.8 | 14 |
| HSP-022 | Nakuru County Referral Hospital | county_referral | 29.8 | 9 |

## Wastage by component

Share of all units made in the period (units still in stock at the end are in the total).

| component | discarded_temperature | expired | in_stock | transfused | all units | wasted | wasted % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRYO | 0 | 54 | 504 | 0 | 558 | 54 | 9.7 |
| FFP | 0 | 54 | 6889 | 1738 | 8681 | 54 | 0.6 |
| PLT | 218 | 2164 | 19 | 639 | 3040 | 2382 | 78.4 |
| RBC | 1651 | 754 | 738 | 20924 | 24067 | 2405 | 10.0 |
| WB | 2068 | 4147 | 516 | 6349 | 13080 | 6215 | 47.5 |

## Emergency resupply time by region

| region | emergency resupplies | median hours |
| --- | --- | --- |
| Eldoret | 214 | 4.9 |
| Embu | 293 | 7.9 |
| Kisumu | 309 | 5.4 |
| Mombasa | 210 | 4.8 |
| Nairobi | 1282 | 4.4 |
| Nakuru | 362 | 5.5 |

## How sparse demand is

| component | series | median share of days with no request % | median units a week |
| --- | --- | --- | --- |
| FFP | 143 | 99.2 | 0.15 |
| PLT | 31 | 98.6 | 0.36 |
| RBC | 246 | 96.4 | 0.51 |

## Whole blood issued for red cell requests, by processing centre

| region | whole_blood | all_units | whole blood % |
| --- | --- | --- | --- |
| Eldoret | 589 | 4095 | 14.4 |
| Embu | 2810 | 2810 | 100.0 |
| Kisumu | 480 | 4712 | 10.2 |
| Mombasa | 293 | 3781 | 7.7 |
| Nairobi | 1570 | 8234 | 19.1 |
| Nakuru | 607 | 3641 | 16.7 |

## Collections by venue type, term time against school breaks

School break dates are in `config/calendar_ke.yaml`.

| venue type | collected a week, term time | collected a week, school breaks |
| --- | --- | --- |
| church | 76 | 123 |
| community_event | 49 | 62 |
| corporate | 50 | 72 |
| emergency_appeal | 56 | 21 |
| fixed_site_walk_in | 11 | 26 |
| market_or_stage | 36 | 44 |
| mosque | 28 | 35 |
| secondary_school | 385 | 10 |
| university_college | 176 | 149 |

## Supply and data quality

- 45,699 donation attempts in the period; 11.2% deferred; 7.9% of tested donations reactive and discarded.
- 3.0% of transfers have no arrival time (kept, marked "not confirmed arrived").
- 55 fridge readings were sensor faults and were dropped.
- 442 requests record the patient group as unknown. They count in hospital totals and are left out of per-group forecasts.
- Join key is always `facility_id`. The typed facility name is never read.
- The donor table is not in this repo and is never loaded.
