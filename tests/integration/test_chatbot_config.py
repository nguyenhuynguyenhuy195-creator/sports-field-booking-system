"""Phase 1 chatbot: configuration and application startup.

The requirement these tests protect is blunt: the booking system must start and
serve normally whether or not the chatbot is enabled, configured or reachable.
A missing GEMINI_API_KEY is a chatbot-unavailable condition, never a Flask
startup failure.
"""

from __future__ import annotations

import pytest

from app import create_app
from app.chatbot import ChatbotSettings
from app.chatbot.errors import ChatbotUnavailableError
from app.chatbot.providers import build_embedding_provider
from app.chatbot.retrieval import (
    APP_EXTENSION_KEY,
    get_knowledge_index,
    reset_knowledge_index,
)
from app.chatbot.settings import DEFAULTS
from config import TestingConfig

from chatbot_doubles import (
    ExplodingEmbeddingProvider,
    FailingEmbeddingProvider,
    LexicalEmbeddingProvider,
)


FAKE_KEY = "integration-gemini-key-0123456789"


# --- startup -----------------------------------------------------------------


def test_app_exposes_every_chatbot_setting():
    application = create_app("testing")

    for name in (
        "CHATBOT_ENABLED",
        "GEMINI_API_KEY",
        "CHATBOT_MODEL",
        "CHATBOT_EMBEDDING_MODEL",
        "CHATBOT_EMBEDDING_DIMENSIONS",
        "CHATBOT_RETRIEVAL_TOP_K",
        "CHATBOT_MIN_RELEVANCE_SCORE",
        "CHATBOT_STRONG_RELEVANCE_SCORE",
        "CHATBOT_MAX_SOURCES",
    ):
        assert name in application.config, name


def test_app_starts_when_the_chatbot_is_enabled_without_a_key(monkeypatch):
    """Startup must not validate the chatbot the way it validates MoMo.

    Asserted on the config class, because BaseConfig reads the environment at
    import time -- so this holds no matter what the developer's .env contains.
    """
    monkeypatch.setattr(TestingConfig, "CHATBOT_ENABLED", True, raising=False)
    monkeypatch.setattr(TestingConfig, "GEMINI_API_KEY", "", raising=False)

    application = create_app("testing")

    settings = ChatbotSettings.from_app(application)
    assert settings.enabled is True
    assert settings.is_configured is False
    assert "GEMINI_API_KEY" in settings.unavailable_reason


def test_app_starts_when_chatbot_is_disabled(app):
    app.config["CHATBOT_ENABLED"] = False

    assert ChatbotSettings.from_app(app).is_configured is False


def test_app_starts_when_the_api_key_is_missing(app):
    """Enabled but keyless is a degraded chatbot, not a broken application."""
    app.config["CHATBOT_ENABLED"] = True
    app.config["GEMINI_API_KEY"] = ""

    settings = ChatbotSettings.from_app(app)

    assert settings.is_configured is False
    assert "GEMINI_API_KEY" in settings.unavailable_reason


def test_existing_pages_still_serve_with_the_chatbot_unconfigured(app):
    app.config["CHATBOT_ENABLED"] = True
    app.config["GEMINI_API_KEY"] = ""
    client = app.test_client()

    assert client.get("/").status_code in (200, 302)
    assert client.get("/venues").status_code == 200
    assert client.get("/health").status_code == 200


def test_no_chatbot_route_is_registered_in_phase_one(app):
    """Phase 1 is the service layer only; the endpoint arrives in Phase 2."""
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert not any(rule.startswith("/chatbot") for rule in rules)


# --- configuration defaults --------------------------------------------------


def test_shipped_defaults_are_safe():
    """Asserted on the dataclass defaults, not on app config: a developer's
    own .env must not be able to make this pass or fail."""
    settings = ChatbotSettings()

    assert settings.enabled is False
    assert settings.api_key == ""
    assert settings.is_configured is False
    assert DEFAULTS["CHATBOT_ENABLED"] is False
    assert settings.chat_model == "gemini-3.5-flash-lite"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_dimensions == 768
    assert settings.retrieval_top_k == 4
    assert settings.max_sources == 3
    assert 0 < settings.min_relevance_score <= settings.strong_relevance_score <= 1


def test_settings_read_overrides_from_config(app):
    app.config["CHATBOT_ENABLED"] = True
    app.config["GEMINI_API_KEY"] = FAKE_KEY
    app.config["CHATBOT_MODEL"] = "gemini-2.5-flash"
    app.config["CHATBOT_RETRIEVAL_TOP_K"] = 6

    settings = ChatbotSettings.from_app(app)

    assert settings.is_configured is True
    assert settings.chat_model == "gemini-2.5-flash"
    assert settings.retrieval_top_k == 6


def test_settings_fall_back_when_a_value_is_none(app):
    app.config["CHATBOT_RETRIEVAL_TOP_K"] = None

    assert ChatbotSettings.from_app(app).retrieval_top_k == 4


def test_index_fingerprint_tracks_the_embedding_model():
    base = ChatbotSettings(enabled=True, api_key=FAKE_KEY)
    other_model = ChatbotSettings(
        enabled=True, api_key=FAKE_KEY, embedding_model="other-model"
    )
    other_dimensions = ChatbotSettings(
        enabled=True, api_key=FAKE_KEY, embedding_dimensions=1536
    )

    assert base.index_fingerprint != other_model.index_fingerprint
    assert base.index_fingerprint != other_dimensions.index_fingerprint


def test_unconfigured_provider_construction_is_refused(app):
    app.config["CHATBOT_ENABLED"] = True
    app.config["GEMINI_API_KEY"] = ""

    with pytest.raises(ChatbotUnavailableError):
        build_embedding_provider(ChatbotSettings.from_app(app))


# --- index lifecycle on the app ----------------------------------------------


def test_index_is_built_once_and_reused(app):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)
    provider = LexicalEmbeddingProvider()

    first = get_knowledge_index(app, embedding_provider=provider, settings=settings)
    second = get_knowledge_index(app, embedding_provider=provider, settings=settings)

    assert first is not None
    assert second is first
    assert provider.embed_document_calls == 1


def test_index_is_rebuilt_when_the_embedding_model_changes(app):
    provider = LexicalEmbeddingProvider()
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)
    first = get_knowledge_index(app, embedding_provider=provider, settings=settings)

    changed = ChatbotSettings(
        enabled=True, api_key=FAKE_KEY, embedding_model="another-model"
    )
    second = get_knowledge_index(app, embedding_provider=provider, settings=changed)

    assert second is not None
    assert second is not first
    assert provider.embed_document_calls == 2


def test_reset_clears_the_cached_index(app):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)
    provider = LexicalEmbeddingProvider()

    get_knowledge_index(app, embedding_provider=provider, settings=settings)
    reset_knowledge_index(app)
    get_knowledge_index(app, embedding_provider=provider, settings=settings)

    assert provider.embed_document_calls == 2


def test_provider_failure_yields_no_index_instead_of_raising(app):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)

    index = get_knowledge_index(
        app, embedding_provider=FailingEmbeddingProvider(), settings=settings
    )

    assert index is None
    assert app.extensions[APP_EXTENSION_KEY]["index"] is None


def test_unexpected_provider_error_also_yields_no_index(app):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)

    index = get_knowledge_index(
        app, embedding_provider=ExplodingEmbeddingProvider(), settings=settings
    )

    assert index is None


def test_a_failed_build_does_not_poison_a_later_good_one(app):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)

    assert (
        get_knowledge_index(
            app, embedding_provider=FailingEmbeddingProvider(), settings=settings
        )
        is None
    )
    recovered = get_knowledge_index(
        app, embedding_provider=LexicalEmbeddingProvider(), settings=settings
    )

    assert recovered is not None
    assert recovered.chunk_count > 0


def test_index_failure_never_leaks_the_api_key(app, caplog):
    settings = ChatbotSettings(enabled=True, api_key=FAKE_KEY)

    with caplog.at_level("WARNING"):
        get_knowledge_index(
            app,
            embedding_provider=FailingEmbeddingProvider(FAKE_KEY),
            settings=settings,
        )

    assert FAKE_KEY not in caplog.text
