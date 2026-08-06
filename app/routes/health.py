from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Report that the Flask process is running."""
    return jsonify(
        {
            "service": "sports-field-booking",
            "status": "ok",
        }
    )


@health_bp.get("/health/ready")
def readiness():
    """Report whether the application can execute a database query."""
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database readiness check failed.")
        return (
            jsonify(
                {
                    "database": "unavailable",
                    "status": "not_ready",
                }
            ),
            503,
        )

    return jsonify(
        {
            "database": "connected",
            "status": "ready",
        }
    )
