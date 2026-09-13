"""Gemini implementations of the provider interfaces.

The ``google.genai`` SDK is imported lazily inside ``_client()`` so that merely
importing this module — which ``app.chatbot`` does — can never break Flask
startup on a machine where the SDK is missing or broken.

Every SDK exception is re-raised as :class:`ChatbotProviderError` with the API
key scrubbed out: google-genai puts the request URL (which can carry the key)
into its error text.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..errors import ChatbotProviderError, scrub_secrets
from ..settings import ChatbotSettings
from .base import ChatModelProvider, EmbeddingProvider


# Keeps one embed_content call well inside the provider's per-request limits.
EMBED_BATCH_SIZE = 32

# Indexing and querying must use the matching task types, or gemini-embedding-001
# places the two in different regions of the space and similarity collapses.
DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


class _GeminiClientMixin:
    """Shared lazy client construction and error scrubbing."""

    def __init__(self, settings: ChatbotSettings) -> None:
        settings.require_configured()
        self._settings = settings
        self._cached_client = None

    def _client(self):
        if self._cached_client is None:
            try:
                from google import genai
                from google.genai import types

                self._cached_client = genai.Client(
                    api_key=self._settings.api_key,
                    http_options=types.HttpOptions(
                        timeout=int(self._settings.timeout_seconds * 1000)
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - SDK raises many types
                raise self._provider_error(
                    "Không khởi tạo được kết nối tới nhà cung cấp AI.", exc
                ) from exc
        return self._cached_client

    def _provider_error(self, message: str, exc: object) -> ChatbotProviderError:
        detail = scrub_secrets(exc, (self._settings.api_key,))
        return ChatbotProviderError(f"{message} ({type(exc).__name__}: {detail})")


class GeminiEmbeddingProvider(_GeminiClientMixin, EmbeddingProvider):
    """gemini-embedding-001 (or whatever CHATBOT_EMBEDDING_MODEL names)."""

    @property
    def model_name(self) -> str:
        return self._settings.embedding_model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(items), EMBED_BATCH_SIZE):
            batch = items[start : start + EMBED_BATCH_SIZE]
            vectors.extend(self._embed(batch, DOCUMENT_TASK_TYPE))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], QUERY_TASK_TYPE)[0]

    def _embed(self, batch: list[str], task_type: str) -> list[list[float]]:
        client = self._client()
        try:
            from google.genai import types

            response = client.models.embed_content(
                model=self._settings.embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._settings.embedding_dimensions,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises many types
            raise self._provider_error(
                "Không tạo được vector cho nội dung này.", exc
            ) from exc

        embeddings = getattr(response, "embeddings", None) or []
        if len(embeddings) != len(batch):
            raise ChatbotProviderError(
                "Nhà cung cấp AI trả về số lượng vector không khớp yêu cầu."
            )
        return [_unit_vector(list(item.values or [])) for item in embeddings]


class GeminiChatModelProvider(_GeminiClientMixin, ChatModelProvider):
    """gemini-3.5-flash-lite (or whatever CHATBOT_MODEL names)."""

    @property
    def model_name(self) -> str:
        return self._settings.chat_model

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        client = self._client()
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                # Grounded answering, not creative writing.
                temperature=0.2,
                max_output_tokens=1024,
                # This assistant never calls tools; the SDK enables automatic
                # function calling by default and warns on every request.
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            )
            # Flash-Lite bills and delays "thinking" tokens a short grounded
            # answer does not need. Gemini 3.x replaced the old numeric
            # thinking_budget with thinking_level and rejects the former with
            # 400 INVALID_ARGUMENT, so the tier is configurable and can be
            # switched off entirely for a model that supports neither.
            thinking_level = (self._settings.thinking_level or "").strip()
            if thinking_level:
                config.thinking_config = types.ThinkingConfig(
                    thinking_level=thinking_level
                )
            response = client.models.generate_content(
                model=self._settings.chat_model,
                contents=user_prompt,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - SDK raises many types
            raise self._provider_error(
                "Không nhận được phản hồi từ nhà cung cấp AI.", exc
            ) from exc

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise ChatbotProviderError("Nhà cung cấp AI trả về nội dung rỗng.")
        return text


def _unit_vector(values: list[float]) -> list[float]:
    """Normalize to length 1.

    gemini-embedding-001 only returns pre-normalized vectors at its full 3072
    dimensions; any truncated output_dimensionality must be normalized by the
    caller before distances are compared.
    """
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


__all__ = ["GeminiChatModelProvider", "GeminiEmbeddingProvider"]
