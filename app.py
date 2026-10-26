
"""Smart Electricity Saving Assistant - Flask application factory.

Run: python app.py
"""

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from config import Config
from database import db as dbm
from routes import (
    algorithm_routes,
    appliance_routes,
    dashboard_routes,
    page_routes,
    report_routes,
    schedule_routes,
)
from routes.helpers import ApiError

log = logging.getLogger("sea")


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    dbm.init_app(app)

    for module in (
        page_routes,
        appliance_routes,
        dashboard_routes,
        schedule_routes,
        algorithm_routes,
        report_routes,
    ):
        app.register_blueprint(module.bp)

    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return (
            jsonify({
                "success": False,
                "error": err.message,
                **({"details": err.details} if err.details else {}),
            }),
            err.status,
        )

    @app.errorhandler(404)
    def not_found(_e):
        if wants_json():
            return jsonify({
                "success": False,
                "error": "Endpoint not found.",
            }), 404
        return "Page not found", 404

    @app.errorhandler(405)
    def bad_method(_e):
        return jsonify({
            "success": False,
            "error": "Method not allowed for this endpoint.",
        }), 405

    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc, HTTPException):
            if wants_json():
                return jsonify({
                    "success": False,
                    "error": exc.description or exc.name,
                }), exc.code
            return exc

        log.exception("Unhandled error: %s", exc)

        if wants_json():
            return jsonify({
                "success": False,
                "error": (
                    "Something went wrong on the server. "
                    "Please try again."
                ),
            }), 500

        return "Internal server error", 500

    return app


if __name__ == "__main__":
    create_app().run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
