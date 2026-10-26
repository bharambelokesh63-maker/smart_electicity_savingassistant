"""Recommendation engine.

Recommendations are produced by the forward-chaining rule engine in
``ai.forward_chaining`` (so the lab page and this page agree), then ranked by

    score = estimated monthly saving (Rs) x feasibility (0-1)

Feasibility reflects how easy the change is, using the appliance's priority and the
type of change (see constants in ``ai.forward_chaining``).  All savings are estimates
derived from the user's own appliance data and the stated assumptions.
"""
from ai.forward_chaining import run_forward_chaining


def generate_recommendations(appliances, tariff, config=None, params=None):
    fc = run_forward_chaining(appliances, tariff, config, params)
    recs = fc["recommendations"]
    best_per_appliance = {}
    for r in recs:
        cur = best_per_appliance.get(r["appliance_id"])
        if cur is None or r["monthly_rs_saved"] > cur["monthly_rs_saved"]:
            best_per_appliance[r["appliance_id"]] = r
    totals = {
        "count": len(recs),
        "monthly_kwh_saved": sum(r["monthly_kwh_saved"] for r in best_per_appliance.values()),
        "monthly_rs_saved": sum(r["monthly_rs_saved"] for r in best_per_appliance.values()),
    }
    return {
        "recommendations": recs, "flagged_for_review": fc["flagged_for_review"], "totals": totals,
        "notes": [
            "All savings are ESTIMATES derived from the appliance data you entered, not measured values.",
            "Totals count only the single best recommendation per appliance, so overlapping advice is not double counted.",
            "Ranking = estimated monthly saving (Rs) x feasibility, where feasibility depends on appliance priority and "
            "the type of change.",
        ],
        "stats": fc["stats"],
    }
