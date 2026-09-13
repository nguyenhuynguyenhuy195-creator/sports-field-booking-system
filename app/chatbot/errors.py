"""Chatbot error types.

Every error message that can reach a user or a log passes through
``scrub_secrets`` first: provider SDKs happily put the API key into a URL in
their exception text, and that text must never reach a response body, a flash
message or a log line.
"""

from __future__ import annotations

from typing import Iterable


SECRET_PLACEHOLDER = "***"
# Anything shorter than this is not treated as a secret: blanking a 3-character
# value out of a message would corrupt ordinary text for no benefit.
MIN_SECRET_LENGTH = 8


class ChatbotError(Exception):
    """Base error for the chatbot subsystem."""


class ChatbotUnavailableError(ChatbotError):
    """The chatbot is disabled or not configured.

    Raised instead of crashing so callers can degrade gracefully. Never
    carries configuration values.
    """


class ChatbotProviderError(ChatbotError):
    """An AI provider call failed (network, quota, bad model id, timeout)."""


class KnowledgeBaseError(ChatbotError):
    """A curated knowledge document is missing or unreadable."""


def scrub_secrets(message: object, secrets: Iterable[str] = ()) -> str:
    """Return ``message`` as text with every known secret replaced."""
    text = str(message)
    for secret in secrets:
        if secret and len(secret) >= MIN_SECRET_LENGTH:
            text = text.replace(secret, SECRET_PLACEHOLDER)
    return text


__all__ = [
    "ChatbotError",
    "ChatbotProviderError",
    "ChatbotUnavailableError",
    "KnowledgeBaseError",
    "SECRET_PLACEHOLDER",
    "scrub_secrets",
]
