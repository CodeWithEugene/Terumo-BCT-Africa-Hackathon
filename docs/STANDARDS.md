# Standards: how this workflow connects to a wider blood-bank information system

All data is the organisers' synthetic starter dataset. Nothing here has been tested against a live system.

## Where this tool sits

A blood-bank information system (BBIS) records donors, donations, testing, labelling, issue and transfusion.
This tool does none of that. It reads **counts** out of such a system (stock, requests, deliveries, drives),
forecasts shortages, and hands **orders** back as requests that a person has approved.

```
BBIS / hospital stock book  ──counts──▶  Providus  ──approved order (FHIR SupplyRequest)──▶  regional centre
                                                │
                                                └──monthly indicators (DHIS2 dataValueSet)──▶  national reporting
```

## Mapping

| Our table or output | Standard | How it maps | Status |
| --- | --- | --- | --- |
| Accepted or changed order (`decision`) | HL7 FHIR R4 `SupplyRequest` | `GET /fhir/SupplyRequest/{decision_id}`. Uses `identifier`, `status`, `category`, `priority`, `itemCodeableConcept`, `quantity`, `occurrenceDateTime`, `authoredOn`, `requester`, `supplier`, `reasonCode`, `deliverFrom`, `deliverTo`. | Field names checked against https://hl7.org/fhir/R4/supplyrequest.html on 10 Nov 2026. Not run through a FHIR validator. |
| `facility` | FHIR `Organization` / `Location`; DHIS2 organisation unit | Referenced as `Organization/<facility_id>`. | Our IDs are the dataset's, not a national facility registry code (in Kenya, the Master Facility List code). |
| Product and blood group | ISBT 128 product description codes; ABO/RhD codes | Sent as text plus a local code such as `RBC|O-`. | **Stand-in.** Real use needs ISBT 128 product codes. |
| `unit.unit_id` | ISBT 128 Donation Identification Number (DIN) | The dataset's unit label stands in for a DIN. We replace it with a scrambled code at build time, so it cannot be linked back. | Stand-in, pseudonymised. |
| `stock_daily` | FHIR `SupplyDelivery` / inventory report; DHIS2 stock data elements | Read-only input. | Not exported. |
| `demand_daily` | FHIR `ServiceRequest` (a blood request) counted per day | Aggregated before storage; no request-level record is kept. | Input only. |
| Monthly indicators | DHIS2 `dataValueSets` | `GET /export/dhis2` returns `dataElement`, `period` (YYYYMM), `orgUnit`, `value`. | **Illustrative mapping.** The element and org-unit IDs are made up; we have no DHIS2 instance to map to. |
| `audit_log` | FHIR `AuditEvent` / `Provenance` | Same content (who, when, what was shown, what was decided). | Not exported as FHIR yet. |

## What would be needed for real use

- ISBT 128 product codes and the national facility codes.
- A FHIR validator run, and agreement with the receiving system on a profile.
- Real DHIS2 data element and organisation unit IDs from the ministry's instance.
- A signed connection (mutual TLS or OAuth 2.0) between systems; today the endpoints use the app's own sign-in.
