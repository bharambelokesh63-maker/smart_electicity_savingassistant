"""Appliance CRUD, presets, tariff and demonstration-data endpoints."""
from flask import Blueprint

from database import db as dbm
from routes.helpers import ApiError, fail, json_body, ok
from services import appliance_service as svc
from services import energy_calculator as ec
from services.validators import CATEGORIES, validate_appliance, validate_tariff

bp = Blueprint("appliances", __name__, url_prefix="/api")


def _validation_error(errors):
    first = next(iter(errors.values()))
    return fail(f"Invalid input: {first}", 400, errors)


@bp.get("/appliances")
def list_appliances():
    conn = dbm.get_db()
    tariff = dbm.get_tariff(conn)
    items = svc.with_metrics(dbm.list_appliances(conn), tariff)
    return ok(ec.round_floats(items, 4), count=len(items))


@bp.get("/appliances/<int:appliance_id>")
def get_appliance(appliance_id):
    conn = dbm.get_db()
    item = dbm.get_appliance(conn, appliance_id)
    if not item:
        return fail("Appliance not found.", 404)
    return ok(item)


@bp.post("/appliances")
def create_appliance():
    clean, errors = validate_appliance(json_body())
    if errors:
        return _validation_error(errors)
    conn = dbm.get_db()
    new_id = dbm.insert_appliance(conn, clean)
    return ok(dbm.get_appliance(conn, new_id), 201)


@bp.put("/appliances/<int:appliance_id>")
def update_appliance(appliance_id):
    conn = dbm.get_db()
    existing = dbm.get_appliance(conn, appliance_id)
    if not existing:
        return fail("Appliance not found.", 404)
    clean, errors = validate_appliance(json_body())
    if errors:
        return _validation_error(errors)
    dbm.update_appliance(conn, appliance_id, clean)
    return ok(dbm.get_appliance(conn, appliance_id))


@bp.delete("/appliances/<int:appliance_id>")
def delete_appliance(appliance_id):
    conn = dbm.get_db()
    if not dbm.delete_appliance(conn, appliance_id):
        return fail("Appliance not found.", 404)
    return ok({"deleted": appliance_id})


@bp.get("/appliance-templates")
def templates():
    return ok(svc.APPLIANCE_TEMPLATES, categories=CATEGORIES)


# ------------------------------------------------------------------ tariff --
@bp.get("/tariff")
def get_tariff():
    return ok(dbm.get_tariff(dbm.get_db()))


@bp.put("/tariff")
def put_tariff():
    clean, errors = validate_tariff(json_body())
    if errors:
        return _validation_error(errors)
    conn = dbm.get_db()
    dbm.save_tariff(conn, clean)
    return ok(dbm.get_tariff(conn))


# ------------------------------------------------------------ demonstration --
@bp.post("/sample-data/load")
def load_sample():
    conn = dbm.get_db()
    inserted = svc.load_sample_data(conn)
    if inserted == 0:
        return fail("Demonstration data is already loaded.", 409)
    return ok({"inserted": inserted, "label": "Demonstration data - replace with your own appliances."}, 201)


@bp.post("/sample-data/reset")
def reset_sample():
    body = json_body(required=False)
    if body.get("confirm") is not True:
        raise ApiError("Confirmation required: send {\"confirm\": true} to delete demonstration data.", 400)
    conn = dbm.get_db()
    removed = dbm.delete_demo_appliances(conn)
    return ok({"removed": removed})
