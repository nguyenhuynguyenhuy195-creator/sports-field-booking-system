"""Retrieval over the curated knowledge base, with an evidence gate.

Two rules drive this module.

1. The index is built once per process and reused. Embedding the whole
   knowledge base on every question would be slow and would spend quota for
   nothing, so the built index is cached on the Flask app. It is rebuilt when
   the embedding model or its dimensions change; editing a knowledge document
   needs a restart or an explicit ``reset_knowledge_index`` call, because
   nothing re-reads docs/chatbot/ on its own.

2. "top-k returned something" is NOT evidence. A vector store always returns
   its k nearest neighbours, however far away they are, so an unrelated
   question still gets four confident-looking chunks back. ``evaluate_evidence``
   applies a similarity floor and, for borderline scores, a lexical-overlap
   check before any of it may be called evidence. When the gate rejects the
   hits, the caller must answer with INSUFFICIENT_EVIDENCE_ANSWER verbatim
   rather than letting the model improvise from its own prior knowledge.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Sequence

from langchain_core.vectorstores import InMemoryVectorStore

from .errors import (
    ChatbotError,
    ChatbotProviderError,
    KnowledgeBaseError,
    scrub_secrets,
)
from .knowledge import KnowledgeChunk, build_knowledge_chunks, knowledge_fingerprint
from .language import matches_knowledge_base_language
from .providers.base import EmbeddingProvider, LangChainEmbeddingAdapter
from .settings import ChatbotSettings


logger = logging.getLogger(__name__)

# The exact deterministic answer for "no trustworthy evidence". Returned by the
# backend without calling the LLM at all.
INSUFFICIENT_EVIDENCE_ANSWER = (
    "Tôi chưa có đủ thông tin để trả lời chính xác câu này."
)

APP_EXTENSION_KEY = "chatbot_knowledge_index"

CONTEXT_SEPARATOR = "\n\n---\n\n"

# Reasons recorded on a RetrievalResult. Stable strings so tests and logs can
# assert on *why* the gate decided what it decided.
REASON_EMPTY_QUESTION = "empty_question"
REASON_NO_HITS = "no_hits"
REASON_BELOW_THRESHOLD = "below_threshold"
REASON_WEAK_WITHOUT_OVERLAP = "weak_similarity_without_lexical_overlap"
REASON_STRONG_SIMILARITY = "strong_similarity"
REASON_THRESHOLD_WITH_OVERLAP = "threshold_with_lexical_overlap"
REASON_CROSS_LANGUAGE_THRESHOLD = "cross_language_threshold"

_TOKEN_PATTERN = re.compile(r"[0-9a-zà-ỹ]+", re.IGNORECASE)

# Function words carry no topical signal, so they must not be able to satisfy
# the overlap check on their own ("tôi có thể ..." matches every document).
VIETNAMESE_STOPWORDS = frozenset(
    {
        "anh", "bao", "bang", "bi", "bơi", "bạn", "bằng", "bị", "chi", "cho",
        "chưa", "chỉ", "co", "con", "cua", "cà", "các", "cách", "cái", "còn",
        "có", "của", "cùng", "cũng", "da", "de", "do", "duoc", "dùng", "được",
        "gi", "gì", "hay", "hoặc", "hơn", "khi", "khong", "không", "la", "lam",
        "làm", "là", "lúc", "mà", "minh", "mình", "mot", "muốn", "mỗi", "một",
        "nao", "này", "nao", "nhiều", "như", "nhưng", "nào", "nếu", "nữa", "o",
        "phai", "phải", "qua", "ra", "rằng", "rồi", "sao", "se", "sẽ", "the",
        "theo", "thi", "thì", "thế", "toi", "tôi", "từ", "va", "vay", "và",
        "vào", "vì", "vậy", "với", "ạ", "ở", "đang", "đây", "đã", "để", "đến",
        "đi", "được", "ơi",
    }
)


@dataclass(frozen=True)
class SourceReference:
    """A citation. Always derived from a chunk that was actually retrieved.

    ``source`` is the repo-relative document path and stays server-side: it is
    useful for auditing which file grounded an answer, but it is an internal
    layout detail. ``doc_slug`` is the manifest's own stable identifier and is
    what may safely be published to a browser.
    """

    title: str
    section: str
    source: str
    source_revision: str
    doc_slug: str = ""

    @property
    def label(self) -> str:
        if self.section and self.section != self.title:
            return f"{self.title} — {self.section}"
        return self.title


@dataclass(frozen=True)
class RetrievedChunk:
    """One hit with its similarity score and user-safe metadata."""

    content: str
    score: float
    chunk_id: str
    title: str
    section: str
    source: str
    category: str
    source_revision: str
    policy: str | None = None
    doc_slug: str = ""

    def as_source(self) -> SourceReference:
        return SourceReference(
            title=self.title,
            section=self.section,
            source=self.source,
            source_revision=self.source_revision,
            doc_slug=self.doc_slug,
        )


@dataclass(frozen=True)
class RetrievalResult:
    """Outcome of one retrieval, including the gate's verdict."""

    question: str
    chunks: tuple[RetrievedChunk, ...]
    sources: tuple[SourceReference, ...]
    has_sufficient_evidence: bool
    reason: str
    best_score: float = 0.0

    @property
    def fallback_answer(self) -> str | None:
        """The deterministic answer to send when evidence is insufficient."""
        if self.has_sufficient_evidence:
            return None
        return INSUFFICIENT_EVIDENCE_ANSWER

    @property
    def context_text(self) -> str:
        """The grounded context block handed to the chat model.

        Empty whenever the gate refused: a rejected hit must never reach the
        prompt, or the model would quietly answer from it anyway.
        """
        if not self.has_sufficient_evidence:
            return ""
        return CONTEXT_SEPARATOR.join(
            f"[{index}] {chunk.title} — {chunk.section}\n{chunk.content}"
            for index, chunk in enumerate(self.chunks, start=1)
        )


class KnowledgeIndex:
    """An embedded, searchable copy of the curated knowledge base."""

    def __init__(
        self,
        *,
        store: InMemoryVectorStore,
        fingerprint: str,
        chunk_count: int,
        embedding_model: str,
    ) -> None:
        self._store = store
        self.fingerprint = fingerprint
        self.chunk_count = chunk_count
        self.embedding_model = embedding_model

    def stored_documents(self) -> list[tuple[str, str, dict]]:
        """Every stored record as ``(id, text, metadata)``.

        Exposed so the contents of the shared index can be audited — it holds
        static public knowledge only, and a test asserts that it never grows
        any per-user data.
        """
        return [
            (str(key), str(record.get("text", "")), dict(record.get("metadata") or {}))
            for key, record in self._store.store.items()
        ]

    def search(self, question: str, *, top_k: int) -> list[RetrievedChunk]:
        """Nearest chunks, unfiltered. The gate is applied separately."""
        if not question.strip() or top_k <= 0:
            return []
        try:
            hits = self._store.similarity_search_with_score(question, k=top_k)
        except ChatbotError:
            raise
        except Exception as exc:  # noqa: BLE001 - store/provider may raise anything
            raise ChatbotProviderError(
                f"Không tra cứu được kho kiến thức ({type(exc).__name__})."
            ) from exc
        return [_to_retrieved_chunk(document, score) for document, score in hits]


def build_knowledge_index(
    *,
    embedding_provider: EmbeddingProvider,
    settings: ChatbotSettings,
    chunks: Sequence[KnowledgeChunk] | None = None,
) -> KnowledgeIndex:
    """Embed the curated knowledge base into a fresh in-memory index.

    Only static, public knowledge is ever embedded here. No booking, payment,
    refund or other per-user data may enter this store: it is shared by every
    request in the process and is not scoped to any viewer.
    """
    knowledge_chunks = list(
        chunks
        if chunks is not None
        else build_knowledge_chunks(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    )
    if not knowledge_chunks:
        raise KnowledgeBaseError("Kho kiến thức trợ lý ảo đang rỗng.")

    store = InMemoryVectorStore(LangChainEmbeddingAdapter(embedding_provider))
    try:
        store.add_documents(
            [chunk.to_langchain_document() for chunk in knowledge_chunks],
            ids=[chunk.chunk_id for chunk in knowledge_chunks],
        )
    except ChatbotError:
        raise
    except Exception as exc:  # noqa: BLE001 - provider may raise anything
        raise ChatbotProviderError(
            f"Không tạo được chỉ mục kho kiến thức ({type(exc).__name__})."
        ) from exc

    return KnowledgeIndex(
        store=store,
        fingerprint=(
            f"{knowledge_fingerprint(knowledge_chunks)}:{settings.index_fingerprint}"
        ),
        chunk_count=len(knowledge_chunks),
        embedding_model=embedding_provider.model_name,
    )


def get_knowledge_index(
    app,
    *,
    embedding_provider: EmbeddingProvider,
    settings: ChatbotSettings,
) -> KnowledgeIndex | None:
    """Return the process-wide index, building it on first use.

    Cached per application and keyed by the embedding model and dimensions, so
    a question never re-embeds the knowledge base. Edited documents are picked
    up by ``reset_knowledge_index`` or a restart, not automatically.

    Returns ``None`` instead of raising when the index cannot be built, so a
    provider outage degrades the chatbot rather than breaking the request or
    the application. The failure is logged, never surfaced with secrets.
    """
    cache = app.extensions.setdefault(
        APP_EXTENSION_KEY, {"lock": threading.Lock(), "index": None, "key": None}
    )
    key = settings.index_fingerprint
    if cache.get("index") is not None and cache.get("key") == key:
        return cache["index"]
    with cache["lock"]:
        # Re-check inside the lock: another thread may have built it while we
        # waited, and embedding the whole base twice is exactly what this
        # cache exists to avoid.
        if cache.get("index") is not None and cache.get("key") == key:
            return cache["index"]
        try:
            built = build_knowledge_index(
                embedding_provider=embedding_provider,
                settings=settings,
            )
        except ChatbotError as exc:
            # Scrub again at the log site. The Gemini provider already cleans
            # its own errors, but this is the single place every provider's
            # failure text reaches a log, so the guarantee is enforced here
            # regardless of which implementation raised.
            logger.warning(
                "Không dựng được chỉ mục trợ lý ảo: %s",
                scrub_secrets(exc, (settings.api_key,)),
            )
            return None
        cache["index"] = built
        cache["key"] = key
        return built


def reset_knowledge_index(app) -> None:
    """Drop the cached index so the next call rebuilds it.

    This is the supported way to pick up edited knowledge documents without
    restarting: nothing re-reads docs/chatbot/ on its own.
    """
    cache = app.extensions.get(APP_EXTENSION_KEY)
    if cache is not None:
        cache["index"] = None
        cache["key"] = None


def evaluate_evidence(
    *,
    question: str,
    hits: Sequence[RetrievedChunk],
    settings: ChatbotSettings,
) -> RetrievalResult:
    """Decide whether the hits may be treated as evidence.

    A hit is retained only if its similarity clears ``min_relevance_score``.
    Retained hits count as evidence when either the best score is strong on its
    own, or the question shares at least one content word with them -- the
    second check is what stops a mediocre-but-uniform similarity score from
    turning an unrelated question into a confident, cited answer.
    """
    normalized_question = question.strip()
    if not normalized_question:
        return _insufficient(question, REASON_EMPTY_QUESTION)
    if not hits:
        return _insufficient(normalized_question, REASON_NO_HITS)

    ranked = sorted(hits, key=lambda chunk: chunk.score, reverse=True)
    best_score = ranked[0].score
    retained = tuple(
        chunk for chunk in ranked if chunk.score >= settings.min_relevance_score
    )
    if not retained:
        return _insufficient(
            normalized_question, REASON_BELOW_THRESHOLD, best_score=best_score
        )

    if best_score >= settings.strong_relevance_score:
        reason = REASON_STRONG_SIMILARITY
    elif not matches_knowledge_base_language(normalized_question):
        # The knowledge base is Vietnamese. An English question shares no
        # content words with it, so absence of overlap says nothing about
        # relevance and the check can only ever reject. Measured against the
        # live embedding model, English off-topic questions top out around
        # 0.58 while English on-topic ones start around 0.69, so the score
        # floor alone already separates them here.
        reason = REASON_CROSS_LANGUAGE_THRESHOLD
    elif _has_lexical_overlap(normalized_question, retained):
        reason = REASON_THRESHOLD_WITH_OVERLAP
    else:
        return _insufficient(
            normalized_question,
            REASON_WEAK_WITHOUT_OVERLAP,
            best_score=best_score,
        )

    return RetrievalResult(
        question=normalized_question,
        chunks=retained,
        sources=_collect_sources(retained, limit=settings.max_sources),
        has_sufficient_evidence=True,
        reason=reason,
        best_score=best_score,
    )


def retrieve(
    question: str,
    *,
    index: KnowledgeIndex | None,
    settings: ChatbotSettings,
) -> RetrievalResult:
    """Search the index and apply the evidence gate in one step."""
    if index is None:
        return _insufficient(question.strip(), REASON_NO_HITS)
    hits = index.search(question, top_k=settings.retrieval_top_k)
    return evaluate_evidence(question=question, hits=hits, settings=settings)


def _collect_sources(
    chunks: Sequence[RetrievedChunk], *, limit: int
) -> tuple[SourceReference, ...]:
    """Deduplicate citations, preserving the retrieval ranking."""
    seen: set[tuple[str, str]] = set()
    sources: list[SourceReference] = []
    for chunk in chunks:
        source = chunk.as_source()
        key = (source.title, source.section)
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
        if len(sources) >= limit:
            break
    return tuple(sources)


def _insufficient(
    question: str, reason: str, *, best_score: float = 0.0
) -> RetrievalResult:
    return RetrievalResult(
        question=question,
        chunks=(),
        sources=(),
        has_sufficient_evidence=False,
        reason=reason,
        best_score=best_score,
    )


def content_tokens(text: str) -> set[str]:
    """Topical words of ``text``: lowercased, stopwords and single letters out."""
    return {
        token
        for token in (match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text))
        if len(token) > 1 and token not in VIETNAMESE_STOPWORDS
    }


def _has_lexical_overlap(question: str, chunks: Sequence[RetrievedChunk]) -> bool:
    asked = content_tokens(question)
    if not asked:
        return False
    return any(
        asked & content_tokens(f"{chunk.section} {chunk.content}")
        for chunk in chunks
    )


def _to_retrieved_chunk(document, score: float) -> RetrievedChunk:
    metadata = document.metadata or {}
    return RetrievedChunk(
        content=document.page_content,
        score=float(score),
        chunk_id=str(metadata.get("chunk_id", "")),
        title=str(metadata.get("title", "")),
        section=str(metadata.get("section", "")),
        source=str(metadata.get("source", "")),
        category=str(metadata.get("category", "")),
        source_revision=str(metadata.get("source_revision", "")),
        policy=metadata.get("policy"),
        doc_slug=str(metadata.get("doc_slug", "")),
    )


__all__ = [
    "APP_EXTENSION_KEY",
    "INSUFFICIENT_EVIDENCE_ANSWER",
    "KnowledgeIndex",
    "REASON_BELOW_THRESHOLD",
    "REASON_CROSS_LANGUAGE_THRESHOLD",
    "REASON_EMPTY_QUESTION",
    "REASON_NO_HITS",
    "REASON_STRONG_SIMILARITY",
    "REASON_THRESHOLD_WITH_OVERLAP",
    "REASON_WEAK_WITHOUT_OVERLAP",
    "RetrievalResult",
    "RetrievedChunk",
    "SourceReference",
    "build_knowledge_index",
    "content_tokens",
    "evaluate_evidence",
    "get_knowledge_index",
    "reset_knowledge_index",
    "retrieve",
]
