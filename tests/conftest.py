import pytest

from app import create_app
from app.extensions import db
from app.services import seed_default_sport_catalog


@pytest.fixture()
def app():
    """Create a fresh Flask application configured for isolated tests."""
    application = create_app("testing")

    with application.app_context():
        db.create_all()
        seed_default_sport_catalog()
        db.session.commit()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()
