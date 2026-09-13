"""Phase 4: the chatbot widget in the Player UI.

Two kinds of check live here. The rendering tests drive real pages and assert
what does and does not reach the HTML — who sees the widget, what page context
it carries, and that no private figure is smuggled into a data attribute. The
static tests read chatbot-widget.js and assert the properties that cannot be
exercised without a browser (sessionStorage over localStorage, textContent over
innerHTML, the IME guard), since this phase deliberately installs no JS test
runner.
"""

from __future__ import annotations

import re
from datetime import time
from pathlib import Path

import pytest

from app.extensions import db
from app.models import BookingMode, User, UserRole
from app.services import (
    create_booking,
    create_match,
    pay_contribution_with_mock,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)


WIDGET_MARKER = "data-chatbot-widget"
JS_SOURCE = Path("app/static/js/chatbot-widget.js").read_text(encoding="utf-8")
CSS_SOURCE = Path("app/static/css/chatbot.css").read_text(encoding="utf-8")


@pytest.fixture()
def world(app):
    owner = create_user(app, email="ui-owner@example.com", role=UserRole.OWNER)
    admin = create_user(app, email="ui-admin@example.com", role=UserRole.ADMIN)
    player = create_user(app, email="ui-player@example.com")
    venue_id, field_id = create_bookable_field(app, owner_id=owner.id)

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        booking_id, booking_code = booking.id, booking.booking_code
        own = next(i for i in booking.contributions if i.user_id == player.id)
        pay_contribution_with_mock(
            booking_code=booking_code, contribution_id=own.id,
            payer=db.session.get(User, player.id),
        )
        match_id = create_match(
            booking_code=booking_code,
            creator=db.session.get(User, player.id),
            title="Kèo kiểm thử giao diện",
            contact_phone="0901000001",
            share_contact=True,
        ).id

    app.config["CHATBOT_ENABLED"] = True
    return {
        "owner": owner, "admin": admin, "player": player,
        "venue_id": venue_id, "booking_id": booking_id,
        "booking_code": booking_code, "match_id": match_id,
    }


def html_of(client, path) -> str:
    response = client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code}"
    return response.get_data(as_text=True)


def widget_attr(html: str, attribute: str) -> str | None:
    block = re.search(r"<div class=\"chatbot-widget\"(.*?)>", html, re.DOTALL)
    assert block, "widget root not found"
    found = re.search(rf'{attribute}="([^"]*)"', block.group(1))
    return found.group(1) if found else None


# --- 1-5. visibility ---------------------------------------------------------


def test_active_user_sees_the_widget(app, client, world):
    login(client, email=world["player"].email)

    assert WIDGET_MARKER in html_of(client, "/")


def test_guest_does_not_see_the_widget(app, client, world):
    assert WIDGET_MARKER not in html_of(client, "/")
    assert "chatbot-widget.js" not in html_of(client, "/")


@pytest.mark.parametrize("who", ["owner", "admin"])
def test_owner_and_admin_do_not_see_the_widget(app, client, world, who):
    login(client, email=world[who].email)

    html = html_of(client, "/")
    assert WIDGET_MARKER not in html
    assert "chatbot.css" not in html


def test_widget_is_absent_when_the_chatbot_is_disabled(app, client, world):
    app.config["CHATBOT_ENABLED"] = False
    login(client, email=world["player"].email)

    html = html_of(client, "/")
    assert WIDGET_MARKER not in html
    assert "chatbot-widget.js" not in html
    assert "chatbot.css" not in html


# --- 6-9. page context -------------------------------------------------------


def test_general_page_sends_general_context(app, client, world):
    login(client, email=world["player"].email)

    html = html_of(client, "/")

    assert widget_attr(html, "data-chatbot-page-type") == "general"
    assert widget_attr(html, "data-chatbot-resource-id") == ""


def test_booking_detail_sends_the_numeric_booking_id(app, client, world):
    """booking_code is in the URL; the API needs the integer primary key."""
    login(client, email=world["player"].email)

    html = html_of(client, f"/bookings/{world['booking_code']}")

    assert widget_attr(html, "data-chatbot-page-type") == "booking_detail"
    assert widget_attr(html, "data-chatbot-resource-id") == str(world["booking_id"])
    assert widget_attr(html, "data-chatbot-resource-id") != world["booking_code"]


def test_match_detail_sends_the_match_id(app, client, world):
    login(client, email=world["player"].email)

    html = html_of(client, f"/matches/{world['match_id']}")

    assert widget_attr(html, "data-chatbot-page-type") == "match_detail"
    assert widget_attr(html, "data-chatbot-resource-id") == str(world["match_id"])


def test_venue_detail_sends_the_venue_id(app, client, world):
    login(client, email=world["player"].email)

    html = html_of(client, f"/venues/{world['venue_id']}")

    assert widget_attr(html, "data-chatbot-page-type") == "venue_detail"
    assert widget_attr(html, "data-chatbot-resource-id") == str(world["venue_id"])


def test_other_player_pages_stay_general(app, client, world):
    login(client, email=world["player"].email)

    for path in ("/venues", "/matches", "/bookings"):
        html = html_of(client, path)
        assert widget_attr(html, "data-chatbot-page-type") == "general", path


# --- 10-11. endpoint and CSRF ------------------------------------------------


def test_widget_points_at_the_real_query_endpoint(app, client, world):
    login(client, email=world["player"].email)

    html = html_of(client, "/")

    assert widget_attr(html, "data-chatbot-query-url") == "/chatbot/query"


def test_widget_carries_a_csrf_token(app, client, world):
    login(client, email=world["player"].email)

    token = widget_attr(html_of(client, "/"), "data-chatbot-csrf")

    assert token and len(token) > 20


def test_javascript_sends_the_csrf_header(app):
    assert '"X-CSRFToken": csrfToken' in JS_SOURCE
    assert '"Content-Type": "application/json"' in JS_SOURCE
    assert "csrf_exempt" not in JS_SOURCE


# --- 12. nothing private in the markup ---------------------------------------


def test_widget_markup_carries_no_private_data(app, client, world):
    login(client, email=world["player"].email)
    html = html_of(client, f"/bookings/{world['booking_code']}")
    block = re.search(r"<div class=\"chatbot-widget\".*?</div>\s*$", html, re.DOTALL)
    widget_html = html[html.index('<div class="chatbot-widget"'):]

    for forbidden in (
        "deposit_remaining", "balance_due_at_venue", "current_user_paid",
        "current_user_payments", "current_user_refunds", "order_id",
        "checkout_url", "provider_trans_id", "GEMINI", "api_key",
        world["booking_code"],
    ):
        assert forbidden not in widget_html, forbidden


def test_the_api_key_never_reaches_any_page(app, client, world):
    app.config["GEMINI_API_KEY"] = "ui-secret-key-0123456789"
    login(client, email=world["player"].email)

    for path in ("/", f"/bookings/{world['booking_code']}",
                 f"/matches/{world['match_id']}",
                 f"/venues/{world['venue_id']}"):
        assert "ui-secret-key-0123456789" not in html_of(client, path), path
    assert "GEMINI_API_KEY" not in JS_SOURCE


# --- 13. assets --------------------------------------------------------------


def test_chatbot_assets_are_linked_and_served(app, client, world):
    login(client, email=world["player"].email)
    html = html_of(client, "/")

    assert "css/chatbot.css" in html
    assert "js/chatbot-widget.js" in html
    assert client.get("/static/css/chatbot.css").status_code == 200
    assert client.get("/static/js/chatbot-widget.js").status_code == 200


# --- 14. existing layouts are untouched --------------------------------------


def test_owner_booking_view_has_no_widget(app, client, world):
    """The owner view extends owner/base.html, which never includes it."""
    login(client, email=world["owner"].email)

    html = html_of(client, f"/owner/bookings/{world['booking_code']}")

    assert WIDGET_MARKER not in html
    assert "chatbot.css" not in html


def test_widget_is_fixed_and_below_bootstrap_modals():
    """It must overlay, never reflow — and a modal must still cover it."""
    root = CSS_SOURCE[CSS_SOURCE.index(".chatbot-widget {"):]
    root = root[: root.index("}")]

    assert "position: fixed" in root
    z_index = int(re.search(r"z-index:\s*(\d+)", root).group(1))
    # Bootstrap: modal-backdrop 1050, modal 1055.
    assert 1030 <= z_index < 1050


def test_chatbot_css_only_targets_its_own_namespace():
    """No bare element or Bootstrap selector may leak onto existing pages."""
    without_comments = re.sub(r"/\*.*?\*/", "", CSS_SOURCE, flags=re.DOTALL)
    offenders = []
    for block in re.finditer(r"([^{}]+)\{", without_comments):
        selector = block.group(1).strip()
        if not selector or selector.startswith("@") or ":root" in selector:
            continue
        for part in selector.split(","):
            part = part.strip()
            if not part:
                continue
            if ".chatbot-" not in part:
                offenders.append(part)

    assert offenders == [], offenders


# --- static review of the browser behaviour ----------------------------------


def test_history_uses_session_storage_only():
    assert "sessionStorage" in JS_SOURCE
    assert "localStorage" not in JS_SOURCE


def test_history_is_capped_at_sixteen_messages():
    assert "MAX_MESSAGES = 16" in JS_SOURCE
    assert "slice(-MAX_MESSAGES)" in JS_SOURCE


def test_storage_key_is_scoped_by_user_page_and_resource():
    assert "${STORAGE_PREFIX}${userId}:${pageType}:${resourceId}" in JS_SOURCE
    # A different account in the same tab drops the previous conversations.
    assert "dropOtherAccounts" in JS_SOURCE


def test_rendering_never_uses_inner_html():
    """Checked against code, not comments.

    The file mentions innerHTML in prose to explain why it is avoided, so the
    comments are stripped first — otherwise this test would fail on its own
    documentation and, worse, could be "fixed" by deleting the explanation.
    """
    code = re.sub(r"//.*", "", JS_SOURCE)

    assert "innerHTML" not in code
    assert "insertAdjacentHTML" not in code
    assert "document.write" not in code
    assert "outerHTML" not in code
    assert "textContent" in code


def test_only_the_source_label_is_rendered():
    assert "entry.textContent = source.label" in JS_SOURCE
    assert "textContent = source.source" not in JS_SOURCE
    assert "Xem nguồn" in JS_SOURCE


def test_enter_sends_and_shift_enter_inserts_a_newline():
    assert 'event.key !== "Enter" || event.shiftKey' in JS_SOURCE
    assert "requestSubmit" in JS_SOURCE


def test_ime_composition_does_not_submit():
    assert "event.isComposing" in JS_SOURCE
    assert "keyCode === 229" in JS_SOURCE


def test_duplicate_submits_are_blocked_while_a_request_is_open():
    assert "if (!trimmed || pending)" in JS_SOURCE
    assert "setPending(true)" in JS_SOURCE
    assert "sendButton.disabled = active" in JS_SOURCE


def test_failed_turns_are_not_remembered():
    """An error bubble must never become context for the next question."""
    error_branch = JS_SOURCE[JS_SOURCE.index("if (!response.ok"):]
    error_branch = error_branch[: error_branch.index("renderMessage(\"assistant\", payload.answer")]

    assert "history.push" not in error_branch


def test_clearing_is_local_only():
    clear = JS_SOURCE[JS_SOURCE.index("clearButton.addEventListener"):]
    clear = clear[: clear.index("});")]

    assert "clearHistory()" in clear
    assert "fetch(" not in clear


def test_accessibility_attributes_are_present(app, client, world):
    login(client, email=world["player"].email)
    html = html_of(client, "/")

    assert 'aria-expanded="false"' in html
    assert 'aria-controls="chatbotPanel"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="false"' in html
    assert 'aria-label="Đóng trợ lý"' in html
    assert "aria-live=\"polite\"" in html
    assert "Escape" in JS_SOURCE


def test_composer_limits_match_the_api(app, client, world):
    login(client, email=world["player"].email)
    html = html_of(client, "/")

    assert 'maxlength="2000"' in html
    assert "Nhập câu hỏi của bạn..." in html


def test_suggestions_never_propose_an_action(app, client, world):
    login(client, email=world["player"].email)

    for path in ("/", f"/bookings/{world['booking_code']}",
                 f"/matches/{world['match_id']}",
                 f"/venues/{world['venue_id']}"):
        html = html_of(client, path)
        widget_html = html[html.index('<div class="chatbot-widget"'):]
        for action in ("Hủy lịch giúp", "Thanh toán giúp", "Đặt sân giúp",
                       "hủy giúp tôi"):
            assert action not in widget_html, f"{action} on {path}"
