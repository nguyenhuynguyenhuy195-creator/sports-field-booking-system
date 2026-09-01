import os

from flask import Flask, render_template

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
    app.config["APP_ENV_NAME"] = selected_config
    if not app.config.get("MEDIA_ROOT"):
        app.config["MEDIA_ROOT"] = os.path.join(app.instance_path, "media")
    _validate_required_config(app)
    _initialize_extensions(app)
    _register_blueprints(app)
    _register_commands(app)
    _register_template_filters(app)
    _register_error_handlers(app)
    _register_response_headers(app)

    return app


def _validate_required_config(app: Flask) -> None:
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured in the environment.")
    if app.config.get("MOMO_ENABLED"):
        required = (
            "MOMO_PARTNER_CODE",
            "MOMO_ACCESS_KEY",
            "MOMO_SECRET_KEY",
            "MOMO_REDIRECT_URL",
            "MOMO_IPN_URL",
        )
        missing = [name for name in required if not app.config.get(name)]
        if missing:
            raise RuntimeError(
                "MoMo Sandbox is enabled but configuration is missing: "
                + ", ".join(missing)
            )


def _initialize_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    _configure_login_manager()
    login_manager.init_app(app)
    csrf.init_app(app)


def _configure_login_manager() -> None:
    from .models import User

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        if not user_id.isdigit():
            return None
        user = db.session.get(User, int(user_id))
        return user if user is not None and user.is_active else None


def _register_blueprints(app: Flask) -> None:
    from .routes.admin import admin_bp
    from .routes.auth import auth_bp
    from .routes.bookings import bookings_bp
    from .routes.fields import fields_bp
    from .routes.health import health_bp
    from .routes.main import main_bp
    from .routes.maintenance import maintenance_bp
    from .routes.matches import matches_bp
    from .routes.media import media_bp
    from .routes.owner_applications import owner_applications_bp
    from .routes.owner import owner_bp
    from .routes.payments import payments_bp
    from .routes.pricing import pricing_bp
    from .routes.venues import venues_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(fields_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(pricing_bp)
    app.register_blueprint(owner_applications_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(health_bp)


def _register_commands(app: Flask) -> None:
    from .cli import register_commands

    register_commands(app)


def _register_template_filters(app: Flask) -> None:
    from .template_filters import register_template_filters

    register_template_filters(app)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404


def _register_response_headers(app: Flask) -> None:
    @app.after_request
    def add_vietnamese_html_headers(response):
        if response.mimetype == "text/html":
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers["Content-Language"] = "vi"
        return response
