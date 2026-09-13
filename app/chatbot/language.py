"""Language detection shared by retrieval and prompt assembly.

Its own module because both sides need it: prompting decides what language to
answer in, and the evidence gate needs to know whether a question is in the
same language as the knowledge base before it applies a lexical check. Putting
it in either of those modules would make them import each other.
"""

from __future__ import annotations

import re


LANGUAGE_VIETNAMESE = "vi"
LANGUAGE_ENGLISH = "en"

# Everything in docs/chatbot/ is written in Vietnamese. The evidence gate uses
# this to decide whether comparing word overlap is meaningful at all.
KNOWLEDGE_BASE_LANGUAGE = LANGUAGE_VIETNAMESE

# Any Vietnamese-specific letter is decisive evidence of a Vietnamese question.
_VIETNAMESE_CHARS = re.compile(
    r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩị"
    r"òóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]",
    re.IGNORECASE,
)

# Common English function words. Only consulted when there are no Vietnamese
# letters at all, so unaccented Vietnamese still defaults to Vietnamese.
_ENGLISH_HINTS = frozenset(
    {
        "a", "am", "an", "and", "are", "at", "back", "ball", "book", "booking",
        "can", "cancel", "deposit", "do", "does", "field", "for", "get", "how",
        "i", "if", "in", "is", "it", "join", "match", "me", "money", "much",
        "my", "need", "of", "opponent", "pay", "payment", "refund", "should",
        "the", "to", "want", "what", "when", "where", "which", "who", "why",
        "will", "with", "you", "your",
    }
)
_WORD = re.compile(r"[a-z]+")


def detect_language(text: str) -> str:
    """Vietnamese unless the text is clearly English."""
    if _VIETNAMESE_CHARS.search(text):
        return LANGUAGE_VIETNAMESE
    words = set(_WORD.findall(text.lower()))
    if words and len(words & _ENGLISH_HINTS) >= 2:
        return LANGUAGE_ENGLISH
    return LANGUAGE_VIETNAMESE


def matches_knowledge_base_language(text: str) -> bool:
    """Whether word-level comparison against the knowledge base is meaningful."""
    return detect_language(text) == KNOWLEDGE_BASE_LANGUAGE


__all__ = [
    "KNOWLEDGE_BASE_LANGUAGE",
    "LANGUAGE_ENGLISH",
    "LANGUAGE_VIETNAMESE",
    "detect_language",
    "matches_knowledge_base_language",
]
