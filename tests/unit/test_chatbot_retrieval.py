"""Phase 1 chatbot: retrieval, the evidence gate and provider failure.

The gate is the security-relevant part. A vector store always hands back its k
nearest neighbours no matter how far away they are, so "top-k returned
something" is not evidence — see
``test_unrelated_question_still_produces_hits_but_no_evidence``, which uses the
real knowledge base and shows an unrelated question scoring well above zero.
"""

from __future__ import annotations

import pytest

from app.chatbot.errors import (
    ChatbotProviderError,
    ChatbotUnavailableError,
    scrub_secrets,
)
from app.chatbot.providers import build_chat_model_provider, build_embedding_provider
from app.chatbot.providers.gemini import GeminiEmbeddingProvider
from app.chatbot.retrieval import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    REASON_BELOW_THRESHOLD,
    REASON_CROSS_LANGUAGE_THRESHOLD,
    REASON_EMPTY_QUESTION,
    REASON_NO_HITS,
    REASON_STRONG_SIMILARITY,
    REASON_THRESHOLD_WITH_OVERLAP,
    REASON_WEAK_WITHOUT_OVERLAP,
    RetrievedChunk,
    build_knowledge_index,
    content_tokens,
    evaluate_evidence,
    retrieve,
)
from app.chatbot.settings import ChatbotSettings
from chatbot_doubles import (
    ExplodingEmbeddingProvider,
    FailingEmbeddingProvider,
    LexicalEmbeddingProvider,
    QueryFailingEmbeddingProvider,
)


FAKE_KEY = "test-gemini-key-0123456789"

# The lexical test double scores lower than a real embedding model would, so
# the gate is re-tuned for it. The production defaults live in config.py and
# still need measuring against a live model.
LEXICAL_MIN_SCORE = 0.40
LEXICAL_STRONG_SCORE = 0.95


def make_settings(**overrides) -> ChatbotSettings:
    values = {
        "enabled": True,
        "api_key": FAKE_KEY,
        "min_relevance_score": LEXICAL_MIN_SCORE,
        "strong_relevance_score": LEXICAL_STRONG_SCORE,
    }
    values.update(overrides)
    return ChatbotSettings(**values)


@pytest.fixture(scope="module")
def settings() -> ChatbotSettings:
    return make_settings()


@pytest.fixture(scope="module")
def index(settings):
    return build_knowledge_index(
        embedding_provider=LexicalEmbeddingProvider(), settings=settings
    )


def chunk(score: float, *, content: str = "Tiền cọc là 30%.", **overrides):
    values = {
        "content": content,
        "score": score,
        "chunk_id": "booking:1",
        "title": "Đặt sân và tiền cọc",
        "section": "Tiền cọc là bao nhiêu",
        "source": "docs/chatbot/booking.md",
        "category": "booking",
        "source_revision": "abc123abc123",
        "policy": "DEPOSIT_30",
    }
    values.update(overrides)
    return RetrievedChunk(**values)


# --- the evidence gate -------------------------------------------------------


def test_empty_question_is_never_evidence(settings):
    result = evaluate_evidence(question="   ", hits=[chunk(0.99)], settings=settings)

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_EMPTY_QUESTION
    assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER


def test_no_hits_is_never_evidence(settings):
    result = evaluate_evidence(question="Tiền cọc?", hits=[], settings=settings)

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_NO_HITS


def test_hits_below_the_threshold_are_rejected(settings):
    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?",
        hits=[chunk(0.31), chunk(0.12)],
        settings=settings,
    )

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_BELOW_THRESHOLD
    assert result.best_score == pytest.approx(0.31)
    assert result.chunks == ()
    assert result.sources == ()


def test_strong_similarity_alone_is_evidence(settings):
    result = evaluate_evidence(
        question="hoàn toàn không trùng chữ nào",
        hits=[chunk(0.97)],
        settings=settings,
    )

    assert result.has_sufficient_evidence is True
    assert result.reason == REASON_STRONG_SIMILARITY


def test_borderline_score_needs_lexical_overlap(settings):
    """A merely-above-threshold score does not turn an unrelated question into
    a cited answer."""
    result = evaluate_evidence(
        question="quantum entanglement superconductor",
        hits=[chunk(0.55)],
        settings=settings,
    )

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_WEAK_WITHOUT_OVERLAP
    assert result.best_score == pytest.approx(0.55)
    assert result.context_text == ""


def test_borderline_score_with_overlap_is_evidence(settings):
    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?",
        hits=[chunk(0.55)],
        settings=settings,
    )

    assert result.has_sufficient_evidence is True
    assert result.reason == REASON_THRESHOLD_WITH_OVERLAP
    assert result.fallback_answer is None


def test_stopwords_alone_cannot_satisfy_the_overlap_check(settings):
    """"tôi có thể ... không" matches every document and must not count."""
    result = evaluate_evidence(
        question="tôi có thể là gì không",
        hits=[chunk(0.55, content="Tiền cọc là 30% tổng tiền sân.")],
        settings=settings,
    )

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_WEAK_WITHOUT_OVERLAP


def test_content_tokens_drops_stopwords_and_single_letters():
    tokens = content_tokens("Tôi có thể hủy lịch đặt sân không?")

    assert "hủy" in tokens
    assert "lịch" in tokens
    assert "tôi" not in tokens
    assert "có" not in tokens
    assert "không" not in tokens


def test_only_chunks_above_threshold_are_retained(settings):
    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?",
        hits=[chunk(0.80), chunk(0.55, chunk_id="booking:2"), chunk(0.10)],
        settings=settings,
    )

    assert [item.score for item in result.chunks] == [0.80, 0.55]
    assert all(item.score >= LEXICAL_MIN_SCORE for item in result.chunks)


def test_rejected_evidence_never_reaches_the_prompt_context(settings):
    result = evaluate_evidence(
        question="quantum entanglement superconductor",
        hits=[chunk(0.55)],
        settings=settings,
    )

    assert result.context_text == ""
    assert result.chunks == ()


def test_accepted_evidence_builds_a_numbered_context(settings):
    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?",
        hits=[chunk(0.80)],
        settings=settings,
    )

    assert "[1]" in result.context_text
    assert "Tiền cọc là 30%." in result.context_text


# --- sources come from real retrieved chunks ---------------------------------


def test_sources_are_built_only_from_retained_chunks(settings):
    retained = chunk(0.80, section="Tiền cọc là bao nhiêu")
    dropped = chunk(
        0.05,
        chunk_id="refunds:9",
        title="Hủy lịch và hoàn tiền",
        section="Chủ sân hủy lịch",
        source="docs/chatbot/refunds.md",
    )

    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?", hits=[retained, dropped], settings=settings
    )

    assert [source.section for source in result.sources] == ["Tiền cọc là bao nhiêu"]
    assert all(
        source.source == "docs/chatbot/booking.md" for source in result.sources
    )


def test_sources_are_deduplicated_and_capped(settings):
    hits = [
        chunk(0.90, chunk_id="booking:1"),
        chunk(0.89, chunk_id="booking:2"),  # same title+section
        chunk(0.88, chunk_id="a", title="A", section="a1", source="docs/chatbot/faq.md"),
        chunk(0.87, chunk_id="b", title="B", section="b1", source="docs/chatbot/faq.md"),
        chunk(0.86, chunk_id="c", title="C", section="c1", source="docs/chatbot/faq.md"),
    ]

    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?", hits=hits, settings=make_settings(max_sources=3)
    )

    assert len(result.sources) == 3
    assert len({(s.title, s.section) for s in result.sources}) == 3


def test_source_label_falls_back_to_the_title(settings):
    result = evaluate_evidence(
        question="Tiền cọc bao nhiêu?",
        hits=[chunk(0.80, section="Đặt sân và tiền cọc")],
        settings=settings,
    )

    assert result.sources[0].label == "Đặt sân và tiền cọc"


# --- retrieval over the real knowledge base ----------------------------------


def test_index_covers_the_whole_knowledge_base(index):
    assert index.chunk_count > 20
    assert index.embedding_model == "fake-lexical-embedding"


def test_business_rule_question_retrieves_real_chunks(index, settings):
    result = retrieve(
        "Ai được gửi tin nhắn trong phòng chat của kèo?",
        index=index,
        settings=settings,
    )

    assert result.has_sufficient_evidence is True
    assert result.chunks
    assert any(chunk.category == "match_chat" for chunk in result.chunks)
    assert all(chunk.source.startswith("docs/chatbot/") for chunk in result.chunks)


def test_deposit_question_retrieves_the_thirty_percent_rule(index, settings):
    result = retrieve("Tiền cọc khi đặt sân là bao nhiêu phần trăm?", index=index, settings=settings)

    assert result.has_sufficient_evidence is True
    assert any("30%" in chunk.content for chunk in result.chunks)


def test_owner_cancellation_question_retrieves_refund_knowledge(index, settings):
    result = retrieve(
        "Chủ sân hủy lịch thì tôi được hoàn bao nhiêu?", index=index, settings=settings
    )

    assert result.has_sufficient_evidence is True
    assert any("100%" in chunk.content for chunk in result.chunks)


def test_retrieved_sources_match_the_retrieved_chunks(index, settings):
    result = retrieve(
        "Tôi rút khỏi kèo thì có được hoàn tiền không?", index=index, settings=settings
    )

    assert result.sources
    retrieved = {(chunk.title, chunk.section) for chunk in result.chunks}
    for source in result.sources:
        assert (source.title, source.section) in retrieved
        assert source.source.startswith("docs/chatbot/")
        assert source.source_revision


def test_unrelated_question_still_produces_hits_but_no_evidence(index, settings):
    """Exactly the failure mode the gate exists for."""
    question = "Công thức nấu phở bò gia truyền Hà Nội"

    raw_hits = index.search(question, top_k=settings.retrieval_top_k)
    result = retrieve(question, index=index, settings=settings)

    assert raw_hits, "the vector store returns neighbours regardless of relevance"
    assert raw_hits[0].score > 0.0
    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_BELOW_THRESHOLD
    assert result.sources == ()
    assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER


def test_off_topic_question_falls_back(index, settings):
    result = retrieve("bitcoin ethereum blockchain", index=index, settings=settings)

    assert result.has_sufficient_evidence is False
    assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert result.context_text == ""


def test_fallback_text_is_exactly_the_agreed_sentence():
    assert (
        INSUFFICIENT_EVIDENCE_ANSWER
        == "Tôi chưa có đủ thông tin để trả lời chính xác câu này."
    )


def test_index_is_not_rebuilt_for_every_question(settings):
    provider = LexicalEmbeddingProvider()
    built = build_knowledge_index(embedding_provider=provider, settings=settings)
    after_build = provider.embed_document_calls

    for question in ("Tiền cọc?", "Hủy lịch?", "Phòng chat?"):
        retrieve(question, index=built, settings=settings)

    assert provider.embed_document_calls == after_build
    assert provider.embed_query_calls == 3


# --- only static public knowledge is ever indexed ----------------------------


def test_the_shared_index_holds_no_user_data(index):
    stored = index.stored_documents()

    assert len(stored) == index.chunk_count
    for key, text, metadata in stored:
        assert metadata["source"].startswith("docs/chatbot/")
        assert key.split(":")[0] in metadata["source"]
        assert "@" not in text
        assert "user_id" not in metadata
        assert "booking_code" not in text


# --- provider failures degrade instead of exploding --------------------------


def test_failing_embedding_provider_cannot_build_an_index(settings):
    with pytest.raises(ChatbotProviderError):
        build_knowledge_index(
            embedding_provider=FailingEmbeddingProvider(), settings=settings
        )


def test_unexpected_sdk_error_is_wrapped_not_leaked(settings):
    with pytest.raises(ChatbotProviderError) as excinfo:
        build_knowledge_index(
            embedding_provider=ExplodingEmbeddingProvider(), settings=settings
        )

    assert "RuntimeError" in str(excinfo.value)


def test_query_time_provider_failure_is_wrapped(settings):
    """The index was built while the API was healthy; the quota runs out later."""
    broken = build_knowledge_index(
        embedding_provider=QueryFailingEmbeddingProvider(), settings=settings
    )

    assert broken.chunk_count > 0
    with pytest.raises(ChatbotProviderError):
        broken.search("Tiền cọc?", top_k=2)


def test_missing_index_falls_back_instead_of_raising(settings):
    result = retrieve("Tiền cọc bao nhiêu?", index=None, settings=settings)

    assert result.has_sufficient_evidence is False
    assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER


# --- secrets never reach an error payload ------------------------------------


def test_scrub_secrets_replaces_the_key():
    message = f"401 from https://api.example/v1?key={FAKE_KEY}"

    scrubbed = scrub_secrets(message, (FAKE_KEY,))

    assert FAKE_KEY not in scrubbed
    assert "***" in scrubbed


def test_scrub_secrets_ignores_short_values():
    assert scrub_secrets("abc happens", ("abc",)) == "abc happens"


def test_provider_error_text_never_contains_the_api_key():
    provider = GeminiEmbeddingProvider(make_settings())
    leaked = RuntimeError(f"PermissionDenied url=...?key={FAKE_KEY}")

    error = provider._provider_error("Không tạo được vector.", leaked)

    assert FAKE_KEY not in str(error)
    assert "***" in str(error)


def test_settings_repr_does_not_expose_the_key():
    assert FAKE_KEY not in repr(make_settings())


def test_unavailable_reason_names_the_setting_not_its_value():
    disabled = ChatbotSettings(enabled=False, api_key=FAKE_KEY)
    keyless = ChatbotSettings(enabled=True, api_key="")

    assert "CHATBOT_ENABLED" in disabled.unavailable_reason
    assert FAKE_KEY not in disabled.unavailable_reason
    assert "GEMINI_API_KEY" in keyless.unavailable_reason


def test_providers_refuse_to_build_when_unconfigured():
    unconfigured = ChatbotSettings(enabled=True, api_key="")

    with pytest.raises(ChatbotUnavailableError):
        build_embedding_provider(unconfigured)
    with pytest.raises(ChatbotUnavailableError):
        build_chat_model_provider(unconfigured)


def test_providers_refuse_to_build_when_disabled():
    disabled = ChatbotSettings(enabled=False, api_key=FAKE_KEY)

    with pytest.raises(ChatbotUnavailableError):
        build_embedding_provider(disabled)


# --- cross-language questions (Phase 2A.5 regression) ------------------------
#
# The knowledge base is Vietnamese. The lexical-overlap stage compares the
# question's words against the retrieved chunks, which can never match for an
# English question, so applying it there rejected genuine questions: measured
# live, 4 of 7 on-topic English questions scored 0.708-0.764 (above the floor)
# and were then thrown away by the word check. The floor alone already
# separates them -- English off-topic questions topped out at 0.582.


def test_english_question_above_the_floor_is_evidence_without_word_overlap(
    settings,
):
    """The exact defect: score is fine, no shared words, must still count."""
    result = evaluate_evidence(
        question="How much deposit do I need to pay?",
        hits=[chunk(0.71, content="Tiền cọc là 30% tổng tiền sân.")],
        settings=settings,
    )

    assert result.has_sufficient_evidence is True
    assert result.reason == REASON_CROSS_LANGUAGE_THRESHOLD
    assert result.sources
    assert result.fallback_answer is None


def test_english_question_below_the_floor_is_still_rejected(settings):
    """Skipping the word check must not weaken the score floor."""
    result = evaluate_evidence(
        question="Who is the president of the United States?",
        hits=[chunk(0.30, content="Tiền cọc là 30% tổng tiền sân.")],
        settings=settings,
    )

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_BELOW_THRESHOLD
    assert result.sources == ()


def test_vietnamese_question_still_needs_word_overlap(settings):
    """The word check stays fully in force for the knowledge base's language."""
    result = evaluate_evidence(
        question="quantum entanglement superconductor lượng tử",
        hits=[chunk(0.55, content="Tiền cọc là 30% tổng tiền sân.")],
        settings=settings,
    )

    assert result.has_sufficient_evidence is False
    assert result.reason == REASON_WEAK_WITHOUT_OVERLAP


def test_cross_language_path_never_bypasses_the_strong_tier(settings):
    """A strong English match is still reported as a strong match."""
    result = evaluate_evidence(
        question="How much deposit do I need to pay?",
        hits=[chunk(0.97, content="Tiền cọc là 30% tổng tiền sân.")],
        settings=settings,
    )

    assert result.reason == REASON_STRONG_SIMILARITY


# =============================================================================
# Phase 5: "what can you do?" must not hit the generic fallback
# =============================================================================
#
# Live verification found the capability questions returning
# INSUFFICIENT_EVIDENCE_ANSWER, because the knowledge base said nothing about
# the assistant itself. The cure is a curated document, so the answer stays
# behind the evidence gate rather than being hard-coded in the widget.
#
# The lexical double is bag-of-words, so it cannot stand in for Gemini's
# semantic match on a question as function-word-heavy as "Bạn có thể làm được
# gì?" (its only content token is "thể"). These tests therefore assert the two
# things that are deterministic offline -- that the capability chunks exist and
# are retrievable, and that the pipeline answers rather than falls back once
# they are retrieved. The live scores are pinned in
# tests/unit/test_chatbot_live_calibration.py.


def assistant_chunks(index):
    return [
        (text, metadata)
        for _, text, metadata in index.stored_documents()
        if metadata.get("doc_slug") == "assistant"
    ]


def test_the_index_carries_the_assistant_capability_chunks(index):
    stored = assistant_chunks(index)

    assert stored, "the assistant document must be indexed"
    joined = "\n".join(text for text, _ in stored)
    assert "chỉ đọc dữ liệu" in joined


@pytest.mark.parametrize(
    "question",
    [
        "Trợ lý ảo làm được những gì?",
        "Trợ lý ảo này giúp được gì cho tôi?",
        "Trợ lý ảo hỗ trợ những nội dung nào?",
    ],
)
def test_a_capability_question_retrieves_the_assistant_document(
    index, settings, question
):
    result = retrieve(question, index=index, settings=settings)

    assert result.has_sufficient_evidence, result.reason
    assert result.fallback_answer is None
    assert any(chunk.doc_slug == "assistant" for chunk in result.chunks)


def test_a_capability_question_does_not_return_the_generic_fallback(
    index, settings
):
    """The regression itself: evidence exists, so no fallback."""
    result = retrieve("Trợ lý ảo làm được những gì?", index=index, settings=settings)

    assert result.fallback_answer != INSUFFICIENT_EVIDENCE_ANSWER
    assert result.context_text
    assert "INSUFFICIENT" not in result.reason.upper()


def test_the_capability_section_carries_the_read_only_boundary(index):
    """A chunk that lists abilities must also carry the limits.

    Chunking is heading-aware, so a chunk is what the model may see on its own.
    The section that answers "what can you do?" therefore has to state the
    read-only boundary itself; relying on a *different* chunk being retrieved
    alongside it would make the disclaimer a coincidence.
    """
    # Collapsed: the document is hard-wrapped, so a phrase can straddle lines.
    section = " ".join(
        next(
            text for text, metadata in assistant_chunks(index)
            if metadata.get("section") == "Bạn có thể làm được gì"
        ).split()
    )

    assert "chỉ đọc và tư vấn" in section
    for cannot in ("không đặt sân", "không hủy lịch", "không thanh toán",
                   "không hoàn tiền", "không tham gia kèo"):
        assert cannot in section, cannot


def test_the_capability_document_is_cited_by_its_public_title(index, settings):
    """The citation is a human label, never a file path."""
    result = retrieve("Trợ lý ảo làm được những gì?", index=index, settings=settings)
    assistant_sources = [
        source for source in result.sources
        if source.doc_slug == "assistant"
    ]

    assert assistant_sources
    for source in assistant_sources:
        assert source.title == "Trợ lý ảo hỗ trợ được gì"
        assert not source.label.startswith("docs/")
        assert ".md" not in source.label


def test_an_off_topic_question_is_not_rescued_by_the_capability_document(
    index, settings
):
    """Adding a document about the assistant must not widen the gate."""
    for question in ("Giá bitcoin hôm nay bao nhiêu?",
                     "Công thức nấu phở bò gia truyền Hà Nội"):
        result = retrieve(question, index=index, settings=settings)
        assert not result.has_sufficient_evidence, question
        assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER
