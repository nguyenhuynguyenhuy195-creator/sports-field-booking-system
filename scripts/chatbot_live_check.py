"""Manual live verification of the chatbot provider stack and evidence gate.

This is a DEV/OPS tool, not a test. pytest never collects it (pytest.ini pins
testpaths to tests/), and the automated suite must keep passing with no API key
and no network. Run it by hand when the knowledge base, the embedding model or
the relevance thresholds change, then copy the measured bands into
tests/unit/test_chatbot_live_calibration.py.

    .\\.venv\\Scripts\\python.exe scripts\\chatbot_live_check.py
    .\\.venv\\Scripts\\python.exe scripts\\chatbot_live_check.py --smoke-only

It reads GEMINI_API_KEY through the application's normal config loading and
never prints it. Free-tier embedding quota is 100 requests/minute; one full run
costs about 30, so back-to-back runs need the built-in backoff.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.chatbot import ChatbotSettings  # noqa: E402
from app.chatbot.errors import ChatbotProviderError  # noqa: E402
from app.chatbot.providers.gemini import (  # noqa: E402
    DOCUMENT_TASK_TYPE,
    QUERY_TASK_TYPE,
    GeminiChatModelProvider,
    GeminiEmbeddingProvider,
)
from app.chatbot.retrieval import (  # noqa: E402
    INSUFFICIENT_EVIDENCE_ANSWER,
    build_knowledge_index,
    evaluate_evidence,
)


BENCHMARK: dict[str, list[str]] = {
    "relevant": [
        "Tôi phải cọc bao nhiêu khi đặt sân?",
        "Tìm đối thủ thì mỗi bên phải cọc bao nhiêu?",
        "Nếu không tìm được đối thủ thì sân của tôi có bị hủy không?",
        "Tìm thêm người chơi có cần chủ kèo duyệt không?",
        "Khi nào tôi được vào phòng chat của kèo?",
        "Tôi rút khỏi kèo thì có được hoàn tiền không?",
        "Chủ sân hủy lịch thì tiền được xử lý thế nào?",
        "MoMo hiện có được sử dụng không?",
        "VNPAY hoạt động như thế nào trong hệ thống?",
        "Tôi có bao nhiêu phút để thanh toán sau khi đặt sân?",
        "Làm sao để đăng ký trở thành chủ sân?",
        "Tìm sân gần tôi có lưu vị trí của tôi không?",
    ],
    "ambiguous": [
        "Tôi còn thiếu bao nhiêu?",
        "Tiền còn lại là gì?",
        "Khi nào được tham gia?",
        "Trạng thái này nghĩa là gì?",
        "Có được hoàn không?",
        "Cái này bao nhiêu?",
        "Nó có hoạt động không?",
        "Tại sao bị từ chối?",
    ],
    "unrelated": [
        "Thời tiết Hà Nội hôm nay thế nào?",
        "Ai là tổng thống Mỹ?",
        "Hướng dẫn tôi học Python.",
        "Công thức tính diện tích hình tròn.",
        "Viết cho tôi một bài thơ.",
        "Giá bitcoin hôm nay bao nhiêu?",
        "Cách nấu phở bò ngon.",
    ],
}

QUOTA_BACKOFF_SECONDS = 65


def load_settings() -> ChatbotSettings:
    """Resolve real settings, forcing enabled without touching .env."""
    settings = ChatbotSettings.from_app(create_app("testing"))
    settings = dataclasses.replace(settings, enabled=True)
    if not settings.api_key:
        raise SystemExit(
            "GEMINI_API_KEY is not visible through the application config. "
            "Add it to .env; this script will not accept an inline key."
        )
    return settings


def with_backoff(call, *, tries: int = 4):
    """Retry only on the provider's per-minute quota error."""
    for attempt in range(tries):
        try:
            return call()
        except ChatbotProviderError as exc:
            if "429" not in str(exc) or attempt == tries - 1:
                raise
            print(f"    [quota] backing off {QUOTA_BACKOFF_SECONDS}s")
            time.sleep(QUOTA_BACKOFF_SECONDS)
    raise RuntimeError("unreachable")


def smoke(settings: ChatbotSettings) -> None:
    print("== chat model ==")
    chat = GeminiChatModelProvider(settings)
    started = time.perf_counter()
    answer = chat.generate(
        system_prompt="Bạn là trợ lý kiểm thử. Trả lời cực ngắn.",
        user_prompt="Trả lời đúng một từ: OK",
    )
    print(
        f"  {chat.model_name}: OK in {time.perf_counter() - started:.2f}s "
        f"-> {answer[:40]!r}"
    )

    print("== embedding model ==")
    embeddings = GeminiEmbeddingProvider(settings)
    for label, task, call in (
        ("document", DOCUMENT_TASK_TYPE,
         lambda: embeddings.embed_documents(["Tiền cọc khi đặt sân là 30%."])[0]),
        ("query", QUERY_TASK_TYPE,
         lambda: embeddings.embed_query("Tôi phải cọc bao nhiêu?")),
    ):
        started = time.perf_counter()
        vector = with_backoff(call)
        norm = math.sqrt(sum(value * value for value in vector))
        print(
            f"  {embeddings.model_name} [{task}] {label}: OK in "
            f"{time.perf_counter() - started:.2f}s dim={len(vector)} "
            f"norm={norm:.6f} finite={all(math.isfinite(v) for v in vector)}"
        )


def benchmark(settings: ChatbotSettings) -> int:
    """Return a non-zero exit code if the thresholds misclassify anything."""
    print(
        f"== benchmark (min={settings.min_relevance_score} "
        f"strong={settings.strong_relevance_score}) =="
    )
    provider = GeminiEmbeddingProvider(settings)
    index = with_backoff(
        lambda: build_knowledge_index(embedding_provider=provider, settings=settings)
    )
    print(f"  index: {index.chunk_count} chunks\n")

    bands: dict[str, list[float]] = {}
    accepted: dict[str, int] = {}
    latencies: list[float] = []

    for group, questions in BENCHMARK.items():
        bands[group] = []
        accepted[group] = 0
        print(f"-- {group} --")
        for question in questions:
            started = time.perf_counter()
            hits = with_backoff(
                lambda: index.search(question, top_k=settings.retrieval_top_k)
            )
            latencies.append(time.perf_counter() - started)
            result = evaluate_evidence(
                question=question, hits=hits, settings=settings
            )
            best = hits[0].score if hits else 0.0
            bands[group].append(best)
            accepted[group] += result.has_sufficient_evidence

            _assert_invariants(result, settings)
            verdict = "ACCEPT  " if result.has_sufficient_evidence else "FALLBACK"
            print(f"  {best:.4f} {verdict} {result.reason:32s} | {question}")
        print()

    print("== measured best-score bands (min / median / max) ==")
    for group, scores in bands.items():
        print(
            f"  {group:10s} {min(scores):.4f} / "
            f"{statistics.median(scores):.4f} / {max(scores):.4f}"
        )

    print("\n== accepted ==")
    for group, questions in BENCHMARK.items():
        print(f"  {group:10s} {accepted[group]}/{len(questions)}")
    print(
        f"\nquery latency mean={statistics.mean(latencies):.2f}s "
        f"max={max(latencies):.2f}s"
    )

    problems = []
    if accepted["unrelated"]:
        problems.append(f"{accepted['unrelated']} unrelated question(s) accepted")
    if accepted["relevant"] != len(BENCHMARK["relevant"]):
        missed = len(BENCHMARK["relevant"]) - accepted["relevant"]
        problems.append(f"{missed} relevant question(s) fell back")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 1
    print("\nOK: no unrelated question accepted, no relevant question lost.")
    return 0


def _assert_invariants(result, settings: ChatbotSettings) -> None:
    """The guarantees the gate must hold on every single question."""
    if result.has_sufficient_evidence:
        assert result.fallback_answer is None
        retrieved = {(chunk.title, chunk.section) for chunk in result.chunks}
        for source in result.sources:
            assert (source.title, source.section) in retrieved, (
                "a citation did not come from a retained chunk"
            )
        assert all(
            chunk.score >= settings.min_relevance_score for chunk in result.chunks
        )
        assert len(result.sources) <= settings.max_sources
    else:
        assert result.fallback_answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert result.context_text == ""
        assert result.sources == ()
        assert result.chunks == ()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="only verify the model identifiers; skip the benchmark",
    )
    args = parser.parse_args()

    settings = load_settings()
    print(f"chat model      : {settings.chat_model}")
    print(f"embedding model : {settings.embedding_model} @ "
          f"{settings.embedding_dimensions}d")
    print(f"GEMINI_API_KEY  : available\n")

    smoke(settings)
    if args.smoke_only:
        return 0
    print()
    return benchmark(settings)


if __name__ == "__main__":
    raise SystemExit(main())
