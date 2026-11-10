"""Standards-shaped outputs so this workflow can plug into a wider blood-bank system.

- FHIR R4 SupplyRequest for an accepted order. Field names were checked against
  https://hl7.org/fhir/R4/supplyrequest.html on 10 Nov 2026. The payload has not
  been run through a FHIR validator, and the product codes are local stand-ins.
- DHIS2 dataValueSets-shaped monthly aggregates. The element and org-unit IDs
  are illustrative: we do not have a real DHIS2 instance to map to.
"""
from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from backend.api.auth import User, scope
from backend.db.core import read
from backend.engine.world import get_world

LOCAL_SYSTEM = "https://example.org/sanguis-providus"
PRODUCT_TEXT = {"RBC": "Red cells (red cell units or whole blood)", "FFP": "Fresh frozen plasma", "PLT": "Platelets"}


def supply_request(user: User, decision_id: int) -> dict:
    rows = read("SELECT * FROM decision WHERE decision_id = ?", (decision_id,)).to_dict("records")
    if not rows or rows[0]["facility_id"] not in scope(user):
        raise HTTPException(status_code=404, detail="That decision was not found.")
    d = rows[0]
    if d["suggestion_kind"] in ("drive", "allocation") or d["action"] == "reject" or d["final_quantity"] <= 0:
        raise HTTPException(status_code=400, detail="Only an accepted or changed order can be shown as a supply request.")
    facility = get_world().facility
    hospital, centre = facility.loc[d["facility_id"]], facility.loc[facility.at[d["facility_id"], "region"]]
    urgent = d["suggestion_kind"] == "early_delivery"
    withdrawn = d["withdrawn_at"] is not None and not pd.isna(d["withdrawn_at"])
    return {
        "resourceType": "SupplyRequest",
        "id": f"decision-{d['decision_id']}",
        "meta": {"tag": [{"system": f"{LOCAL_SYSTEM}/tag", "code": "synthetic-demo",
                          "display": "Synthetic demo data. FHIR-shaped, checked against the R4 field list, not validated."}]},
        "identifier": [{"system": f"{LOCAL_SYSTEM}/decision", "value": str(d["decision_id"])}],
        "status": "cancelled" if withdrawn else "active",
        "category": {"text": "Blood component order"},
        "priority": "urgent" if urgent else "routine",
        "itemCodeableConcept": {
            "coding": [{"system": f"{LOCAL_SYSTEM}/product", "code": f"{d['component']}|{d['blood_group']}",
                        "display": f"{PRODUCT_TEXT[d['component']]}, group {d['blood_group']}"}],
            "text": f"{PRODUCT_TEXT[d['component']]}, blood group {d['blood_group']}",
        },
        "quantity": {"value": int(d["final_quantity"]), "unit": "unit", "system": "http://unitsofmeasure.org", "code": "{unit}"},
        "occurrenceDateTime": d["for_date"],
        "authoredOn": d["created_at"],
        # The requester is the hospital, not a named person. Who decided is in the audit log.
        "requester": {"reference": f"Organization/{d['facility_id']}", "display": hospital["name"]},
        "supplier": [{"reference": f"Organization/{centre.name}", "display": centre["name"]}],
        "reasonCode": [{"text": "Early delivery requested: shelf projected to run out before the next routine delivery"
                        if urgent else "Routine order from the stock projection, decided by the blood bank officer"}],
        "deliverFrom": {"reference": f"Organization/{centre.name}", "display": centre["name"]},
        "deliverTo": {"reference": f"Organization/{d['facility_id']}", "display": hospital["name"]},
    }


def dhis2_export(user: User) -> dict:
    """Monthly red cell indicators per hospital, in the shape of a DHIS2 dataValueSet."""
    allowed = scope(user)
    marks = ",".join("?" for _ in allowed)
    demand = read(f"SELECT facility_id, substr(date, 1, 7) AS month, SUM(units_requested) r, SUM(units_issued) i, "
                  f"COUNT(DISTINCT CASE WHEN shortage_requests > 0 THEN date END) days "
                  f"FROM demand_daily WHERE component = 'RBC' AND facility_id IN ({marks}) GROUP BY 1, 2", tuple(allowed))
    waste = read(f"SELECT current_facility_id AS facility_id, substr(status_date, 1, 7) AS month, COUNT(*) n FROM unit "
                 f"WHERE status IN ('expired', 'discarded_temperature') AND component IN ('RBC', 'WB') "
                 f"AND current_facility_id IN ({marks}) GROUP BY 1, 2", tuple(allowed))
    wasted = {(w["facility_id"], w["month"]): int(w["n"]) for w in waste.to_dict("records")}
    values = []
    for row in demand.to_dict("records"):
        period, org = row["month"].replace("-", ""), row["facility_id"]
        fill = round(100 * row["i"] / row["r"], 1) if row["r"] else None
        for element, value in (("SP_RBC_SHORTAGE_DAYS", int(row["days"])), ("SP_RBC_FILL_RATE_PCT", fill),
                               ("SP_RBC_UNITS_WASTED", wasted.get((org, row["month"]), 0))):
            if value is not None:
                values.append({"dataElement": element, "period": period, "orgUnit": org, "value": str(value)})
    return {
        "note": "Illustrative mapping on synthetic data. The dataElement and orgUnit IDs are stand-ins, "
                "not real DHIS2 identifiers.",
        "dataElements": {
            "SP_RBC_SHORTAGE_DAYS": "Days in the month with a red cell request not fully met or needing an emergency delivery",
            "SP_RBC_FILL_RATE_PCT": "Red cell units issued as a percentage of units requested",
            "SP_RBC_UNITS_WASTED": "Red cell and whole blood units expired or discarded at the hospital",
        },
        "dataSet": "SP_BLOOD_STOCK_MONTHLY", "dataValues": values,
    }
