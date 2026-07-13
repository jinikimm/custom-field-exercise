import json
import time
from uuid import uuid4
import logging

from flask import g, request


def init_logger(app):
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def set_request_id():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        g.request_started_at = time.time()

    @app.after_request
    def log_and_attach_request_id(response):
        duration_ms = int((time.time() - g.request_started_at) * 1000)

        app.logger.info(
            json.dumps(
                {
                    "request_id": g.request_id,
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )

        response.headers["X-Request-ID"] = g.request_id
        return response
