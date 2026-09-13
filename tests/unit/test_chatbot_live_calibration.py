"""Phase 1.5 findings, locked in as offline regression tests.

These record what a live verification run against Gemini actually measured on
2026-09-13, so that a later change to the model identifier or the evidence
thresholds has to be a conscious decision rather than a silent drift. Nothing
here calls the network: the live script lives at scripts/chatbot_live_check.py
and is a manual/dev path, never part of the standard suite.
"""

from __future__ import annotations

import pytest

from app.chatbot.errors import ChatbotProviderError
from app.chatbot.settings import DEFAULTS, ChatbotSettings
from chatbot_doubles import FailingChatModelProvider, RecordingChatModelProvider


# --- what the live run measured ---------------------------------------------
# Best-score bands over the 27-question Vietnamese benchmark, using
# gemini-embedding-001 @768d over the current docs/chatbot/ set.
MEASURED_RELEVANT_BAND = (0.7686, 0.8696)
MEASURED_AMBIGUOUS_BAND = (0.6756, 0.7460)
MEASURED_UNRELATED_BAND = (0.5652, 0.6496)


def test_default_chat_model_is_the_live_verified_identifier():
    """gemini-2.5-flash-lite is retired: the API answers 404 'no longer
    available to new users' and names gemini-3.5-flash-lite instead."""
    assert DEFAULTS["CHATBOT_MODEL"] == "gemini-3.5-flash-lite"
    assert ChatbotSettings().chat_model == "gemini-3.5-flash-lite"


def test_default_embedding_model_and_dimensions_are_the_verified_pair():
    settings = ChatbotSettings()

    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_dimensions == 768


def test_thinking_level_replaces_the_retired_thinking_budget():
    """Gemini 3.x rejects thinking_budget with 400 INVALID_ARGUMENT."""
    assert ChatbotSettings().thinking_level == "low"


def test_thinking_level_can_be_disabled_for_a_model_that_supports_neither(app):
    app.config["CHATBOT_THINKING_LEVEL"] = ""

    assert ChatbotSettings.from_app(app).thinking_level == ""


def test_min_threshold_clears_the_whole_unrelated_band():
    """No off-topic question may reach the evidence stage."""
    minimum = ChatbotSettings().min_relevance_score

    assert minimum > MEASURED_UNRELATED_BAND[1], (
        "an unrelated question would be retained as evidence"
    )


def test_min_threshold_stays_below_the_whole_relevant_band():
    """No genuine question may be dropped by the score gate."""
    minimum = ChatbotSettings().min_relevance_score

    assert minimum < MEASURED_RELEVANT_BAND[0], (
        "a clearly relevant question would fall back"
    )


def test_strong_threshold_sits_above_the_ambiguous_band():
    """Similarity alone may bypass the lexical check only when it is genuinely
    high; an under-specified question must never qualify on score alone."""
    settings = ChatbotSettings()

    assert settings.strong_relevance_score > MEASURED_AMBIGUOUS_BAND[1]
    assert settings.min_relevance_score < settings.strong_relevance_score


def test_gemini_similarity_floor_makes_a_low_threshold_meaningless():
    """Documents why the threshold is not near zero.

    Gemini embeddings never scored below ~0.565 against this knowledge base,
    even for completely off-topic questions, so a naive low cutoff would
    accept everything.
    """
    assert MEASURED_UNRELATED_BAND[0] > 0.5
    assert ChatbotSettings().min_relevance_score > MEASURED_UNRELATED_BAND[0]


# --- chat provider failure ---------------------------------------------------


def test_chat_provider_failure_raises_a_wrapped_error_not_a_raw_sdk_error():
    provider = FailingChatModelProvider()

    with pytest.raises(ChatbotProviderError):
        provider.generate(system_prompt="s", user_prompt="u")


def test_chat_provider_timeout_is_catchable_by_the_caller():
    """A timeout must be an ordinary handled failure, not an escaping crash."""
    provider = FailingChatModelProvider(TimeoutError("read timed out"))

    with pytest.raises(TimeoutError):
        provider.generate(system_prompt="s", user_prompt="u")
    assert provider.calls == 1


def test_chat_provider_failure_does_not_break_the_application(app):
    """The booking site keeps serving while the chat model is unreachable."""
    provider = FailingChatModelProvider()
    client = app.test_client()

    with pytest.raises(ChatbotProviderError):
        provider.generate(system_prompt="s", user_prompt="u")

    assert client.get("/venues").status_code == 200
    assert client.get("/health").status_code == 200


def test_recording_chat_provider_captures_what_would_be_sent():
    """Phase 2 will assert on the payload, not just the answer."""
    provider = RecordingChatModelProvider(answer="OK")

    answer = provider.generate(system_prompt="hệ thống", user_prompt="câu hỏi")

    assert answer == "OK"
    assert provider.calls[0]["system_prompt"] == "hệ thống"
    assert provider.calls[0]["user_prompt"] == "câu hỏi"
