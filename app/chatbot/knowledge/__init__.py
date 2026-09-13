"""Curated chatbot knowledge base: manifest, loading and chunking."""

from .loader import (
    KnowledgeChunk,
    LoadedDocument,
    build_knowledge_chunks,
    chunk_document,
    chunk_loaded_documents,
    content_revision,
    knowledge_directory,
    knowledge_fingerprint,
    load_documents,
)
from .manifest import (
    APPROVED_FILENAMES,
    KNOWLEDGE_DIRECTORY,
    KNOWLEDGE_MANIFEST,
    KnowledgeDocument,
    get_document,
)

__all__ = [
    "APPROVED_FILENAMES",
    "KNOWLEDGE_DIRECTORY",
    "KNOWLEDGE_MANIFEST",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LoadedDocument",
    "build_knowledge_chunks",
    "chunk_document",
    "chunk_loaded_documents",
    "content_revision",
    "get_document",
    "knowledge_directory",
    "knowledge_fingerprint",
    "load_documents",
]
