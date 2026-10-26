"""Recommendation and schedule-optimization endpoints."""
from flask import Blueprint

from database import db as dbm
from routes.helpers import ApiError, fail, json_body, ok
from services import energy_calculator as ec
from services.recommendation_engine import generate_recommendations
from services.schedule_optimizer import METHODS, optimize_schedule
from services.validators import validate_schedule_config

bp = Blueprint("schedule", __name__, url_prefix="/api")


def require_appliances(conn):
    appliances = dbm.list_appliances(conn)
    if not appliances:
        raise ApiError("No appliances found. Add appliances or load the demonstration data first.", 400)
    return appliances


@bp.post("/recommendations")
def make_recommendations():
    body = json_body(required=False)
    conn = dbm.get_db()
    appliances = require_appliances(conn)
    config = dbm.get_setting(conn, "schedule_config", {}) or {}
    params = {}
    for key in ("high_share_pct", "high_monthly_kwh", "min_saving_rs", "min_standby_kwh",
                "standby_avoidable_pct", "reduce_fraction"):
        if key in body:
            try:
                params[key] = float(body[key])
            except (TypeError, ValueError):
                return fail(f"Invalid input: {key} must be a number.", 400, {key: "must be a number"})
            if params[key] < 0:
                return fail(f"Invalid input: {key} cannot be negative.", 400, {key: "cannot be negative"})
    result = generate_recommendations(appliances, dbm.get_tariff(conn), config, params)
    dbm.replace_recommendations(conn, result["recommendations"])
    return ok(ec.round_floats(result, 4))


@bp.get("/recommendations")
def saved_recommendations():
    return ok(ec.round_floats(dbm.list_recommendations(dbm.get_db()), 4))


@bp.get("/schedule-config")
def get_schedule_config():
    conn = dbm.get_db()
    cfg, _ = validate_schedule_config(dbm.get_setting(conn, "schedule_config", {}) or {})
    return ok(cfg)


@bp.post("/optimize-schedule")
def optimize():
    body = json_body(required=False)
    method = body.get("method", "astar")
    if method not in METHODS:
        return fail(f"Invalid input: method must be one of {', '.join(METHODS)}.", 400, {"method": "invalid"})
    cfg, errors = validate_schedule_config(body)
    if errors:
        return fail(f"Invalid input: {next(iter(errors.values()))}", 400, errors)
    conn = dbm.get_db()
    appliances = require_appliances(conn)
    result = optimize_schedule(appliances, dbm.get_tariff(conn), cfg, method)
    dbm.set_setting(conn, "schedule_config", cfg)
    if result["found"] and result["optimized"]:
        dbm.replace_schedule(
            conn, "optimized",
            [(e["appliance_id"], e["start"], e["duration"]) for e in result["optimized"]["entries"]],
            result["method"],
        )
    dbm.insert_algorithm_run(
        conn, result["method"], result["found"],
        result["optimized"]["objective"] if result["optimized"] else None,
        result["algorithm_result"]["runtime_ms"],
        {"source": "scheduler page", "moved": result["moved"]},
    )
    return ok(ec.round_floats(result, 4))
