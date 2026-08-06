import pytest

from app import create_app


@pytest.fixture()
def app():
    """Create a fresh Flask application configured for isolated tests."""
    return create_app("testing")
