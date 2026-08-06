from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db


def test_application_factory_creates_testing_app():
    app = create_app("testing")

    assert app.name == "app"
    assert app.config["TESTING"] is True


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "service": "sports-field-booking",
        "status": "ok",
    }


def test_readiness_returns_ready_when_database_responds(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.get_json() == {
        "database": "connected",
        "status": "ready",
    }


def test_readiness_hides_database_error_details(client, monkeypatch):
    def raise_database_error(*args, **kwargs):
        raise SQLAlchemyError("sensitive connection details")

    monkeypatch.setattr(db.session, "execute", raise_database_error)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "database": "unavailable",
        "status": "not_ready",
    }
    assert b"sensitive connection details" not in response.data
