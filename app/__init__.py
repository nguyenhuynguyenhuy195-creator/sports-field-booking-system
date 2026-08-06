import os

from flask import Flask

from config import CONFIG_BY_NAME

from .extensions import csrf, db, login_manager, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)

    selected_config = config_name or os.getenv("APP_ENV", "development")
    config_class = CONFIG_BY_NAME.get(selected_config)
    if config_class is None:
        raise ValueError(f"Unsupported APP_ENV: {selected_config}")

    app.config.from_object(config_class)
    _validate_required_config(app)
    _initialize_extensions(app)
    _register_blueprints(app)

    return app


def _validate_required_config(app: Flask) -> None:
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured in the environment.")


def _initialize_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)


def _register_blueprints(app: Flask) -> None:
    from .routes.health import health_bp

    app.register_blueprint(health_bp)
