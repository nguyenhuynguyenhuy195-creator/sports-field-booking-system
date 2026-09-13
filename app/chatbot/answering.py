"""The static-knowledge answer pipeline.

    question -> validate -> retrieve -> evidence gate
             -> (insufficient) deterministic fallback, model NEVER called
             -> (sufficient)   safe prompt -> ChatModelProvider -> answer

Two outcomes are kept strictly apart, because conflating them is how a chatbot
starts inventing rules:

* Not enough trustworthy evidence is a NORMAL answer. The exact fallback
  sentence is returned and no model call happens at all, so the model has no
  opportunity to fill the gap from its own prior knowledge.
* A model that fails after good evidence is an OUTAGE. It raises a controlled
  ChatbotProviderError carrying only an exception type name -- never provider
  text, which can contain the API key.

Phase 2B adds a second, independent source of grounding: read-only dynamic
context for the logged-in viewer (see :mod:`.context`). Static evidence
explains policy; dynamic context explains the viewer's current state. Either
one can justify answering, but neither is automatic -- context only counts for
a question its page can actually answer (see :mod:`.context_gate`), so having
a booking on screen never turns an off-topic question into an answerable one.

Still no route and still no writes: the resolver issues SELECTs only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from .context import ResolvedDynamicContext
from .context_gate import dynamic_context_relevance
from .errors import ChatbotError, ChatbotProviderError, scrub_secrets
from .prompting import (
    ConversationTurn,
    build_system_prompt,
    build_user_prompt,
    detect_language,
    normalize_history,
    normalize_question,
)
from .providers.base import ChatModelProvider
from .retrieval import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    KnowledgeIndex,
    SourceReference,
    retrieve,
)
from .settings import ChatbotSettings


logger = logging.getLogger(__name__)

STATUS_ANSWERED = "ANSWERED"
STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

# What a caller may show when the model is unreachable. Deliberately free of
# any provider detail.
CHAT_UNAVAILABLE_MESSAGE = (
    "Trợ lý ảo tạm thời không phản hồi được. Vui lòng thử lại sau."
)


@dataclass(frozen=True)
class ChatbotAnswer:
    """The pipeline's result.

    Carries no chunk text: the retrieved passages are an internal detail of
    grounding, and echoing them back would leak more of the knowledge base
    than a citation needs to.
    """

    answer: str
    sources: tuple[SourceReference, ...]
    status: str
    retrieval_reason: str
    evidence_count: int
    language: str
    history_turns_used: int
    model_name: str | None = None
    used_dynamic_context: bool = False
    dynamic_context_reason: str = ""
    context_page_type: str | None = None

    @property
    def used_model(self) -> bool:
        return self.status == STATUS_ANSWERED

    @property
    def is_fallback(self) -> bool:
        return self.status == STATUS_INSUFFICIENT_EVIDENCE


def answer_question(
    question: str,
    *,
    chat_provider: ChatModelProvider,
    index: KnowledgeIndex | None,
    settings: ChatbotSettings,
    history: Iterable | None = None,
    context: ResolvedDynamicContext | None = None,
) -> ChatbotAnswer:
    """Answer one question from curated static knowledge.

    Raises ChatbotValidationError for unusable input and ChatbotProviderError
    when the chat model cannot be reached. A missing index is not an error: it
    simply yields no evidence, and therefore the fallback.
    """
    normalized_question = normalize_question(question)
    turns = normalize_history(history)
    language = detect_language(normalized_question)

    result = retrieve(normalized_question, index=index, settings=settings)

    # Dynamic context is a second, independent source of grounding -- but only
    # for questions it can actually answer. "Context exists" is never enough.
    context_relevant, context_reason = dynamic_context_relevance(
        question=normalized_question, context=context
    )
    dynamic_lines = (
        context.prompt_lines if context_relevant and context is not None else ()
    )
    context_page_type = context.page_type if context is not None else None

    if not result.has_sufficient_evidence and not context_relevant:
        # The model is never consulted here. This is the whole point of the
        # gate: no evidence means no chance to improvise an answer.
        return ChatbotAnswer(
            answer=INSUFFICIENT_EVIDENCE_ANSWER,
            sources=(),
            status=STATUS_INSUFFICIENT_EVIDENCE,
            retrieval_reason=result.reason,
            evidence_count=0,
            language=language,
            history_turns_used=len(turns),
            model_name=None,
            used_dynamic_context=False,
            dynamic_context_reason=context_reason,
            context_page_type=context_page_type,
        )

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        question=normalized_question,
        result=result,
        history=turns,
        language=language,
        dynamic_lines=dynamic_lines,
    )

    answer_text = _generate(
        chat_provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        settings=settings,
    )

    return ChatbotAnswer(
        answer=answer_text,
        # Backend-controlled: already deduplicated, capped at
        # settings.max_sources, and built only from retained chunks.
        sources=result.sources,
        status=STATUS_ANSWERED,
        retrieval_reason=result.reason,
        evidence_count=len(result.chunks),
        language=language,
        history_turns_used=len(turns),
        model_name=getattr(chat_provider, "model_name", None),
        used_dynamic_context=bool(dynamic_lines),
        dynamic_context_reason=context_reason,
        context_page_type=context_page_type,
    )


def _generate(
    chat_provider: ChatModelProvider,
    *,
    system_prompt: str,
    user_prompt: str,
    settings: ChatbotSettings,
) -> str:
    """Call the model, converting any failure into a controlled error.

    The raised message names only the exception type. Provider text is kept
    out of it entirely -- scrubbing alone is not enough of a guarantee when
    the string may reach a user -- while ``from exc`` preserves the detail in
    the traceback for operators.
    """
    try:
        answer = chat_provider.generate(
            system_prompt=system_prompt, user_prompt=user_prompt
        )
    except ChatbotError as exc:
        logger.warning(
            "Trợ lý ảo gọi mô hình thất bại: %s",
            scrub_secrets(exc, (settings.api_key,)),
        )
        raise ChatbotProviderError(
            f"{CHAT_UNAVAILABLE_MESSAGE} ({type(exc).__name__})"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - any SDK may raise anything
        logger.warning(
            "Trợ lý ảo gặp lỗi không mong đợi khi gọi mô hình: %s",
            scrub_secrets(type(exc).__name__, (settings.api_key,)),
        )
        raise ChatbotProviderError(
            f"{CHAT_UNAVAILABLE_MESSAGE} ({type(exc).__name__})"
        ) from exc

    text = (answer or "").strip()
    if not text:
        raise ChatbotProviderError(
            f"{CHAT_UNAVAILABLE_MESSAGE} (EmptyAnswer)"
        )
    return text


__all__ = [
    "CHAT_UNAVAILABLE_MESSAGE",
    "STATUS_ANSWERED",
    "STATUS_INSUFFICIENT_EVIDENCE",
    "ChatbotAnswer",
    "ConversationTurn",
    "answer_question",
]
