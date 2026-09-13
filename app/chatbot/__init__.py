"""Chatbot foundation: settings, providers and curated-knowledge retrieval.

Phase 1 scope. This package builds and searches a static knowledge index and
decides whether what it found may be used as evidence. It deliberately does
NOT contain: the HTTP query endpoint, any per-user data resolver, the chat UI,
conversation history, or anything that writes to the database.

Importing this package must never require an AI SDK or an API key -- the
vendor SDK is imported lazily inside the Gemini provider -- so Flask starts
normally with the chatbot disabled or unconfigured.
"""

from .answering import (
    CHAT_UNAVAILABLE_MESSAGE,
    STATUS_ANSWERED,
    STATUS_INSUFFICIENT_EVIDENCE,
    ChatbotAnswer,
    answer_question,
)
from .errors import (
    ChatbotError,
    ChatbotProviderError,
    ChatbotUnavailableError,
    ChatbotValidationError,
    KnowledgeBaseError,
    scrub_secrets,
)
from .prompting import (
    MAX_HISTORY_MESSAGES,
    MAX_HISTORY_TURNS,
    MAX_QUESTION_LENGTH,
    ConversationTurn,
    build_system_prompt,
    build_user_prompt,
    normalize_history,
    normalize_question,
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
    "CHAT_UNAVAILABLE_MESSAGE",
    "INSUFFICIENT_EVIDENCE_ANSWER",
    "KNOWLEDGE_MANIFEST",
    "MAX_HISTORY_MESSAGES",
    "MAX_HISTORY_TURNS",
    "MAX_QUESTION_LENGTH",
    "STATUS_ANSWERED",
    "STATUS_INSUFFICIENT_EVIDENCE",
    "ChatModelProvider",
    "ChatbotAnswer",
    "ChatbotError",
    "ChatbotProviderError",
    "ChatbotSettings",
    "ChatbotUnavailableError",
    "ChatbotValidationError",
    "ConversationTurn",
    "EmbeddingProvider",
    "KnowledgeBaseError",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeIndex",
    "RetrievalResult",
    "RetrievedChunk",
    "SourceReference",
    "answer_question",
    "build_chat_model_provider",
    "build_embedding_provider",
    "build_knowledge_chunks",
    "build_knowledge_index",
    "build_system_prompt",
    "build_user_prompt",
    "evaluate_evidence",
    "get_knowledge_index",
    "load_documents",
    "normalize_history",
    "normalize_question",
    "reset_knowledge_index",
    "retrieve",
    "scrub_secrets",
]
