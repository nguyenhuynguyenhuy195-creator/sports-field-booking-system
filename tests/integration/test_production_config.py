import pytest

from app import create_app
from config import DevelopmentConfig, ProductionConfig, TestingConfig


VALID_TEST_SECRET = "production-config-regression-secret-0123456789"


def _production_app(monkeypatch, secret_key=VALID_TEST_SECRET):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", secret_key)
    return create_app("production")


def test_production_profile_uses_safe_runtime_and_cookie_settings(monkeypatch):
    app = _production_app(monkeypatch)

    assert app.debug is False
    assert app.testing is False
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"


@pytest.mark.parametrize(
    "secret_key",
    [
        None,
        "",
        "   ",
        "change-me",
        "dev-secret-change-me",
        "demo-secret-key",
        "replace-with-a-random-secret",
        "YOUR_SECRET_KEY",
    ],
)
def test_production_rejects_missing_empty_and_placeholder_secrets(
    monkeypatch, secret_key
):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", secret_key)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_accepts_valid_secret_and_environment_selection(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", VALID_TEST_SECRET)
    monkeypatch.setenv("APP_ENV", "production")

    app = create_app()

    assert app.config["APP_ENV_NAME"] == "production"


def test_development_and_testing_profiles_still_initialize(monkeypatch):
    monkeypatch.setattr(DevelopmentConfig, "SECRET_KEY", "development-test-secret")
    monkeypatch.setattr(TestingConfig, "SECRET_KEY", "testing-test-secret")

    development = create_app("development")
    testing = create_app("testing")

    assert development.debug is True
    assert development.testing is False
    assert testing.testing is True


def test_production_keeps_vnpay_and_chatbot_configuration(monkeypatch):
    expected_vnpay = ProductionConfig.VNPAY_ENABLED
    expected_chatbot = ProductionConfig.CHATBOT_ENABLED

    app = _production_app(monkeypatch)

    assert app.config["VNPAY_ENABLED"] is expected_vnpay
    assert app.config["CHATBOT_ENABLED"] is expected_chatbot
