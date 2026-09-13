"""Phase 1 chatbot: the curated knowledge base and its chunking.

The point of these tests is that indexing stays *curated*. The repository is
full of Markdown that must never reach a user as current policy — README's
MOCK-only payment description, the ADR decision log, the older docs/ set with
its 80/20 refunds and 12-hour deadlines. Nothing here may start crawling them.
"""

from __future__ import annotations

import re

import pytest

from app.chatbot.errors import KnowledgeBaseError
from app.chatbot.knowledge import (
    APPROVED_FILENAMES,
    KNOWLEDGE_DIRECTORY,
    KNOWLEDGE_MANIFEST,
    KnowledgeDocument,
    build_knowledge_chunks,
    chunk_document,
    knowledge_directory,
    knowledge_fingerprint,
    load_documents,
)
from app.chatbot.knowledge.loader import REPO_ROOT, LoadedDocument, content_revision


EXPECTED_SLUGS = {
    "booking",
    "matchmaking",
    "payments",
    "refunds",
    "match-chat",
    "faq",
    "user-guide",
}


@pytest.fixture(scope="module")
def chunks():
    return build_knowledge_chunks()


# --- the manifest is the whitelist -------------------------------------------


def test_manifest_covers_exactly_the_expected_documents():
    assert {item.slug for item in KNOWLEDGE_MANIFEST} == EXPECTED_SLUGS


def test_every_manifest_document_exists_on_disk():
    for document in KNOWLEDGE_MANIFEST:
        assert (knowledge_directory() / document.filename).is_file(), document.filename


def test_knowledge_directory_holds_no_unapproved_markdown():
    """A file dropped into docs/chatbot/ is not silently half-indexed."""
    on_disk = {path.name for path in knowledge_directory().glob("*.md")}
    assert on_disk == set(APPROVED_FILENAMES)


def test_loader_reads_only_manifest_files(tmp_path):
    approved = KnowledgeDocument(
        slug="approved",
        filename="approved.md",
        title="Được duyệt",
        category="booking",
    )
    (tmp_path / "approved.md").write_text("# Được duyệt\n\nNội dung.", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README\n\nStale.", encoding="utf-8")
    (tmp_path / "10-decision-log.md").write_text("# ADR\n\nLegacy.", encoding="utf-8")

    loaded = load_documents((approved,), base_directory=tmp_path)

    assert [item.document.slug for item in loaded] == ["approved"]
    assert "Stale" not in loaded[0].text
    assert "Legacy" not in loaded[0].text


def test_missing_manifest_document_is_reported_without_absolute_path(tmp_path):
    ghost = KnowledgeDocument(
        slug="ghost",
        filename="ghost.md",
        title="Thiếu",
        category="faq",
    )

    with pytest.raises(KnowledgeBaseError) as excinfo:
        load_documents((ghost,), base_directory=tmp_path)

    message = str(excinfo.value)
    assert "docs/chatbot/ghost.md" in message
    assert str(tmp_path) not in message


def test_empty_document_is_rejected(tmp_path):
    blank = KnowledgeDocument(
        slug="blank", filename="blank.md", title="Rỗng", category="faq"
    )
    (tmp_path / "blank.md").write_text("   \n", encoding="utf-8")

    with pytest.raises(KnowledgeBaseError):
        load_documents((blank,), base_directory=tmp_path)


# --- README and the legacy docs stay out -------------------------------------


def test_readme_is_not_an_approved_document():
    assert "README.md" not in APPROVED_FILENAMES
    assert not any(
        item.filename.lower() == "readme.md" for item in KNOWLEDGE_MANIFEST
    )


def test_readme_is_not_indexed(chunks):
    sources = {chunk.source for chunk in chunks}
    assert not any("readme" in source.lower() for source in sources)


def test_legacy_docs_are_not_indexed(chunks):
    """docs/01-*.md … docs/12-*.md and the ADR log are never pulled in."""
    sources = {chunk.source for chunk in chunks}
    assert sources == {f"{KNOWLEDGE_DIRECTORY}/{name}" for name in APPROVED_FILENAMES}

    legacy_names = {path.name for path in (REPO_ROOT / "docs").glob("*.md")}
    assert legacy_names, "expected the legacy docs/ set to still exist"
    assert not (legacy_names & set(APPROVED_FILENAMES))


def test_project_instruction_files_are_not_indexed(chunks):
    contents = "\n".join(chunk.content for chunk in chunks)
    for marker in ("CURRENT_SPRINT", "AGENTS.md", "CLAUDE.md", "PHASE2_VERIFICATION"):
        assert marker not in contents


def test_knowledge_directory_is_scoped_to_docs_chatbot():
    assert knowledge_directory() == REPO_ROOT / "docs" / "chatbot"


# --- chunking and metadata ---------------------------------------------------


def test_chunk_metadata_is_preserved(chunks):
    manifest_by_slug = {item.slug: item for item in KNOWLEDGE_MANIFEST}
    assert chunks

    for chunk in chunks:
        document = manifest_by_slug[chunk.doc_slug]
        assert chunk.title == document.title
        assert chunk.source == document.source
        assert chunk.category == document.category
        assert chunk.policy == document.policy
        assert chunk.section.strip()
        assert len(chunk.source_revision) == 12
        assert chunk.chunk_id == f"{chunk.doc_slug}:{chunk.chunk_index}"

        metadata = chunk.metadata
        assert set(metadata) == {
            "chunk_id",
            "title",
            "source",
            "section",
            "category",
            "source_revision",
            "doc_slug",
            "chunk_index",
            "policy",
        }
        assert metadata["title"] == chunk.title
        assert metadata["section"] == chunk.section


def test_metadata_survives_conversion_to_langchain_documents(chunks):
    document = chunks[0].to_langchain_document()

    assert document.page_content == chunks[0].content
    assert document.metadata == chunks[0].metadata


def test_chunk_ids_are_unique(chunks):
    ids = [chunk.chunk_id for chunk in chunks]
    assert len(ids) == len(set(ids))


def test_sources_are_repo_relative_never_absolute(chunks):
    """A citation must never expose where the repo sits on this machine."""
    for chunk in chunks:
        assert chunk.source.startswith(f"{KNOWLEDGE_DIRECTORY}/")
        assert "\\" not in chunk.source
        assert not re.match(r"^[A-Za-z]:", chunk.source)
        assert str(REPO_ROOT) not in chunk.source


def test_chunking_is_heading_aware_and_keeps_headings():
    loaded = LoadedDocument(
        document=KnowledgeDocument(
            slug="sample",
            filename="sample.md",
            title="Mẫu",
            category="booking",
            policy="DEPOSIT_30",
        ),
        text=(
            "# Mẫu\n\nMở đầu.\n\n"
            "## Tiền cọc\n\nCọc là 30% tổng tiền sân.\n\n"
            "## Hủy lịch\n\nKhông hoàn cọc của người đặt.\n"
        ),
        revision="abc123abc123",
    )

    produced = chunk_document(loaded)
    sections = [chunk.section for chunk in produced]

    assert "Tiền cọc" in sections
    assert "Hủy lịch" in sections
    deposit = next(chunk for chunk in produced if chunk.section == "Tiền cọc")
    assert "## Tiền cọc" in deposit.content
    assert "30%" in deposit.content
    # Two different rules never share a chunk.
    assert "Hủy lịch" not in deposit.content


def test_oversized_section_is_split_with_overlap():
    body = " ".join(f"câu số {index}." for index in range(400))
    loaded = LoadedDocument(
        document=KnowledgeDocument(
            slug="long", filename="long.md", title="Dài", category="faq"
        ),
        text=f"# Dài\n\n## Một mục rất dài\n\n{body}\n",
        revision="0" * 12,
    )

    produced = chunk_document(loaded, chunk_size=400, chunk_overlap=100)

    assert len(produced) > 1
    assert all(len(chunk.content) <= 400 for chunk in produced)
    assert all(chunk.section == "Một mục rất dài" for chunk in produced)


def test_chunks_stay_within_the_configured_size(chunks):
    assert all(len(chunk.content) <= 1000 for chunk in chunks)


def test_every_manifest_document_produces_chunks(chunks):
    produced = {chunk.doc_slug for chunk in chunks}
    assert produced == EXPECTED_SLUGS


# --- the fingerprint tracks content ------------------------------------------


def test_fingerprint_changes_when_content_changes():
    first = build_knowledge_chunks()
    baseline = knowledge_fingerprint(first)

    assert baseline == knowledge_fingerprint(build_knowledge_chunks())
    assert content_revision("a") != content_revision("b")


# --- no private data in static knowledge -------------------------------------


def test_static_knowledge_contains_no_private_or_secret_data(chunks):
    """Static knowledge is shared by every viewer, so nothing per-user may
    live in it — and no credential may either."""
    body = "\n".join(chunk.content for chunk in chunks)

    assert "@" not in body, "an email address would be personal data"
    # Phone numbers / ids: any run of 9+ digits.
    assert not re.search(r"\d{9,}", body)
    for secret_marker in (
        "GEMINI_API_KEY",
        "SECRET_KEY",
        "VNPAY_HASH_SECRET",
        "VNPAY_TMN_CODE",
        "password",
        "Bearer ",
    ):
        assert secret_marker not in body, secret_marker


def test_static_knowledge_holds_no_per_user_records(chunks):
    body = "\n".join(chunk.content for chunk in chunks).lower()
    for marker in ("booking_code", "user_id=", "payer_id", "order_id"):
        assert marker not in body, marker


def test_chunk_metadata_carries_no_user_fields(chunks):
    for chunk in chunks:
        assert "user" not in set(chunk.metadata)
        assert "user_id" not in set(chunk.metadata)


# --- the knowledge base states the current rules, not the legacy ones ---------


def test_knowledge_states_the_current_deposit_rate(chunks):
    deposit_text = "\n".join(
        chunk.content for chunk in chunks if chunk.category == "booking"
    )
    assert "30%" in deposit_text


def test_legacy_policies_are_labelled_as_legacy_where_mentioned(chunks):
    """The 80/20 split and the 12-hour window exist only as history.

    They may appear, but never as a description of what happens to a new
    booking — every mention sits in a section that names it as an old policy.
    """
    for chunk in chunks:
        if "80%" in chunk.content or "12 giờ" in chunk.content:
            assert any(
                marker in chunk.content
                for marker in ("cũ", "lịch sử", "trước đây", "không áp dụng")
            ), chunk.chunk_id
