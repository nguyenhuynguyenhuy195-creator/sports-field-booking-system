"""Chatbot foundation: settings, providers and curated-knowledge retrieval.

Phase 1 scope. This package builds and searches a static knowledge index and
decides whether what it found may be used as evidence. It deliberately does
NOT contain: the HTTP query endpoint, any per-user data resolver, the chat UI,
conversation history, or anything that writes to the database.

Importing this package must never require an AI SDK or an API key -- the
vendor SDK is imported lazily inside the Gemini provider -- so Flask starts
normally with the chatbot disabled or unconfigured.
"""

from .errors import (
    ChatbotError,
    ChatbotProviderError,
    ChatbotUnavailableError,
    KnowledgeBaseError,
    scrub_secrets,
)
from .knowledge import (
    KNOWLEDGE_MANIFEST,
    KnowledgeChunk,
    KnowledgeDocument,
    build_knowledge_chunks,
    load_documents,
)
from .providers import (
    ChatModelProvider,
    EmbeddingProvider,
    build_chat_model_provider,
    build_embedding_provider,
)
from .retrieval import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    KnowledgeIndex,
    RetrievalResult,
    RetrievedChunk,
    SourceReference,
    build_knowledge_index,
    evaluate_evidence,
    get_knowledge_index,
    reset_knowledge_index,
    retrieve,
)
from .settings import ChatbotSettings

__all__ = [
    "INSUFFICIENT_EVIDENCE_ANSWER",
    "KNOWLEDGE_MANIFEST",
    "ChatModelProvider",
    "ChatbotError",
    "ChatbotProviderError",
    "ChatbotSettings",
    "ChatbotUnavailableError",
    "EmbeddingProvider",
    "KnowledgeBaseError",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeIndex",
    "RetrievalResult",
    "RetrievedChunk",
    "SourceReference",
    "build_chat_model_provider",
    "build_embedding_provider",
    "build_knowledge_chunks",
    "build_knowledge_index",
    "evaluate_evidence",
    "get_knowledge_index",
    "load_documents",
    "reset_knowledge_index",
    "retrieve",
    "scrub_secrets",
]
