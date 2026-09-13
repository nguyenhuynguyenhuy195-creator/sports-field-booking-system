"""Chatbot settings resolved from Flask config.

Reading config happens here and nowhere else, so the rest of the package never
touches ``current_app.config`` (and never has to guess a default). The API key
lives on this object but is deliberately kept out of ``__repr__``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ChatbotUnavailableError


DEFAULTS: dict[str, object] = {
    "CHATBOT_ENABLED": False,
    "GEMINI_API_KEY": "",
    "CHATBOT_MODEL": "gemini-3.5-flash-lite",
    "CHATBOT_THINKING_LEVEL": "low",
    "CHATBOT_EMBEDDING_MODEL": "gemini-embedding-001",
    "CHATBOT_EMBEDDING_DIMENSIONS": 768,
    "CHATBOT_CHUNK_SIZE": 1000,
    "CHATBOT_CHUNK_OVERLAP": 120,
    "CHATBOT_RETRIEVAL_TOP_K": 4,
    "CHATBOT_MIN_RELEVANCE_SCORE": 0.70,
    "CHATBOT_STRONG_RELEVANCE_SCORE": 0.78,
    "CHATBOT_MAX_SOURCES": 3,
    "CHATBOT_TIMEOUT_SECONDS": 20.0,
}


@dataclass(frozen=True)
class ChatbotSettings:
    """Everything the chatbot needs to run, already validated."""

    enabled: bool = False
    api_key: str = field(default="", repr=False)
    chat_model: str = "gemini-3.5-flash-lite"
    thinking_level: str = "low"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    chunk_size: int = 1000
    chunk_overlap: int = 120
    retrieval_top_k: int = 4
    min_relevance_score: float = 0.70
    strong_relevance_score: float = 0.78
    max_sources: int = 3
    timeout_seconds: float = 20.0

    @property
    def is_configured(self) -> bool:
        """Enabled *and* holding an API key — the only runnable state."""
        return bool(self.enabled and self.api_key)

    @property
    def unavailable_reason(self) -> str | None:
        """Why the chatbot cannot run, as operator-facing text.

        Never contains a configuration value, only the name of what is missing.
        """
        if not self.enabled:
            return "Trợ lý ảo đang được tắt trong cấu hình (CHATBOT_ENABLED)."
        if not self.api_key:
            return "Thiếu khóa API của nhà cung cấp AI (GEMINI_API_KEY)."
        return None

    def require_configured(self) -> None:
        reason = self.unavailable_reason
        if reason is not None:
            raise ChatbotUnavailableError(reason)

    @property
    def index_fingerprint(self) -> str:
        """Identity of an index built with these settings.

        Changing the embedding model or its dimensions invalidates a cached
        index even when the documents themselves are untouched.
        """
        return f"{self.embedding_model}:{self.embedding_dimensions}"

    @classmethod
    def from_mapping(cls, config) -> "ChatbotSettings":
        def value(name: str):
            raw = config.get(name, DEFAULTS[name])
            return DEFAULTS[name] if raw is None else raw

        return cls(
            enabled=bool(value("CHATBOT_ENABLED")),
            api_key=str(value("GEMINI_API_KEY") or "").strip(),
            chat_model=str(value("CHATBOT_MODEL")),
            thinking_level=str(value("CHATBOT_THINKING_LEVEL") or ""),
            embedding_model=str(value("CHATBOT_EMBEDDING_MODEL")),
            embedding_dimensions=int(value("CHATBOT_EMBEDDING_DIMENSIONS")),
            chunk_size=int(value("CHATBOT_CHUNK_SIZE")),
            chunk_overlap=int(value("CHATBOT_CHUNK_OVERLAP")),
            retrieval_top_k=int(value("CHATBOT_RETRIEVAL_TOP_K")),
            min_relevance_score=float(value("CHATBOT_MIN_RELEVANCE_SCORE")),
            strong_relevance_score=float(value("CHATBOT_STRONG_RELEVANCE_SCORE")),
            max_sources=int(value("CHATBOT_MAX_SOURCES")),
            timeout_seconds=float(value("CHATBOT_TIMEOUT_SECONDS")),
        )

    @classmethod
    def from_app(cls, app=None) -> "ChatbotSettings":
        """Resolve from ``app`` or, when omitted, the current Flask app."""
        if app is None:
            from flask import current_app

            app = current_app
        return cls.from_mapping(app.config)


__all__ = ["ChatbotSettings", "DEFAULTS"]
