"""Load and chunk the curated knowledge base.

Reading is manifest-driven (see :mod:`.manifest`) and heading-aware: documents
are first cut at their Markdown headings so a chunk never straddles two
business rules, then any oversized section is split further with an overlap.

Every chunk carries the metadata a citation needs -- and only metadata that is
safe to show a user. The on-disk absolute path is never stored.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from ..errors import KnowledgeBaseError
from .manifest import KNOWLEDGE_DIRECTORY, KNOWLEDGE_MANIFEST, KnowledgeDocument


HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]
SECTION_SEPARATOR = " > "

# Repo root: app/chatbot/knowledge/loader.py -> up three package levels.
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class LoadedDocument:
    """One approved document plus its content and content hash."""

    document: KnowledgeDocument
    text: str
    revision: str


@dataclass(frozen=True)
class KnowledgeChunk:
    """One indexable passage with its user-safe citation metadata."""

    chunk_id: str
    content: str
    title: str
    source: str
    section: str
    category: str
    source_revision: str
    doc_slug: str
    chunk_index: int
    policy: str | None = None

    @property
    def metadata(self) -> dict:
        """Exactly what is stored alongside the vector."""
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "source": self.source,
            "section": self.section,
            "category": self.category,
            "source_revision": self.source_revision,
            "doc_slug": self.doc_slug,
            "chunk_index": self.chunk_index,
            "policy": self.policy,
        }

    def to_langchain_document(self) -> Document:
        return Document(page_content=self.content, metadata=self.metadata)


def knowledge_directory() -> Path:
    return REPO_ROOT / KNOWLEDGE_DIRECTORY


def load_documents(
    manifest: Sequence[KnowledgeDocument] = KNOWLEDGE_MANIFEST,
    *,
    base_directory: Path | None = None,
) -> list[LoadedDocument]:
    """Read every approved document. Files not in the manifest are ignored."""
    directory = base_directory or knowledge_directory()
    loaded: list[LoadedDocument] = []
    for document in manifest:
        path = directory / document.filename
        if not path.is_file():
            # The repo-relative source is safe to name; the absolute path is not.
            raise KnowledgeBaseError(
                f"Thiếu tài liệu kiến thức: {document.source}"
            )
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise KnowledgeBaseError(
                f"Không đọc được tài liệu kiến thức: {document.source}"
            ) from exc
        if not text.strip():
            raise KnowledgeBaseError(f"Tài liệu kiến thức rỗng: {document.source}")
        loaded.append(
            LoadedDocument(
                document=document,
                text=text,
                revision=content_revision(text),
            )
        )
    return loaded


def content_revision(text: str) -> str:
    """Short, stable content hash used for citations and cache keys."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def chunk_document(
    loaded: LoadedDocument,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 120,
) -> list[KnowledgeChunk]:
    """Split one document at headings, then cap each section by length."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        # Keep the heading text inside the chunk: it is a strong retrieval
        # signal and it is what the citation's section label quotes.
        strip_headers=False,
    )
    length_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    document = loaded.document
    chunks: list[KnowledgeChunk] = []
    for section_doc in header_splitter.split_text(loaded.text):
        section = _section_label(section_doc.metadata, fallback=document.title)
        for piece in length_splitter.split_text(section_doc.page_content):
            content = piece.strip()
            if not content:
                continue
            index = len(chunks)
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document.slug}:{index}",
                    content=content,
                    title=document.title,
                    source=document.source,
                    section=section,
                    category=document.category,
                    source_revision=loaded.revision,
                    doc_slug=document.slug,
                    chunk_index=index,
                    policy=document.policy,
                )
            )
    if not chunks:
        raise KnowledgeBaseError(
            f"Không tách được đoạn nội dung nào từ: {document.source}"
        )
    return chunks


def chunk_loaded_documents(
    loaded_documents: Iterable[LoadedDocument],
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 120,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for loaded in loaded_documents:
        chunks.extend(
            chunk_document(
                loaded,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks


def build_knowledge_chunks(
    manifest: Sequence[KnowledgeDocument] = KNOWLEDGE_MANIFEST,
    *,
    base_directory: Path | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 120,
) -> list[KnowledgeChunk]:
    """Load every approved document and return all of its chunks."""
    return chunk_loaded_documents(
        load_documents(manifest, base_directory=base_directory),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def knowledge_fingerprint(chunks: Sequence[KnowledgeChunk]) -> str:
    """Identity of a whole chunk set, for cache invalidation."""
    revisions = sorted({(chunk.doc_slug, chunk.source_revision) for chunk in chunks})
    digest = hashlib.sha256()
    for slug, revision in revisions:
        digest.update(f"{slug}@{revision};".encode("utf-8"))
    digest.update(f"count={len(chunks)}".encode("utf-8"))
    return digest.hexdigest()[:16]


def _section_label(metadata: dict, *, fallback: str) -> str:
    """Breadcrumb of the sub-headings, falling back to the document title."""
    parts = [
        str(metadata[key]).strip() for key in ("h2", "h3") if metadata.get(key)
    ]
    if parts:
        return SECTION_SEPARATOR.join(parts)
    return str(metadata.get("h1") or fallback).strip()


__all__ = [
    "KnowledgeChunk",
    "LoadedDocument",
    "build_knowledge_chunks",
    "chunk_document",
    "chunk_loaded_documents",
    "content_revision",
    "knowledge_directory",
    "knowledge_fingerprint",
    "load_documents",
]
