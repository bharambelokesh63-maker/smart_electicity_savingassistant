"""Dashboard, calculator and usage-record endpoints."""
from flask import Blueprint

from database import db as dbm
from routes.helpers import fail, json_body, ok
from services import energy_calculator as ec
from services.report_service import build_dashboard
from services.validators import validate_appliance, validate_tariff

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
def dashboard():
    return ok(build_dashboard(dbm.get_db()))


@bp.get("/calculator")
def calculator():
    """Appliance-wise calculation from the saved appliances and tariff."""
    conn = dbm.get_db()
    tariff = dbm.get_tariff(conn)
    return ok(ec.round_floats(ec.summarize(dbm.list_appliances(conn), tariff), 4), tariff=tariff)


@bp.post("/calculate")
def quick_calculate():
    """Stateless what-if calculation for ONE appliance (nothing is saved)."""
    body = json_body()
    probe = {"name": "What-if", "category": "Other", "flexible": False,
             **{k: body.get(k) for k in ("power_w", "quantity", "hours_per_day", "days_per_month", "standby_w")}}
    clean, errors = validate_appliance(probe)
    if errors:
        return fail(f"Invalid input: {next(iter(errors.values()))}", 400, errors)
    tariff_clean, terrors = validate_tariff({"base_rate": body.get("base_rate")})
    if terrors:
        return fail(f"Invalid input: {next(iter(terrors.values()))}", 400, terrors)
    m = ec.appliance_metrics(clean, tariff_clean["base_rate"])
    return ok(ec.round_floats({
        **m, "tariff_rate": tariff_clean["base_rate"],
        "formulas": {
            "daily": "Power(W) x Quantity x Hours per day / 1000",
            "monthly": "Daily kWh x Operating days per month",
            "cost": "Monthly kWh x Tariff (Rs/kWh)",
        },
    }, 4))


@bp.post("/usage-records")
def save_usage_record():
    conn = dbm.get_db()
    appliances = dbm.list_appliances(conn)
    if not appliances:
        return fail("Add at least one appliance before saving a snapshot.", 400)
    s = ec.summarize(appliances, dbm.get_tariff(conn))["totals"]
    rec = {k: s[k] for k in ("appliance_count", "daily_kwh", "monthly_kwh", "energy_charge")}
    rec.update(tariff_rate=s["tariff_rate"], estimated_bill=s["estimated_bill"])
    rec_id = dbm.insert_usage_record(conn, rec)
    return ok({"id": rec_id, **ec.round_floats(rec, 4)}, 201)


@bp.get("/usage-records")
def usage_records():
    return ok(ec.round_floats(dbm.list_usage_records(dbm.get_db()), 4))
