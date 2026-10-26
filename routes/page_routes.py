"""HTML pages (all data is loaded by JavaScript through the REST API)."""
from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

PAGES = [
    ("/", "dashboard", "dashboard.html"),
    ("/appliances", "appliances", "appliances.html"),
    ("/calculator", "calculator", "calculator.html"),
    ("/recommendations", "recommendations", "recommendations.html"),
    ("/scheduler", "scheduler", "scheduler.html"),
    ("/algorithms", "algorithms", "algorithm_lab.html"),
    ("/reports", "reports", "reports.html"),
]


def _make(template, active):
    def view():
        return render_template(template, active=active)
    view.__name__ = f"page_{active}"
    return view


for path, active, template in PAGES:
    bp.add_url_rule(path, view_func=_make(template, active))
