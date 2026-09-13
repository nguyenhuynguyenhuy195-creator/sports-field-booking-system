"""Provider interfaces and the factory that builds the configured pair."""

from __future__ import annotations

from ..settings import ChatbotSettings
from .base import ChatModelProvider, EmbeddingProvider, LangChainEmbeddingAdapter
from .gemini import GeminiChatModelProvider, GeminiEmbeddingProvider


def build_embedding_provider(settings: ChatbotSettings) -> EmbeddingProvider:
    """Raises ChatbotUnavailableError when the chatbot is off or unconfigured."""
    settings.require_configured()
    return GeminiEmbeddingProvider(settings)


def build_chat_model_provider(settings: ChatbotSettings) -> ChatModelProvider:
    """Raises ChatbotUnavailableError when the chatbot is off or unconfigured."""
    settings.require_configured()
    return GeminiChatModelProvider(settings)


__all__ = [
    "ChatModelProvider",
    "EmbeddingProvider",
    "GeminiChatModelProvider",
    "GeminiEmbeddingProvider",
    "LangChainEmbeddingAdapter",
    "build_chat_model_provider",
    "build_embedding_provider",
]
