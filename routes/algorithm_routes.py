"""Endpoints for the AI Algorithm Laboratory.

Route handlers only parse input, load data and call the independent algorithm
functions in ``ai/``; no AI logic lives here.
"""
from flask import Blueprint

from ai.a_star import a_star_search
from ai.bayesian_network import run_bayesian_network
from ai.best_first import best_first_search
from ai.csp_scheduler import csp_backtracking
from ai.forward_chaining import DEFAULT_PARAMS, run_forward_chaining
from ai.hill_climbing import hill_climbing
from ai.scheduling_problem import SchedulingProblem
from database import db as dbm
from routes.helpers import fail, json_body, ok
from routes.schedule_routes import require_appliances
from services import energy_calculator as ec
from services.validators import validate_schedule_config

bp = Blueprint("algorithms", __name__, url_prefix="/api/algorithms")


def _record(conn, result):
    summary = {k: result.get(k) for k in ("stats", "explanation") if k in result}
    summary["moved"] = result.get("moved", [])
    objective = result.get("objective")
    dbm.insert_algorithm_run(conn, result["algorithm"], result["found"], objective,
                             result.get("runtime_ms", 0.0), summary)


def _scheduling_run(fn):
    body = json_body(required=False)
    cfg, errors = validate_schedule_config(body)
    if errors:
        return fail(f"Invalid input: {next(iter(errors.values()))}", 400, errors)
    conn = dbm.get_db()
    appliances = require_appliances(conn)
    problem = SchedulingProblem(appliances, dbm.get_tariff(conn), cfg)
    result = fn(problem, cfg)
    _record(conn, result)
    return ok(ec.round_floats(result, 4))


@bp.post("/best-first")
def best_first():
    return _scheduling_run(lambda p, c: best_first_search(p, c["max_expansions"]))


@bp.post("/a-star")
def a_star():
    return _scheduling_run(lambda p, c: a_star_search(p, c["max_expansions"]))


@bp.post("/hill-climbing")
def hill():
    return _scheduling_run(lambda p, c: hill_climbing(p, c["max_iterations"]))


@bp.post("/csp")
def csp():
    return _scheduling_run(lambda p, c: csp_backtracking(p, value_order=c["value_order"]))


@bp.post("/forward-chaining")
def forward():
    body = json_body(required=False)
    cfg, errors = validate_schedule_config(body)
    if errors:
        return fail(f"Invalid input: {next(iter(errors.values()))}", 400, errors)
    params = {}
    for key in DEFAULT_PARAMS:
        if key in body:
            try:
                params[key] = float(body[key])
            except (TypeError, ValueError):
                return fail(f"Invalid input: {key} must be a number.", 400, {key: "must be a number"})
            if params[key] < 0:
                return fail(f"Invalid input: {key} cannot be negative.", 400, {key: "cannot be negative"})
    conn = dbm.get_db()
    appliances = require_appliances(conn)
    result = run_forward_chaining(appliances, dbm.get_tariff(conn), cfg, params)
    _record(conn, result)
    return ok(ec.round_floats(result, 4))


@bp.post("/bayesian-network")
def bayes():
    body = json_body(required=False)
    overrides = {k: body[k] for k in ("UsageIntensity", "HighPowerCount", "StandbyLevel") if k in body}
    conn = dbm.get_db()
    appliances = require_appliances(conn)
    try:
        result = run_bayesian_network(appliances, overrides)
    except ValueError as exc:
        return fail(f"Invalid input: {exc}", 400)
    _record(conn, result)
    return ok(ec.round_floats(result, 4))
