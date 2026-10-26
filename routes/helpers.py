"""Shared helpers for JSON responses and request parsing."""
from flask import jsonify, request


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message, self.status, self.details = message, status, details


def ok(data=None, status=200, **extra):
    body = {"success": True, "data": data}
    body.update(extra)
    return jsonify(body), status


def fail(message, status=400, details=None):
    body = {"success": False, "error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def json_body(required=True):
    """Parse a JSON object body.  Optional bodies may be empty."""
    raw = request.get_data(cache=True)
    if not raw or not raw.strip():
        if required:
            raise ApiError("Request body must be a JSON object.")
        return {}
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be valid JSON containing an object.")
    return data
