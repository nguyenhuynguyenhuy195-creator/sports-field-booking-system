"""Provider abstractions.

Nothing outside ``app/chatbot/providers/`` may import a vendor SDK. Retrieval,
chunking and (later) the query service all depend on these two interfaces, so
swapping Gemini for another vendor is a change in this package only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from langchain_core.embeddings import Embeddings


class EmbeddingProvider(ABC):
    """Turns text into vectors for the knowledge index."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the embedding model, for cache keys and reporting."""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed stored knowledge chunks (indexing side)."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a user question (search side)."""


class ChatModelProvider(ABC):
    """Generates an answer from a system prompt plus grounded context."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the chat model, for reporting."""

    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the model's plain-text answer."""


class LangChainEmbeddingAdapter(Embeddings):
    """Exposes an :class:`EmbeddingProvider` through LangChain's interface.

    LangChain's vector store insists on its own ``Embeddings`` protocol. Rather
    than let that protocol leak into our services, it is adapted at this single
    boundary — which is also what lets tests drive the whole retrieval stack
    with a plain fake provider and no SDK.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._provider.embed_query(text)


__all__ = [
    "ChatModelProvider",
    "EmbeddingProvider",
    "LangChainEmbeddingAdapter",
]
