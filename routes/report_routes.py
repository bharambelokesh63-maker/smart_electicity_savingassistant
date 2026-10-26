"""Energy report endpoints (JSON and CSV download)."""
from flask import Blueprint, Response

from database import db as dbm
from routes.helpers import fail, ok
from services.report_service import build_report, report_to_csv

bp = Blueprint("reports", __name__, url_prefix="/api")


@bp.get("/energy-report")
def energy_report():
    return ok(build_report(dbm.get_db()))


@bp.get("/energy-report/csv")
def energy_report_csv():
    report = build_report(dbm.get_db())
    if report.get("empty"):
        return fail("No appliances to report. Add appliances first.", 400)
    return Response(
        report_to_csv(report), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=energy_report.csv"},
    )
