"""The curated whitelist of chatbot knowledge documents.

Indexing is manifest-driven on purpose. Nothing scans ``docs/`` or the repo for
``*.md``: README.md, the ADR decision log and the older docs/ set all contain
statements that are stale or historical (MOCK-only payments, 80/20 refunds,
12-hour deadlines), and an automatic crawler would happily present them to a
user as current policy. A document is indexed only if it is listed here.
"""

from __future__ import annotations

from dataclasses import dataclass


# Relative to the repository root. Kept relative so no absolute local path can
# ever reach a user-facing source citation.
KNOWLEDGE_DIRECTORY = "docs/chatbot"


@dataclass(frozen=True)
class KnowledgeDocument:
    """One approved knowledge file."""

    slug: str
    filename: str
    title: str
    category: str
    # Which booking policy the document describes, when that matters. Current
    # documents describe DEPOSIT_30; legacy rules are named as legacy in prose.
    policy: str | None = None

    @property
    def source(self) -> str:
        """User-safe source identifier — a repo-relative path, never absolute."""
        return f"{KNOWLEDGE_DIRECTORY}/{self.filename}"


KNOWLEDGE_MANIFEST: tuple[KnowledgeDocument, ...] = (
    KnowledgeDocument(
        slug="booking",
        filename="booking.md",
        title="Đặt sân và tiền cọc",
        category="booking",
        policy="DEPOSIT_30",
    ),
    KnowledgeDocument(
        slug="matchmaking",
        filename="matchmaking.md",
        title="Tìm đối thủ và tìm thêm người",
        category="matchmaking",
        policy="DEPOSIT_30",
    ),
    KnowledgeDocument(
        slug="payments",
        filename="payments.md",
        title="Thanh toán",
        category="payments",
        policy="DEPOSIT_30",
    ),
    KnowledgeDocument(
        slug="refunds",
        filename="refunds.md",
        title="Hủy lịch và hoàn tiền",
        category="refunds",
        policy="DEPOSIT_30",
    ),
    KnowledgeDocument(
        slug="match-chat",
        filename="match-chat.md",
        title="Phòng chat trong kèo",
        category="match_chat",
    ),
    KnowledgeDocument(
        slug="faq",
        filename="faq.md",
        title="Câu hỏi thường gặp",
        category="faq",
    ),
    KnowledgeDocument(
        slug="user-guide",
        filename="user-guide.md",
        title="Hướng dẫn sử dụng",
        category="user_guide",
    ),
)

APPROVED_FILENAMES: frozenset[str] = frozenset(
    document.filename for document in KNOWLEDGE_MANIFEST
)


def get_document(slug: str) -> KnowledgeDocument | None:
    return next(
        (item for item in KNOWLEDGE_MANIFEST if item.slug == slug),
        None,
    )


__all__ = [
    "APPROVED_FILENAMES",
    "KNOWLEDGE_DIRECTORY",
    "KNOWLEDGE_MANIFEST",
    "KnowledgeDocument",
    "get_document",
]
