"""Deterministic relevance gate for dynamic context.

Resolved context must not be a free pass. If merely *having* a booking on
screen let every question through, "Giá Bitcoin hôm nay bao nhiêu?" would be
answered by a model holding that booking in its prompt — the exact
false-confidence failure the static evidence gate exists to prevent.

So the question has to be about the kind of thing this context can answer. The
test is a fixed per-page vocabulary, matched against the same content tokens
the static gate uses. It is deliberately keyword-based and conservative: no
second model call, no embedding, no scoring to tune — a reviewer can read the
word lists and know exactly what passes.

Words that are common to any question ("bao nhiêu", "giá", "thế nào") are left
out on purpose; they would let unrelated questions through.
"""

from __future__ import annotations

from .context import (
    PAGE_BOOKING_DETAIL,
    PAGE_MATCH_DETAIL,
    PAGE_VENUE_DETAIL,
    ResolvedDynamicContext,
)
from .retrieval import content_tokens


# Vietnamese is tokenised per syllable, so multi-syllable terms are listed as
# their parts ("thanh toán" -> "thanh", "toán").
_MONEY_TERMS = {
    "cọc", "tiền", "thanh", "toán", "trả", "thiếu", "nợ", "khoản", "phí",
    "hoàn", "refund", "deposit", "paid", "pay", "payment", "owe", "remaining",
    "balance", "money", "amount", "vnd",
}
_BOOKING_TERMS = {
    "lịch", "đặt", "sân", "booking", "book", "hủy", "cancel", "trạng", "thái",
    "status", "mã", "code", "giờ", "ngày", "date", "time", "slot",
} | _MONEY_TERMS

_MATCH_TERMS = {
    "kèo", "match", "trận", "đối", "thủ", "opponent", "tham", "gia", "join",
    "joined", "rút", "withdraw", "chat", "phòng", "nhắn", "tin", "message",
    "slot", "suất", "người", "chơi", "player", "players", "trạng", "thái",
    "status", "vai", "trò", "role", "creator", "chủ",
} | _MONEY_TERMS

_VENUE_TERMS = {
    "cơ", "sở", "venue", "sân", "field", "địa", "chỉ", "address", "mở",
    "đóng", "cửa", "giờ", "hours", "open", "close", "điện", "thoại", "phone",
    "liên", "hệ", "contact", "môn", "sport", "sức", "chứa", "capacity",
}

PAGE_VOCABULARY: dict[str, frozenset[str]] = {
    PAGE_BOOKING_DETAIL: frozenset(_BOOKING_TERMS),
    PAGE_MATCH_DETAIL: frozenset(_MATCH_TERMS),
    PAGE_VENUE_DETAIL: frozenset(_VENUE_TERMS),
}

REASON_NO_CONTEXT = "no_dynamic_context"
REASON_NO_VOCABULARY = "page_has_no_vocabulary"
REASON_OFF_TOPIC = "question_outside_page_vocabulary"
REASON_RELEVANT = "question_matches_page_vocabulary"


def dynamic_context_relevance(
    *,
    question: str,
    context: ResolvedDynamicContext | None,
) -> tuple[bool, str]:
    """Return ``(is_relevant, reason)`` for this question and context."""
    if context is None or not context.available:
        return False, REASON_NO_CONTEXT
    vocabulary = PAGE_VOCABULARY.get(context.page_type)
    if not vocabulary:
        return False, REASON_NO_VOCABULARY
    if content_tokens(question) & vocabulary:
        return True, REASON_RELEVANT
    return False, REASON_OFF_TOPIC


def is_dynamic_context_relevant(
    *, question: str, context: ResolvedDynamicContext | None
) -> bool:
    return dynamic_context_relevance(question=question, context=context)[0]


__all__ = [
    "PAGE_VOCABULARY",
    "REASON_NO_CONTEXT",
    "REASON_NO_VOCABULARY",
    "REASON_OFF_TOPIC",
    "REASON_RELEVANT",
    "dynamic_context_relevance",
    "is_dynamic_context_relevant",
]
