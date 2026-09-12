"""Integration coverage for the Match chat room MVP."""

from datetime import time, timedelta

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    Match,
    MatchMessage,
    MatchMessageType,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    MatchSystemEventType,
    User,
    UserRole,
)
from app.services import (
    READ_ONLY_NOTICE,
    cancel_owner_booking,
    complete_finished_bookings,
    current_vietnam_datetime,
    decide_match_request,
    match_chat_is_active,
    pay_contribution_with_mock,
    process_vnpay_ipn,
    record_listing_closed,
    request_to_join_match,
    start_vnpay_payment,
    withdraw_match_request,
)
from app.services.matchmaking import (
    close_opponent_listing,
    join_waived_match_participants,
    mark_participant_joined_after_payment,
)
from tests.integration.test_bookings import (
    create_bookable_field,
    create_user,
    login,
)
from tests.integration.test_matchmaking import _create_match, _create_split_booking
from tests.integration.test_vnpay_payments import (
    VNPAY_API_URL,
    VNPAY_HASH_SECRET,
    VNPAY_PAYMENT_URL,
    VNPAY_TMN_CODE,
    build_vnpay_client,
    vnpay_callback_payload,
)


NON_READER_STATUSES = [
    MatchParticipantStatus.PENDING.value,
    MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
    MatchParticipantStatus.REJECTED.value,
    MatchParticipantStatus.EXPIRED.value,
    MatchParticipantStatus.WITHDRAWN.value,
]


def _prepare(app, *, mode=BookingMode.FIND_OPPONENT.value, suffix=""):
    owner = create_user(app, email=f"chat-owner{suffix}@example.com", role=UserRole.OWNER)
    creator = create_user(app, email=f"chat-creator{suffix}@example.com")
    player = create_user(app, email=f"chat-player{suffix}@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=mode,
        requested_players=2 if mode == BookingMode.FIND_PLAYERS.value else None,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)
    return owner, creator, player, booking_code, match_id


def _join(app, *, match_id, user_id, pay=False, phone="0901000002"):
    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, user_id),
            contact_phone=phone,
            share_contact=True,
        )
        if pay:
            pay_contribution_with_mock(
                booking_code=participant.match.booking.booking_code,
                contribution_id=participant.contribution_id,
                payer=db.session.get(User, user_id),
            )
        return participant.id


def _joined_member(app, *, suffix=""):
    """A FIND_OPPONENT match whose opponent is genuinely JOINED after paying."""
    owner, creator, player, booking_code, match_id = _prepare(app, suffix=suffix)
    _join(app, match_id=match_id, user_id=player.id, pay=True)
    with app.app_context():
        participant = db.session.scalar(
            db.select(MatchParticipant).where(MatchParticipant.match_id == match_id)
        )
        assert participant.status == MatchParticipantStatus.JOINED.value
    return owner, creator, player, booking_code, match_id


def _set_participant_status(app, *, match_id, user_id, status):
    with app.app_context():
        participant = db.session.scalar(
            db.select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == user_id,
            )
        )
        participant.status = status
        db.session.commit()


def _set_match_status(app, *, match_id, status):
    with app.app_context():
        db.session.get(Match, match_id).status = status
        db.session.commit()


def _set_booking_status(app, *, match_id, status):
    with app.app_context():
        db.session.get(Match, match_id).booking.status = status
        db.session.commit()


def _move_booking(app, *, match_id, days=0, start=None, end=None):
    with app.app_context():
        booking = db.session.get(Match, match_id).booking
        booking.booking_date = current_vietnam_datetime().date() + timedelta(days=days)
        if start is not None:
            booking.start_time = start
        if end is not None:
            booking.end_time = end
        db.session.commit()


def _add_messages(app, *, match_id, sender_id, count):
    with app.app_context():
        for index in range(1, count + 1):
            db.session.add(
                MatchMessage(
                    match_id=match_id,
                    sender_id=sender_id,
                    message_type=MatchMessageType.USER.value,
                    content=f"Tin nhắn số {index}",
                )
            )
        db.session.commit()


def _system_events(app, *, match_id):
    with app.app_context():
        return [
            (row.event_type, row.event_key)
            for row in db.session.scalars(
                db.select(MatchMessage)
                .where(
                    MatchMessage.match_id == match_id,
                    MatchMessage.message_type == MatchMessageType.SYSTEM.value,
                )
                .order_by(MatchMessage.id)
            )
        ]


# --- Authorization -----------------------------------------------------------


def test_creator_can_open_chat_from_match_creation(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.get(f"/matches/{match_id}/chat")

    assert response.status_code == 200
    assert "Phòng kèo" in response.get_data(as_text=True)


def test_joined_participant_can_open_chat(app, client):
    _, _, player, _, match_id = _joined_member(app)

    login(client, email=player.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 200
    assert client.get(f"/matches/{match_id}/messages").status_code == 200


@pytest.mark.parametrize("status", NON_READER_STATUSES)
def test_non_joined_participant_statuses_cannot_read_chat(app, client, status):
    _, _, player, _, match_id = _joined_member(app)
    _set_participant_status(app, match_id=match_id, user_id=player.id, status=status)

    login(client, email=player.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 403
    assert client.get(f"/matches/{match_id}/messages").status_code == 403
    assert (
        client.post(f"/matches/{match_id}/messages", data={"content": "Xin chào"})
        .status_code
        == 403
    )


def test_withdrawn_member_loses_access_but_history_is_kept(app, client):
    _, creator, player, _, match_id = _joined_member(app)
    login(client, email=player.email)
    assert (
        client.post(f"/matches/{match_id}/messages", data={"content": "Chào cả kèo"})
        .status_code
        == 201
    )
    client.post("/auth/logout")

    _set_participant_status(
        app,
        match_id=match_id,
        user_id=player.id,
        status=MatchParticipantStatus.WITHDRAWN.value,
    )

    login(client, email=player.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 403
    client.post("/auth/logout")

    login(client, email=creator.email)
    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)
    assert "Chào cả kèo" in page


def test_outsider_cannot_read_chat(app, client):
    _, _, _, _, match_id = _prepare(app)
    outsider = create_user(app, email="chat-outsider@example.com")

    login(client, email=outsider.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 403
    assert client.get(f"/matches/{match_id}/messages").status_code == 403


def test_admin_outside_the_match_has_no_privilege(app, client):
    _, _, _, _, match_id = _prepare(app)
    admin = create_user(app, email="chat-admin@example.com", role=UserRole.ADMIN)

    login(client, email=admin.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 403
    assert client.get(f"/matches/{match_id}/messages").status_code == 403


def test_venue_owner_outside_the_match_has_no_privilege(app, client):
    owner, _, _, _, match_id = _prepare(app)

    login(client, email=owner.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 403


def test_anonymous_user_is_redirected_to_login(app, client):
    _, _, _, _, match_id = _prepare(app)

    response = client.get(f"/matches/{match_id}/chat")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_unknown_match_returns_404(app, client):
    _, creator, _, _, _ = _prepare(app)

    login(client, email=creator.email)
    assert client.get("/matches/999999/chat").status_code == 404
    assert client.get("/matches/999999/messages").status_code == 404


def test_chat_rooms_are_isolated_between_matches(app, client):
    _, creator_a, _, _, match_a = _prepare(app, suffix="-a")
    _, creator_b, _, _, match_b = _prepare(app, suffix="-b")

    login(client, email=creator_b.email)
    client.post(f"/matches/{match_b}/messages", data={"content": "Bí mật của kèo B"})
    client.post("/auth/logout")

    login(client, email=creator_a.email)
    assert client.get(f"/matches/{match_b}/chat").status_code == 403
    payload = client.get(f"/matches/{match_a}/messages").get_json()
    assert payload["messages"] == []
    assert "Bí mật của kèo B" not in client.get(
        f"/matches/{match_a}/chat"
    ).get_data(as_text=True)


# --- Validation --------------------------------------------------------------


@pytest.mark.parametrize("content", ["", "   ", "\n\t "])
def test_empty_or_whitespace_message_is_rejected(app, client, content):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.post(f"/matches/{match_id}/messages", data={"content": content})

    assert response.status_code == 422
    assert response.get_json()["ok"] is False
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(MatchMessage.id))) == 0


def test_message_of_500_characters_is_accepted(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "a" * 500},
    )

    assert response.status_code == 201
    assert len(response.get_json()["message"]["content"]) == 500


def test_message_of_501_characters_is_rejected(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "a" * 501},
    )

    assert response.status_code == 422
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(MatchMessage.id))) == 0


def test_message_is_trimmed_before_storing(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "   Gặp nhau lúc 18h   "},
    )

    assert response.status_code == 201
    assert response.get_json()["message"]["content"] == "Gặp nhau lúc 18h"


@pytest.mark.parametrize("after_id", ["abc", "-1", "1.5"])
def test_invalid_after_id_is_rejected(app, client, after_id):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    response = client.get(f"/matches/{match_id}/messages?after_id={after_id}")

    assert response.status_code == 422
    assert response.get_json()["ok"] is False


# --- XSS / rendering safety --------------------------------------------------


def test_script_payload_is_stored_verbatim_and_escaped_in_html(app, client):
    _, creator, _, _, match_id = _prepare(app)
    payload = "<script>alert('xss')</script><b>đậm</b>"

    login(client, email=creator.email)
    created = client.post(f"/matches/{match_id}/messages", data={"content": payload})
    assert created.status_code == 201

    with app.app_context():
        stored = db.session.scalar(db.select(MatchMessage))
        assert stored.content == payload

    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)
    assert "<script>alert('xss')</script>" not in page
    assert "<b>đậm</b>" not in page
    assert "&lt;script&gt;" in page

    # The JSON API returns the raw text; the browser renders it with
    # textContent, never innerHTML.
    api = client.get(f"/matches/{match_id}/messages").get_json()
    assert api["messages"][0]["content"] == payload


def test_chat_javascript_never_uses_innerhtml_for_message_data():
    with open("app/static/js/match-chat.js", encoding="utf-8") as handle:
        source = handle.read()
    assert "innerHTML" not in source
    assert "textContent" in source


# --- Loading / polling -------------------------------------------------------


def test_initial_load_returns_latest_50_oldest_first(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _add_messages(app, match_id=match_id, sender_id=creator.id, count=60)

    login(client, email=creator.email)
    payload = client.get(f"/matches/{match_id}/messages").get_json()

    assert len(payload["messages"]) == 50
    assert payload["messages"][0]["content"] == "Tin nhắn số 11"
    assert payload["messages"][-1]["content"] == "Tin nhắn số 60"
    ids = [item["id"] for item in payload["messages"]]
    assert ids == sorted(ids)
    assert payload["last_id"] == ids[-1]

    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)
    assert "Tin nhắn số 11" in page
    assert "Tin nhắn số 10" not in page
    assert page.index("Tin nhắn số 11") < page.index("Tin nhắn số 60")


def test_after_id_returns_only_newer_messages_without_duplicates(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _add_messages(app, match_id=match_id, sender_id=creator.id, count=3)

    login(client, email=creator.email)
    first = client.get(f"/matches/{match_id}/messages").get_json()
    last_id = first["last_id"]

    assert client.get(
        f"/matches/{match_id}/messages?after_id={last_id}"
    ).get_json()["messages"] == []

    sent = client.post(f"/matches/{match_id}/messages", data={"content": "Tin mới"})
    new_id = sent.get_json()["message"]["id"]

    polled = client.get(f"/matches/{match_id}/messages?after_id={last_id}").get_json()
    assert [item["id"] for item in polled["messages"]] == [new_id]
    assert polled["last_id"] == new_id
    assert client.get(
        f"/matches/{match_id}/messages?after_id={new_id}"
    ).get_json()["messages"] == []


def test_payload_shape_for_user_and_system_messages(app, client):
    _, creator, player, _, match_id = _joined_member(app)

    login(client, email=creator.email)
    client.post(f"/matches/{match_id}/messages", data={"content": "Chủ kèo nói"})
    client.post("/auth/logout")
    login(client, email=player.email)
    client.post(f"/matches/{match_id}/messages", data={"content": "Thành viên nói"})

    messages = client.get(f"/matches/{match_id}/messages").get_json()["messages"]
    by_content = {item["content"]: item for item in messages}

    assert by_content["Chủ kèo nói"]["sender_role"] == "Chủ kèo"
    assert by_content["Chủ kèo nói"]["type"] == "USER"
    assert by_content["Thành viên nói"]["sender_role"] == "Thành viên"

    system = [item for item in messages if item["type"] == "SYSTEM"]
    assert system, "joining should have recorded a system event"
    assert system[0]["sender_name"] == "Hệ thống"
    assert system[0]["sender_role"] is None
    assert system[0]["event_type"] == MatchSystemEventType.PARTICIPANT_JOINED.value


def test_chat_payload_never_exposes_contact_details(app, client):
    _, creator, player, _, match_id = _joined_member(app)

    login(client, email=creator.email)
    client.post(f"/matches/{match_id}/messages", data={"content": "Hẹn gặp"})
    body = client.get(f"/matches/{match_id}/messages").get_data(as_text=True)
    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)

    for marker in ("0901000001", "0901000002", "contact_phone", "Zalo"):
        assert marker not in body
    assert "0901000002" not in page


def test_server_rendered_and_polled_messages_share_one_shape(app, client):
    _, creator, _, _, match_id = _joined_member(app)

    login(client, email=creator.email)
    client.post(f"/matches/{match_id}/messages", data={"content": "Đồng bộ"})

    api = client.get(f"/matches/{match_id}/messages").get_json()["messages"]
    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)
    for item in api:
        assert item["created_at"] in page
        assert f'data-message-id="{item["id"]}"' in page


# --- Active / read-only ------------------------------------------------------


def test_full_and_confirmed_rooms_still_accept_messages(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    for status in (MatchStatus.FULL.value, MatchStatus.CONFIRMED.value):
        _set_match_status(app, match_id=match_id, status=status)
        response = client.post(
            f"/matches/{match_id}/messages",
            data={"content": f"Gửi khi {status}"},
        )
        assert response.status_code == 201


def test_room_is_active_after_start_time_until_end_time(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _move_booking(
        app,
        match_id=match_id,
        days=0,
        start=time(0, 0),
        end=time(23, 59, 59),
    )

    login(client, email=creator.email)
    response = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "Đang diễn ra vẫn nhắn được"},
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "status",
    [MatchStatus.CANCELLED.value, MatchStatus.COMPLETED.value],
)
def test_cancelled_or_completed_match_is_read_only(app, client, status):
    _, creator, _, _, match_id = _prepare(app)
    _set_match_status(app, match_id=match_id, status=status)

    login(client, email=creator.email)
    page = client.get(f"/matches/{match_id}/chat")
    posted = client.post(f"/matches/{match_id}/messages", data={"content": "Còn gửi?"})

    assert page.status_code == 200
    assert "data-chat-readonly" in page.get_data(as_text=True)
    assert posted.status_code == 409
    assert posted.get_json()["ok"] is False


def test_cancelled_booking_makes_the_room_read_only(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _set_booking_status(app, match_id=match_id, status=BookingStatus.CANCELLED.value)

    login(client, email=creator.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 200
    assert (
        client.post(f"/matches/{match_id}/messages", data={"content": "x"}).status_code
        == 409
    )


def test_room_is_read_only_after_booking_end_time(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _move_booking(app, match_id=match_id, days=-1)

    login(client, email=creator.email)
    assert client.get(f"/matches/{match_id}/chat").status_code == 200
    assert (
        client.post(f"/matches/{match_id}/messages", data={"content": "x"}).status_code
        == 409
    )


def test_active_predicate_does_not_use_booking_start_time(app):
    """Regression guard: match_accepts_actions() closes at start_time; the chat
    room must stay open until end_time."""
    _, _, _, _, match_id = _prepare(app)
    with app.app_context():
        match = db.session.get(Match, match_id)
        booking = match.booking
        booking.booking_date = current_vietnam_datetime().date()
        booking.start_time = time(8, 0)
        booking.end_time = time(22, 0)
        db.session.commit()

        just_after_start = current_vietnam_datetime().replace(
            year=booking.booking_date.year,
            month=booking.booking_date.month,
            day=booking.booking_date.day,
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )
        just_after_end = just_after_start.replace(hour=22, minute=30)

        assert match_chat_is_active(match, now=just_after_start) is True
        assert match_chat_is_active(match, now=just_after_end) is False


# --- Entry points ------------------------------------------------------------


def test_entry_button_is_shown_only_to_members(app, client):
    _, creator, player, _, match_id = _joined_member(app)
    outsider = create_user(app, email="chat-entry-outsider@example.com")
    chat_url = f"/matches/{match_id}/chat"

    login(client, email=creator.email)
    assert chat_url in client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert chat_url in client.get("/matches/mine").get_data(as_text=True)
    client.post("/auth/logout")

    login(client, email=player.email)
    assert chat_url in client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert chat_url in client.get("/matches/mine").get_data(as_text=True)
    client.post("/auth/logout")

    login(client, email=outsider.email)
    assert chat_url not in client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert chat_url not in client.get("/matches/mine").get_data(as_text=True)
# --- System events -----------------------------------------------------------


def test_accepted_find_players_join_records_one_joined_event(app):
    _, creator, player, _, match_id = _prepare(
        app, mode=BookingMode.FIND_PLAYERS.value
    )
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        decide_match_request(
            match_id=match_id,
            participant_id=participant_id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
        assert (
            db.session.get(MatchParticipant, participant_id).status
            == MatchParticipantStatus.JOINED.value
        )

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.PARTICIPANT_JOINED.value,
            f"participant_joined:{participant_id}",
        )
    ]


def test_join_after_payment_records_one_joined_event(app):
    _, _, player, _, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id, pay=True)

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.PARTICIPANT_JOINED.value,
            f"participant_joined:{participant_id}",
        )
    ]


def test_replacement_opponent_joining_without_payment_records_joined_event(app):
    """The brand-new request reaches the join helper before the caller adds it
    to the session, so this proves the event still gets a complete key."""
    _, _, first_opponent, _, match_id = _prepare(app)
    replacement = create_user(app, email="chat-replacement@example.com")
    _join(app, match_id=match_id, user_id=first_opponent.id, pay=True)

    with app.app_context():
        withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, first_opponent.id),
        )
    replacement_id = _join(app, match_id=match_id, user_id=replacement.id)

    with app.app_context():
        participant = db.session.get(MatchParticipant, replacement_id)
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert participant.contribution_id is None

    events = _system_events(app, match_id=match_id)
    assert (
        MatchSystemEventType.PARTICIPANT_JOINED.value,
        f"participant_joined:{replacement_id}",
    ) in events
    assert all(key.split(":")[-1] != "None" for _, key in events)


def test_waived_join_records_joined_event(app):
    """The third JOINED site: the outstanding obligation was covered for the
    participant, so join_waived_match_participants() promotes it without any
    payment of its own."""
    _, _, player, _, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        assert participant.status == (
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
        contribution = participant.contribution
        contribution.status = ContributionStatus.WAIVED.value
        db.session.flush()

        joined = join_waived_match_participants(
            booking_id=contribution.booking_id,
            joined_at=current_vietnam_datetime(),
        )
        db.session.commit()

        assert joined == 1
        assert (
            db.session.get(MatchParticipant, participant_id).status
            == MatchParticipantStatus.JOINED.value
        )

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.PARTICIPANT_JOINED.value,
            f"participant_joined:{participant_id}",
        )
    ]


def test_withdrawal_records_event_only_when_prior_status_was_joined(app):
    _, _, player, _, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id, pay=True)

    with app.app_context():
        withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, player.id),
        )

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.PARTICIPANT_JOINED.value,
            f"participant_joined:{participant_id}",
        ),
        (
            MatchSystemEventType.PARTICIPANT_WITHDRAWN.value,
            f"participant_withdrawn:{participant_id}",
        ),
    ]


def test_withdrawal_before_joining_records_no_event(app):
    _, _, player, _, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        assert participant.status == (
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
        withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, player.id),
        )
        assert (
            db.session.get(MatchParticipant, participant_id).status
            == MatchParticipantStatus.WITHDRAWN.value
        )

    assert _system_events(app, match_id=match_id) == []


def test_closing_the_opponent_listing_records_listing_closed(app):
    _, creator, _, _, match_id = _prepare(app)

    with app.app_context():
        close_opponent_listing(
            match_id=match_id,
            creator=db.session.get(User, creator.id),
        )

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.LISTING_CLOSED.value,
            f"listing_closed:{match_id}",
        )
    ]


def test_owner_cancellation_records_exactly_one_cancellation_event(app):
    owner, _, player, booking_code, match_id = _prepare(app)
    _join(app, match_id=match_id, user_id=player.id, pay=True)

    with app.app_context():
        cancel_owner_booking(
            booking_code=booking_code,
            owner=db.session.get(User, owner.id),
            reason="Sân ngập nước đột xuất.",
        )

    cancellations = [
        key
        for event_type, key in _system_events(app, match_id=match_id)
        if event_type == MatchSystemEventType.MATCH_CANCELLED.value
    ]
    assert cancellations == [f"match_cancelled:{match_id}"]


def test_completion_job_records_one_event_even_when_run_twice(app):
    _, _, player, _, match_id = _prepare(app)
    _join(app, match_id=match_id, user_id=player.id, pay=True)
    _move_booking(app, match_id=match_id, days=-1)

    with app.app_context():
        assert complete_finished_bookings() == 1
        assert db.session.get(Match, match_id).status == MatchStatus.COMPLETED.value
    with app.app_context():
        assert complete_finished_bookings() == 0

    completions = [
        key
        for event_type, key in _system_events(app, match_id=match_id)
        if event_type == MatchSystemEventType.MATCH_COMPLETED.value
    ]
    assert completions == [f"match_completed:{match_id}"]


def test_repeated_join_helper_call_does_not_duplicate_the_event(app):
    """The transition guard itself: a retried callback finds the participant
    already JOINED and mutates nothing, so no second event is appended."""
    _, _, player, _, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id, pay=True)

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        contribution = participant.contribution
        assert (
            mark_participant_joined_after_payment(
                contribution,
                paid_at=current_vietnam_datetime(),
            )
            is None
        )
        db.session.commit()

    joined = [
        key
        for event_type, key in _system_events(app, match_id=match_id)
        if event_type == MatchSystemEventType.PARTICIPANT_JOINED.value
    ]
    assert joined == [f"participant_joined:{participant_id}"]


def test_duplicate_system_event_is_a_noop_and_the_transition_still_commits(app):
    _, _, _, _, match_id = _prepare(app)

    with app.app_context():
        match = db.session.get(Match, match_id)
        assert record_listing_closed(match) is not None
        assert record_listing_closed(match) is None
        match.status = MatchStatus.CANCELLED.value
        db.session.commit()

    assert len(_system_events(app, match_id=match_id)) == 1
    with app.app_context():
        match = db.session.get(Match, match_id)
        assert match.status == MatchStatus.CANCELLED.value
        assert record_listing_closed(match) is None
        db.session.commit()

    assert len(_system_events(app, match_id=match_id)) == 1


def test_system_event_rolls_back_with_its_business_transition(app):
    _, _, _, _, match_id = _prepare(app)

    with app.app_context():
        match = db.session.get(Match, match_id)
        match.status = MatchStatus.CANCELLED.value
        record_listing_closed(match)
        db.session.rollback()

    assert _system_events(app, match_id=match_id) == []
    with app.app_context():
        assert db.session.get(Match, match_id).status == MatchStatus.OPEN.value


def test_payment_and_refund_activity_records_no_extra_system_events(app):
    owner, _, player, booking_code, match_id = _prepare(app)
    _join(app, match_id=match_id, user_id=player.id, pay=True)

    with app.app_context():
        cancel_owner_booking(
            booking_code=booking_code,
            owner=db.session.get(User, owner.id),
            reason="Sân ngập nước đột xuất.",
        )

    recorded = {event_type for event_type, _ in _system_events(app, match_id=match_id)}
    assert recorded <= {
        MatchSystemEventType.PARTICIPANT_JOINED.value,
        MatchSystemEventType.MATCH_CANCELLED.value,
    }
    for unwanted in ("payment", "refund", "contribution", "top_up", "rejected"):
        assert not any(unwanted in event_type for event_type in recorded)


def test_rejected_request_records_no_system_event(app):
    _, creator, player, _, match_id = _prepare(
        app, mode=BookingMode.FIND_PLAYERS.value
    )
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        decide_match_request(
            match_id=match_id,
            participant_id=participant_id,
            creator=db.session.get(User, creator.id),
            accept=False,
        )

    assert _system_events(app, match_id=match_id) == []


@pytest.fixture()
def vnpay_enabled(app):
    app.config.update(
        VNPAY_ENABLED=True,
        VNPAY_TMN_CODE=VNPAY_TMN_CODE,
        VNPAY_HASH_SECRET=VNPAY_HASH_SECRET,
        VNPAY_PAYMENT_URL=VNPAY_PAYMENT_URL,
        VNPAY_API_URL=VNPAY_API_URL,
        VNPAY_TIMEOUT_SECONDS=30,
        VNPAY_RETURN_URL="https://example.test/payments/vnpay/return",
    )
    return app


def test_vnpay_ipn_retry_records_exactly_one_joined_event(app, vnpay_enabled):
    _, _, player, booking_code, match_id = _prepare(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)
    vnpay = build_vnpay_client()

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        checkout = start_vnpay_payment(
            booking_code=booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, player.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        first = process_vnpay_ipn(payload, client=vnpay)
        second = process_vnpay_ipn(payload, client=vnpay)

        assert first.rsp_code == "00"
        assert second.rsp_code == "02"
        assert (
            db.session.get(MatchParticipant, participant_id).status
            == MatchParticipantStatus.JOINED.value
        )

    assert _system_events(app, match_id=match_id) == [
        (
            MatchSystemEventType.PARTICIPANT_JOINED.value,
            f"participant_joined:{participant_id}",
        )
    ]
# --- Finding 1: live read-only contract --------------------------------------


def _js_source():
    with open("app/static/js/match-chat.js", encoding="utf-8") as handle:
        return handle.read()


def _js_block(source, start_marker, end_marker):
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


def test_messages_payload_carries_send_state_and_server_notice(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    active = client.get(f"/matches/{match_id}/messages").get_json()
    assert active["can_send"] is True
    assert active["read_only_notice"] == READ_ONLY_NOTICE

    _set_match_status(app, match_id=match_id, status=MatchStatus.COMPLETED.value)
    closed = client.get(f"/matches/{match_id}/messages").get_json()
    assert closed["can_send"] is False
    assert closed["read_only_notice"] == READ_ONLY_NOTICE


def test_send_into_a_room_that_just_closed_returns_the_read_only_contract(app, client):
    _, creator, _, _, match_id = _prepare(app)
    login(client, email=creator.email)
    _set_booking_status(app, match_id=match_id, status=BookingStatus.CANCELLED.value)

    response = client.post(f"/matches/{match_id}/messages", data={"content": "x"})
    payload = response.get_json()

    assert response.status_code == 409
    assert payload["ok"] is False
    assert payload["can_send"] is False
    assert payload["read_only_notice"] == READ_ONLY_NOTICE


def test_active_room_ships_the_read_only_notice_hidden(app, client):
    _, creator, _, _, match_id = _prepare(app)

    login(client, email=creator.email)
    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)

    assert "data-chat-form" in page
    assert "match-chat-readonly mb-0 d-none" in page
    assert READ_ONLY_NOTICE in page


def test_closed_room_shows_the_notice_and_drops_the_composer(app, client):
    _, creator, _, _, match_id = _prepare(app)
    _set_match_status(app, match_id=match_id, status=MatchStatus.CANCELLED.value)

    login(client, email=creator.email)
    page = client.get(f"/matches/{match_id}/chat").get_data(as_text=True)

    assert "data-chat-form" not in page
    assert "match-chat-readonly mb-0 d-none" not in page
    assert "data-chat-readonly" in page
    assert READ_ONLY_NOTICE in page


def test_chat_javascript_renders_only_the_server_notice_and_keeps_polling():
    source = _js_source()

    # The wording exists once, on the server.
    assert READ_ONLY_NOTICE not in source
    assert "read_only_notice" in source

    read_only = _js_block(source, "const applyReadOnly", "const applySendState")
    assert "stopPolling" not in read_only
    assert "clearInterval" not in read_only

    # A 409 flips the UI over in place, no reload.
    assert "response.status === 409" in source
    assert "window.location.reload" not in source


# --- Finding 2: completion concurrency ---------------------------------------


def test_completion_job_locks_its_candidate_bookings(app, monkeypatch):
    """The candidate SELECT must hold an update lock, so two concurrent jobs
    cannot both decide the same booking is still completable and then race on
    the match_completed event."""
    from app.services import booking as booking_service

    calls = []
    original = booking_service.with_update_lock

    def spy(statement, entity):
        calls.append(entity)
        return original(statement, entity)

    monkeypatch.setattr(booking_service, "with_update_lock", spy)

    _, _, player, _, match_id = _prepare(app)
    _join(app, match_id=match_id, user_id=player.id, pay=True)
    _move_booking(app, match_id=match_id, days=-1)

    calls.clear()
    with app.app_context():
        assert complete_finished_bookings() == 1

    assert calls, "complete_finished_bookings() took no update lock"
    assert calls[0] is Booking


# --- Finding 3: polling cursor vs POST race ----------------------------------


def test_polling_from_the_pre_post_cursor_returns_every_message_once(app, client):
    """Server contract behind the cursor fix: polling from the cursor the page
    held BEFORE its own POST must still return the message another member sent
    in between, and each message exactly once."""
    _, creator, player, _, match_id = _joined_member(app)

    login(client, email=creator.email)
    cursor = client.get(f"/matches/{match_id}/messages").get_json()["last_id"]
    client.post("/auth/logout")

    login(client, email=player.email)
    other_id = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "Tin của thành viên khác"},
    ).get_json()["message"]["id"]
    client.post("/auth/logout")

    login(client, email=creator.email)
    own_id = client.post(
        f"/matches/{match_id}/messages",
        data={"content": "Tin của chính tôi"},
    ).get_json()["message"]["id"]

    assert cursor < other_id < own_id

    polled = client.get(
        f"/matches/{match_id}/messages?after_id={cursor}"
    ).get_json()
    ids = [item["id"] for item in polled["messages"]]

    assert ids == [other_id, own_id]
    assert ids.count(other_id) == 1
    assert ids.count(own_id) == 1
    assert polled["last_id"] == own_id


def test_chat_javascript_never_advances_the_cursor_from_a_post():
    source = _js_source()

    submit_handler = source[source.index('form.addEventListener("submit"') :]
    assert "pollAfterId" not in submit_handler

    poll_block = _js_block(source, "const poll = async", "const startPolling")
    assert "pollAfterId = nextCursor" in poll_block

    # Rendering is deduped by id, so the POST-rendered message is not appended
    # a second time when the next poll returns it.
    assert "renderedIds" in source
    assert "renderedIds.has(id)" in source
