"""Offline provider doubles for the chatbot tests.

Kept in its own module (not in conftest.py) so that importing the chatbot's
RAG dependencies happens only in the chatbot tests. The rest of the suite must
keep running on a checkout where those packages are not installed.

``LexicalEmbeddingProvider`` is deliberately more than a stub: it hashes the
same content tokens the evidence gate uses into a fixed-size vector, so cosine
similarity over it behaves like real lexical similarity. That lets the
retrieval tests exercise the genuine knowledge base and the genuine vector
store -- a relevant question really does score high and an unrelated one really
does score near zero -- without calling a live embedding API.
"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

from app.chatbot.errors import ChatbotProviderError
from app.chatbot.providers.base import ChatModelProvider, EmbeddingProvider
from app.chatbot.retrieval import content_tokens


EMBEDDING_DIMENSIONS = 256


class LexicalEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-words embeddings; no network, no API key."""

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions
        self.embed_document_calls = 0
        self.embed_query_calls = 0

    @property
    def model_name(self) -> str:
        return "fake-lexical-embedding"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_document_calls += 1
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls += 1
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in content_tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class FailingEmbeddingProvider(EmbeddingProvider):
    """Stands in for an embedding API that is down or rejecting the key."""

    def __init__(self, message: str = "embedding backend unavailable") -> None:
        self.message = message

    @property
    def model_name(self) -> str:
        return "failing-embedding"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise ChatbotProviderError(self.message)

    def embed_query(self, text: str) -> list[float]:
        raise ChatbotProviderError(self.message)


class QueryFailingEmbeddingProvider(LexicalEmbeddingProvider):
    """Indexes normally, then fails on queries.

    The realistic mid-session outage: the index was built while the API was
    healthy, and the quota runs out (or the key is revoked) later.
    """

    @property
    def model_name(self) -> str:
        return "query-failing-embedding"

    def embed_query(self, text: str) -> list[float]:
        raise ChatbotProviderError("embedding quota exhausted")


class ExplodingEmbeddingProvider(EmbeddingProvider):
    """Raises a non-chatbot exception, as a third-party SDK would."""

    def __init__(self, message: str = "boom") -> None:
        self.message = message

    @property
    def model_name(self) -> str:
        return "exploding-embedding"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError(self.message)

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError(self.message)


class FailingChatModelProvider(ChatModelProvider):
    """Chat model that is down, rate-limited or timing out.

    ``error`` lets a test pick the failure shape: a ChatbotProviderError (what
    the Gemini provider raises after wrapping an SDK error) or a raw exception
    such as TimeoutError, to prove nothing leaks out unwrapped.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or ChatbotProviderError(
            "Không nhận được phản hồi từ nhà cung cấp AI. (ClientError: 429)"
        )
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "failing-chat-model"

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        raise self.error


class RecordingChatModelProvider(ChatModelProvider):
    """Captures the exact prompts a caller would send to the LLM."""

    def __init__(self, answer: str = "Câu trả lời thử nghiệm.") -> None:
        self.answer = answer
        self.calls: list[dict[str, str]] = []

    @property
    def model_name(self) -> str:
        return "fake-chat-model"

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt}
        )
        return self.answer


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "ExplodingEmbeddingProvider",
    "FailingChatModelProvider",
    "FailingEmbeddingProvider",
    "QueryFailingEmbeddingProvider",
    "LexicalEmbeddingProvider",
    "RecordingChatModelProvider",
]
