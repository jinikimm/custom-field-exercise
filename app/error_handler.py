from flask import g, jsonify
from werkzeug.exceptions import BadRequest


class Error(Exception):
    def __init__(self, status_code, code, message, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details if details is not None else []


class ValidationError(Error):
    def __init__(self, details=None, message="Invalid request"):
        super().__init__(400, "bad_request", message, details)


class NotFoundError(Error):
    def __init__(self, details=None, message="Resource not found"):
        super().__init__(404, "not_found", message, details)


class ConflictError(Error):
    def __init__(self, details=None, message="Conflict"):
        super().__init__(409, "conflict", message, details)


def error_handlers(app):
    def _request_id():
        return getattr(g, "request_id", None)

    @app.errorhandler(Error)
    def app_error(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": e.details,
                    },
                }
            ),
            e.status_code,
        )

    @app.errorhandler(BadRequest)
    def bad_request(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid request",
                        "details": [
                            {
                                "field": "body",
                                "message": "Malformed JSON",
                            }
                        ],
                    },
                }
            ),
            400,
        )

    @app.errorhandler(500)
    def internal_error(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred.",
                        "details": [],
                    },
                }
            ),
            500,
        )
