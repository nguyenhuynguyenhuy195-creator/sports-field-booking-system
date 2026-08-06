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
    from .routes.auth import auth_bp
    from .routes.health import health_bp
    from .routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
