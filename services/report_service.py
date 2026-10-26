"""Builds the dashboard and report payloads and the CSV export from saved data."""
import csv
import io

from database import db as dbm
from ai.scheduling_problem import fmt_hour
from services import energy_calculator as ec
from services.recommendation_engine import generate_recommendations
from services.schedule_optimizer import optimize_schedule

DASHBOARD_MAX_EXPANSIONS = 5000


def _load_all(conn):
    appliances = dbm.list_appliances(conn)
    tariff = dbm.get_tariff(conn)
    config = dbm.get_setting(conn, "schedule_config", {}) or {}
    return appliances, tariff, config


def _scheduler_view(appliances, tariff, config):
    cfg = dict(config)
    cfg["max_expansions"] = DASHBOARD_MAX_EXPANSIONS
    return optimize_schedule(appliances, tariff, cfg, method="astar")


def build_dashboard(conn):
    appliances, tariff, config = _load_all(conn)
    if not appliances:
        return {"empty": True, "tariff": tariff, "totals": {
            "appliance_count": 0, "daily_kwh": 0.0, "monthly_kwh": 0.0, "estimated_bill": 0.0,
            "energy_charge": 0.0},
            "message": "No appliances yet. Add your appliances or load the demonstration data to see your dashboard."}
    summary = ec.summarize(appliances, tariff)
    recs = generate_recommendations(appliances, tariff, config)
    sched = _scheduler_view(appliances, tariff, config)
    rows = summary["rows"]
    top = max(rows, key=lambda r: r["monthly_kwh"])
    comp = sched["comparison"]
    return ec.round_floats({
        "empty": False, "tariff": tariff, "totals": summary["totals"],
        "potential_savings": recs["totals"],
        "top_appliance": {"name": top["name"], "monthly_kwh": top["monthly_kwh"],
                          "share_percent": top["share_percent"]},
        "recent_recommendations": recs["recommendations"][:5],
        "charts": {
            "appliances": [{"name": r["name"], "daily_kwh": r["daily_kwh"], "monthly_kwh": r["monthly_kwh"],
                            "energy_charge": r["energy_charge"], "category": r["category"]} for r in rows],
            "hourly_load": {
                "labels": [fmt_hour(h) for h in range(24)],
                "original": sched["original"]["hourly_load_kwh"],
                "optimized": sched["optimized"]["hourly_load_kwh"] if sched["optimized"] else None,
            },
        },
        "comparison": comp,
        "scheduler_method": sched["method"], "scheduler_fallback": sched["fallback"],
        "disclaimer": ("Monthly bill is an ESTIMATE: energy charge at your flat tariff plus the fixed charge and tax "
                       "percentage you entered. Real bills may include slabs, surcharges and meter-reading differences."),
    }, 3)


def build_report(conn):
    appliances, tariff, config = _load_all(conn)
    if not appliances:
        return {"empty": True, "message": "No appliances yet. Add appliances to generate a report.",
                "tariff": tariff, "algorithm_runs": dbm.latest_algorithm_runs(conn)}
    summary = ec.summarize(appliances, tariff)
    recs = generate_recommendations(appliances, tariff, config)
    sched = _scheduler_view(appliances, tariff, config)
    opt_start = {}
    if sched["optimized"]:
        opt_start = {e["appliance_id"]: e["start"] for e in sched["optimized"]["entries"]}
    orig_start = {e["appliance_id"]: e["start"] for e in sched["original"]["entries"]}
    for r in summary["rows"]:
        r["original_start"] = fmt_hour(orig_start[r["id"]]) if r["id"] in orig_start else None
        r["optimized_start"] = fmt_hour(opt_start[r["id"]]) if r["id"] in opt_start else None
    runs = dbm.latest_algorithm_runs(conn)
    return ec.round_floats({
        "empty": False, "tariff": tariff, "rows": summary["rows"], "totals": summary["totals"],
        "recommendations": recs["recommendations"], "recommendation_totals": recs["totals"],
        "scheduler": {
            "method": sched["method"], "found": sched["found"], "comparison": sched["comparison"],
            "explanation": sched["explanation"], "fallback": sched["fallback"],
            "moved": sched["moved"],
            "hourly_labels": [fmt_hour(h) for h in range(24)],
            "hourly_original": sched["original"]["hourly_load_kwh"],
            "hourly_optimized": sched["optimized"]["hourly_load_kwh"] if sched["optimized"] else None,
        },
        "algorithm_runs": runs,
        "notes": ["Energy charge = monthly kWh x flat tariff. It is not a complete electricity bill.",
                  "Savings are estimates based on the data and assumptions shown."],
    }, 3)


def _safe(cell):
    """Neutralise spreadsheet formula injection in user-entered text."""
    if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + cell
    return cell


def report_to_csv(report):
    buf = io.StringIO()
    w = csv.writer(buf)
    t = report["tariff"]
    w.writerow(["Smart Electricity Saving Assistant - Energy Report (estimates)"])
    w.writerow(["Tariff (Rs/kWh)", t["base_rate"], "Fixed charge (Rs)", t["fixed_charge"], "Tax %", t["tax_percent"]])
    w.writerow([])
    w.writerow(["Appliance", "Category", "Power (W)", "Quantity", "Hours/day", "Days/month",
                "Active daily kWh", "Standby daily kWh", "Total daily kWh", "Monthly kWh",
                "Energy charge (Rs)", "Share %", "Original start", "Optimized start"])
    for r in report["rows"]:
        w.writerow([_safe(r["name"]), _safe(r["category"]), r["power_w"], r["quantity"], r["hours_per_day"],
                    r["days_per_month"], r["active_daily_kwh"], r["standby_daily_kwh"], r["daily_kwh"],
                    r["monthly_kwh"], r["energy_charge"], r["share_percent"],
                    r.get("original_start"), r.get("optimized_start")])
    tot = report["totals"]
    w.writerow(["TOTAL", "", "", "", "", "", tot["active_daily_kwh"], "", tot["daily_kwh"], tot["monthly_kwh"],
                tot["energy_charge"], 100.0 if tot["monthly_kwh"] else 0.0, "", ""])
    w.writerow(["Estimated bill (energy + fixed + tax)", tot["estimated_bill"]])
    w.writerow([])
    comp = report["scheduler"]["comparison"]
    w.writerow(["Schedule optimization (" + report["scheduler"]["method"] + ")"])
    if comp:
        w.writerow(["Original energy cost (Rs/month)", comp["original_cost"]])
        w.writerow(["Optimized energy cost (Rs/month)", comp["optimized_cost"]])
        w.writerow(["Estimated saving (Rs/month)", comp["cost_saving"]])
    else:
        w.writerow(["No feasible optimized schedule", report["scheduler"]["explanation"]])
    w.writerow([])
    w.writerow(["Rank", "Appliance", "Type", "Issue", "Action", "Daily kWh saved", "Monthly kWh saved",
                "Monthly Rs saved", "Feasibility"])
    for r in report["recommendations"]:
        w.writerow([r["rank"], _safe(r["appliance"]), r["kind"], _safe(r["issue"]), _safe(r["action"]),
                    r["daily_kwh_saved"], r["monthly_kwh_saved"], r["monthly_rs_saved"], r["feasibility"]])
    return buf.getvalue()
