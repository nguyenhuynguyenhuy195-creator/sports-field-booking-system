"""Deterministic relevance gate for dynamic context.

Resolved context must not be a free pass. If merely *having* a booking on
screen let every question through, "Giá Bitcoin hôm nay bao nhiêu?" would be
answered by a model holding that booking in its prompt — the exact
false-confidence failure the static evidence gate exists to prevent.

The gate matches **phrases**, not single syllables. A single-syllable rule was
too loose: Vietnamese splits "tài khoản", "giá tiền", "người chơi" and "địa
chỉ" into syllables that overlap the domain vocabulary, so "Tôi có bao nhiêu
tiền trong tài khoản?" and "Địa chỉ Nhà Trắng ở đâu?" both looked relevant on
the strength of one generic word. Requiring a domain *phrase* ("tiền cọc",
"còn thiếu", "cơ sở", "phòng chat") removes that whole class of false
positive while still accepting short real questions.

Text is compared with diacritics stripped, so "co so nay mo cua may gio"
behaves exactly like "cơ sở này mở cửa mấy giờ" without loosening anything:
the phrase requirement is what does the filtering, not the accents.

Still deterministic and keyword-based on purpose: no second model call, no
embedding, no score to tune. A reviewer can read the phrase lists and know
exactly what passes.
"""

from __future__ import annotations

import re
import unicodedata

from .context import (
    PAGE_BOOKING_DETAIL,
    PAGE_MATCH_DETAIL,
    PAGE_VENUE_DETAIL,
    ResolvedDynamicContext,
)


REASON_NO_CONTEXT = "no_dynamic_context"
REASON_NO_VOCABULARY = "page_has_no_vocabulary"
REASON_OFF_TOPIC = "question_outside_page_vocabulary"
REASON_RELEVANT = "question_matches_page_vocabulary"

_WORD = re.compile(r"[0-9a-z]+")

# Phrases that are unambiguously about this system's money and scheduling.
# Written unaccented because that is how questions are normalised before
# matching. Multi-word entries must appear as consecutive syllables.
_MONEY_PHRASES = {
    "coc", "tien coc", "dat coc", "tien con lai", "so tien", "con thieu",
    "con no", "thanh toan", "da tra", "da dong", "da thanh toan", "hoan tien",
    "duoc hoan", "tra tai san", "tai san bao nhieu", "khoan coc", "phi huy",
    "giao dich", "deposit", "refund", "payment", "paid", "balance",
}
_BOOKING_PHRASES = {
    "lich dat", "dat san", "san nay", "huy lich", "huy san", "trang thai",
    "ma dat", "ma lich", "booking", "gio choi", "khung gio", "ngay dat",
    "con han", "het han",
} | _MONEY_PHRASES

_MATCH_PHRASES = {
    "keo", "keo nay", "tran nay", "doi thu", "tham gia", "da tham gia",
    "rut khoi", "rut keo", "phong chat", "chat", "tin nhan", "nhan tin",
    "suat", "con thieu", "con trong", "so nguoi", "nguoi tham gia",
    "chu keo", "vai tro", "trang thai", "match", "opponent", "join",
} | _MONEY_PHRASES

_VENUE_PHRASES = {
    "co so", "san bong", "san nay", "dia chi o dau", "dia chi cua",
    "mo cua", "dong cua", "gio mo", "gio dong", "gio hoat dong", "lien he",
    "so dien thoai", "suc chua", "mon the thao", "loai san", "venue",
    "open", "close",
}

PAGE_PHRASES: dict[str, frozenset[str]] = {
    PAGE_BOOKING_DETAIL: frozenset(_BOOKING_PHRASES),
    PAGE_MATCH_DETAIL: frozenset(_MATCH_PHRASES),
    PAGE_VENUE_DETAIL: frozenset(_VENUE_PHRASES),
}

# Longest phrase in any list, so only that many syllables need joining.
_MAX_PHRASE_WORDS = max(
    len(phrase.split())
    for phrases in PAGE_PHRASES.values()
    for phrase in phrases
)


def strip_diacritics(text: str) -> str:
    """Lowercase and remove Vietnamese accents; 'đ' becomes 'd'."""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )


def question_phrases(question: str) -> set[str]:
    """Every 1..N-syllable run in the question, normalised for comparison."""
    words = _WORD.findall(strip_diacritics(question))
    found: set[str] = set()
    for start in range(len(words)):
        for size in range(1, _MAX_PHRASE_WORDS + 1):
            if start + size > len(words):
                break
            found.add(" ".join(words[start : start + size]))
    return found


def dynamic_context_relevance(
    *,
    question: str,
    context: ResolvedDynamicContext | None,
) -> tuple[bool, str]:
    """Return ``(is_relevant, reason)`` for this question and context."""
    if context is None or not context.available:
        return False, REASON_NO_CONTEXT
    phrases = PAGE_PHRASES.get(context.page_type)
    if not phrases:
        return False, REASON_NO_VOCABULARY
    if question_phrases(question) & phrases:
        return True, REASON_RELEVANT
    return False, REASON_OFF_TOPIC


def is_dynamic_context_relevant(
    *, question: str, context: ResolvedDynamicContext | None
) -> bool:
    return dynamic_context_relevance(question=question, context=context)[0]


__all__ = [
    "PAGE_PHRASES",
    "REASON_NO_CONTEXT",
    "REASON_NO_VOCABULARY",
    "REASON_OFF_TOPIC",
    "REASON_RELEVANT",
    "dynamic_context_relevance",
    "is_dynamic_context_relevant",
    "question_phrases",
    "strip_diacritics",
]
