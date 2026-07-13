from flask import Flask
from flask_migrate import Migrate
from sqlalchemy import text


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        app.config.from_object("app.config.Config")
    else:
        app.config.update(test_config)

    from .models import db
    db.init_app(app)
    Migrate(app, db)

    from .logger import init_logger
    init_logger(app)

    from .error_handler import error_handlers
    error_handlers(app)

    from .apis import register_api
    register_api(app)

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception:
            return {"status": "error"}, 500

    return app
