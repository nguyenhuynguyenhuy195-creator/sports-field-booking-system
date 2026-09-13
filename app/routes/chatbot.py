"""JSON API for the chatbot. Phase 3: one endpoint, no page and no widget.

Everything the browser sends is a hint. ``page_type`` and ``resource_id`` are
passed to ``resolve_dynamic_context`` as untrusted input and that resolver --
not this route -- decides what the viewer may see. No user id, role, payer or
recipient is ever read from the request body; the viewer is always
``current_user``.

The response is a deliberately narrow projection. Dynamic context exists only
on the server, for grounding: the answer text and a short list of
backend-chosen curated sources go back, and nothing else. In particular the
resolved DTO, the prompt lines, the retrieved chunks, the prompts themselves,
retrieval scores and every payment/provider identifier stay here.

Auth is checked by hand rather than with ``@login_required`` because the login
manager has a ``login_view``, so the decorator answers an anonymous request
with a 302 to the HTML login page. An API caller needs a 401.
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.chatbot import (
    ChatbotProviderError,
    ChatbotSettings,
    ChatbotUnavailableError,
    ChatbotValidationError,
    answer_question,
    build_chat_model_provider,
    build_embedding_provider,
    get_knowledge_index,
)
from app.chatbot.context import resolve_dynamic_context
from app.chatbot.rate_limit import get_rate_limiter
from app.models import UserRole


logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# Bound the body before parsing it. MAX_CONTENT_LENGTH is sized for media
# uploads and is far too generous for a question plus eight turns of history.
DEFAULT_MAX_REQUEST_BYTES = 32 * 1024

UNAUTHENTICATED_MESSAGE = "Vui lòng đăng nhập để sử dụng trợ lý ảo."
FORBIDDEN_MESSAGE = "Tài khoản này không sử dụng được trợ lý ảo."
NOT_JSON_MESSAGE = "Yêu cầu phải ở định dạng JSON."
MALFORMED_MESSAGE = "Nội dung yêu cầu không hợp lệ."
TOO_LARGE_MESSAGE = "Nội dung yêu cầu quá lớn."
RATE_LIMITED_MESSAGE = "Bạn đang hỏi quá nhanh. Vui lòng thử lại sau giây lát."
UNAVAILABLE_MESSAGE = "Trợ lý ảo tạm thời không sẵn sàng. Vui lòng thử lại sau."


def _error(message: str, status: int, **extra):
    return jsonify(ok=False, message=message, **extra), status


@chatbot_bp.post("/query")
def query():
    settings = ChatbotSettings.from_app(current_app)

    # --- who is asking -------------------------------------------------
    if not current_user.is_authenticated:
        return _error(UNAUTHENTICATED_MESSAGE, 401)
    if current_user.role != UserRole.USER.value or not current_user.is_active:
        return _error(FORBIDDEN_MESSAGE, 403)

    # --- what they sent ------------------------------------------------
    max_bytes = int(
        current_app.config.get("CHATBOT_MAX_REQUEST_BYTES")
        or DEFAULT_MAX_REQUEST_BYTES
    )
    if (request.content_length or 0) > max_bytes:
        return _error(TOO_LARGE_MESSAGE, 413)
    if not request.is_json:
        return _error(NOT_JSON_MESSAGE, 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error(MALFORMED_MESSAGE, 400)
    # A chunked or mis-declared request can slip past content_length.
    if len(request.get_data(cache=True)) > max_bytes:
        return _error(TOO_LARGE_MESSAGE, 413)

    try:
        page_type, resource_id = _read_context(payload.get("context"))
        history = _read_history(payload.get("history"))
    except ChatbotValidationError as exc:
        return _error(str(exc), 422)

    # --- how often ------------------------------------------------------
    limiter = get_rate_limiter(
        current_app,
        limit=int(current_app.config.get("CHATBOT_RATE_LIMIT_PER_MINUTE") or 0),
        window_seconds=int(
            current_app.config.get("CHATBOT_RATE_LIMIT_WINDOW_SECONDS") or 60
        ),
    )
    decision = limiter.check(current_user.id)
    if decision.limited:
        return _error(RATE_LIMITED_MESSAGE, 429, retry_after=decision.retry_after)

    # --- answer ----------------------------------------------------------
    # The resolver is the authorization boundary. A resource the viewer may not
    # see comes back unavailable, exactly like one that does not exist, so this
    # route has no separate branch to distinguish them and cannot leak one.
    context = resolve_dynamic_context(
        viewer=current_user, page_type=page_type, resource_id=resource_id
    )

    try:
        provider = build_chat_model_provider(settings)
        index = get_knowledge_index(
            current_app,
            embedding_provider=build_embedding_provider(settings),
            settings=settings,
        )
        answer = answer_question(
            payload.get("question"),
            chat_provider=provider,
            index=index,
            settings=settings,
            history=history,
            context=context,
        )
    except ChatbotValidationError as exc:
        return _error(str(exc), 422)
    except ChatbotUnavailableError:
        # Disabled or unconfigured: an operational state, never a config dump.
        logger.warning("Trợ lý ảo chưa sẵn sàng để trả lời.")
        return _error(UNAVAILABLE_MESSAGE, 503)
    except ChatbotProviderError:
        # Already scrubbed upstream; the text still never reaches the client.
        logger.warning("Nhà cung cấp AI không phản hồi cho yêu cầu trợ lý ảo.")
        return _error(UNAVAILABLE_MESSAGE, 503)

    return jsonify(
        ok=True,
        answer=answer.answer,
        status=answer.status,
        # doc_slug, not source: the repo-relative path is an internal layout
        # detail and has no business reaching a browser.
        sources=[
            {"label": source.label, "source": source.doc_slug}
            for source in answer.sources
        ],
    )


def _read_context(raw: object) -> tuple[str, int | None]:
    """Shape the page hint. Unknown page names are allowed through.

    Only malformed *types* are rejected, because they mean a broken client. An
    unrecognised page name is not an error: the resolver simply returns no
    context, which keeps unknown names from behaving any differently than a
    resource the viewer cannot see.
    """
    if raw is None:
        return "general", None
    if not isinstance(raw, dict):
        raise ChatbotValidationError("Trường context không hợp lệ.")

    page_type = raw.get("page_type", "general")
    if page_type is None:
        page_type = "general"
    if not isinstance(page_type, str):
        raise ChatbotValidationError("Trường page_type không hợp lệ.")

    resource_id = raw.get("resource_id")
    if resource_id is not None and (
        isinstance(resource_id, bool) or not isinstance(resource_id, int)
    ):
        raise ChatbotValidationError("Trường resource_id không hợp lệ.")
    return page_type, resource_id


def _read_history(raw: object) -> list | None:
    """Only the shape is checked here; normalize_history() owns the rules."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ChatbotValidationError("Lịch sử hội thoại không hợp lệ.")
    return raw


__all__ = ["chatbot_bp"]
