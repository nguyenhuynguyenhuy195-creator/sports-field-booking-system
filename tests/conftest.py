import pytest

from app import create_app
from app.extensions import db
from app.services import seed_administrative_catalog, seed_default_sport_catalog


@pytest.fixture()
def app(tmp_path):
    """Create a fresh Flask application configured for isolated tests."""
    application = create_app("testing")
    application.config["MEDIA_ROOT"] = str(tmp_path / "media")

    with application.app_context():
        db.create_all()
        seed_administrative_catalog()
        seed_default_sport_catalog()
        db.session.commit()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()
