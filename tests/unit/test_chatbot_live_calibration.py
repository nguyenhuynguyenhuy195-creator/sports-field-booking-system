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


# =============================================================================
# Phase 5 live verification, 2026-09-13
# =============================================================================
#
# Measured with gemini-embedding-001 @768d over docs/chatbot/ including the new
# assistant.md. Same method as the bands above: best top-k score per question.

# The capability questions that used to hit the insufficient-evidence fallback
# because nothing in the knowledge base described the assistant. With
# assistant.md indexed they score 0.7093 - 0.7896 and every one clears the gate.
MEASURED_CAPABILITY_BAND = (0.7093, 0.7896)

# English on-topic questions, measured on the same run. Two of eight sit BELOW
# the configured floor, so they fall back rather than being answered in English
# -- see test_english_on_topic_questions_sit_partly_below_the_floor.
MEASURED_ENGLISH_RELEVANT_BAND = (0.6845, 0.7556)
MEASURED_ENGLISH_UNRELATED_BAND = (0.5155, 0.5475)


def test_capability_questions_clear_the_configured_floor():
    """The Phase 5 fix, pinned: "Bạn có thể làm được gì?" is answerable."""
    settings = ChatbotSettings()

    assert MEASURED_CAPABILITY_BAND[0] > settings.min_relevance_score, (
        "a capability question would fall back to the generic refusal"
    )


def test_the_capability_margin_is_recorded_as_thin():
    """Documents how little headroom the weakest capability phrasing has.

    0.7093 against a 0.70 floor is ~0.009. Raising CHATBOT_MIN_RELEVANCE_SCORE
    or rewording assistant.md can silently push these back into the fallback,
    so a change to either must be re-measured with scripts/chatbot_live_check.py
    rather than assumed safe.
    """
    settings = ChatbotSettings()
    margin = MEASURED_CAPABILITY_BAND[0] - settings.min_relevance_score

    assert 0 < margin < 0.02


def test_capability_questions_stay_below_the_strong_shortcut():
    """Most capability phrasings still face the lexical-overlap check."""
    assert MEASURED_CAPABILITY_BAND[0] < ChatbotSettings().strong_relevance_score


def test_english_off_topic_stays_far_below_the_floor():
    """Whatever happens to English support, off-topic English must not pass."""
    settings = ChatbotSettings()

    assert MEASURED_ENGLISH_UNRELATED_BAND[1] < settings.min_relevance_score
    assert settings.min_relevance_score - MEASURED_ENGLISH_UNRELATED_BAND[1] > 0.1


def test_english_on_topic_questions_sit_partly_below_the_floor():
    """A known, deliberately unfixed gap, recorded so it is not forgotten.

    The system prompt promises to answer an English question in English, but
    the evidence gate drops the weakest English phrasings first: the measured
    English on-topic band starts at 0.6845, under the 0.70 floor, so those
    questions get the fallback and never reach the model at all.

    Not changed in Phase 5: the floor is the anti-hallucination gate for every
    language, and moving it -- or giving non-Vietnamese questions a lower floor
    -- is a calibration decision that needs its own benchmark run, not a
    side-effect of a polish pass. The off-topic English band (max 0.5475) shows
    the headroom exists if that change is ever made deliberately.
    """
    settings = ChatbotSettings()

    assert MEASURED_ENGLISH_RELEVANT_BAND[0] < settings.min_relevance_score
    assert MEASURED_ENGLISH_RELEVANT_BAND[1] > settings.min_relevance_score
