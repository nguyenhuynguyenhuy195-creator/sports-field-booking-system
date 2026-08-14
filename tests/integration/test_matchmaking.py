from datetime import datetime, time, timedelta, timezone

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    User,
    UserRole,
)
from app.services import (
    DuplicateMatchRequestError,
    InvalidMatchStateError,
    MatchmakingError,
    create_booking,
    create_match,
    decide_match_request,
    expire_stale_match_participants,
    pay_contribution_with_mock,
    request_to_join_match,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)


def _create_split_booking(
    app,
    *,
    creator_id: int,
    field_id: int,
    booking_mode: str,
    requested_players: int | None = None,
) -> str:
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator_id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=booking_mode,
            requested_players=requested_players,
        )
        creator_contribution = next(
            contribution
            for contribution in booking.contributions
            if contribution.user_id == creator_id
        )
        pay_contribution_with_mock(
            booking_code=booking.booking_code,
            contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator_id),
        )
        return booking.booking_code


def _create_match(
    app,
    *,
    booking_code: str,
    creator_id: int,
) -> int:
    with app.app_context():
        match = create_match(
            booking_code=booking_code,
            creator=db.session.get(User, creator_id),
            title="Kèo giao hữu cuối tuần",
            description="Chơi vui, đúng giờ.",
            skill_level="INTERMEDIATE",
        )
        return match.id


def test_empty_match_list_guides_user_to_booking_flow(app, client):
    player = create_user(app, email="player@example.com")
    login(client, email=player.email)

    response = client.get("/matches")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Chưa có kèo đang mở" in html
    assert 'href="/venues"' in html
    assert 'href="/matches/mine"' in html


def test_opponent_request_payment_confirms_match_and_booking(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            message="Đội mình nhận kèo này.",
        )
        decide_match_request(
            match_id=match_id,
            participant_id=participant.id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
        db.session.refresh(participant)
        assert participant.status == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        assert participant.payment_due_at is not None
        assert participant.contribution.user_id == opponent.id

        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id),
        )
        db.session.refresh(participant)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert db.session.get(Match, match_id).status == MatchStatus.CONFIRMED.value
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount


def test_opponent_payment_window_is_capped_at_matchmaking_deadline(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        accepted_at = booking.matchmaking_deadline - timedelta(minutes=5)
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            now=accepted_at,
        )
        decide_match_request(
            match_id=match_id,
            participant_id=participant.id,
            creator=db.session.get(User, creator.id),
            accept=True,
            now=accepted_at,
        )
        assert participant.payment_due_at == booking.matchmaking_deadline


def test_expired_opponent_request_reopens_same_contribution(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    first = create_user(app, email="first@example.com")
    second = create_user(app, email="second@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)
    accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        first_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, first.id),
            now=accepted_at,
        )
        decide_match_request(
            match_id=match_id,
            participant_id=first_request.id,
            creator=db.session.get(User, creator.id),
            accept=True,
            now=accepted_at,
        )
        contribution_id = first_request.contribution_id
        assert expire_stale_match_participants(
            now=accepted_at + timedelta(minutes=16)
        ) == 1
        contribution = db.session.get(BookingContribution, contribution_id)
        assert first_request.status == MatchParticipantStatus.EXPIRED.value
        assert contribution.status == ContributionStatus.PENDING.value
        assert contribution.user_id is None

        second_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, second.id),
        )
        decide_match_request(
            match_id=match_id,
            participant_id=second_request.id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
        assert second_request.contribution_id == contribution_id


def test_find_players_join_with_zalo_has_no_online_payment(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    players = [
        create_user(app, email=f"player{number}@example.com")
        for number in range(1, 3)
    ]
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=2,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        for index, player in enumerate(players, start=1):
            participant = request_to_join_match(
                match_id=match_id,
                user=db.session.get(User, player.id),
                contact_phone=f"091234560{index}",
                share_contact=True,
            )
            decide_match_request(
                match_id=match_id,
                participant_id=participant.id,
                creator=db.session.get(User, creator.id),
                accept=True,
            )
            assert participant.status == MatchParticipantStatus.JOINED.value
            assert participant.contribution_id is None
            assert participant.payment_due_at is None
            assert participant.contact_phone == f"091234560{index}"

        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert db.session.get(Match, match_id).status == MatchStatus.FULL.value
        assert booking.status == BookingStatus.PAID.value
        assert db.session.scalar(db.select(db.func.count(BookingContribution.id))) == 1


def test_find_players_requires_phone_consent_and_rejects_duplicate(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=2,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        user = db.session.get(User, player.id)
        with pytest.raises(MatchmakingError, match="điện thoại"):
            request_to_join_match(match_id=match_id, user=user)
        request_to_join_match(
            match_id=match_id,
            user=user,
            contact_phone="0912345678",
            share_contact=True,
        )
        with pytest.raises(DuplicateMatchRequestError):
            request_to_join_match(
                match_id=match_id,
                user=user,
                contact_phone="0912345678",
                share_contact=True,
            )


def test_cannot_create_match_before_creator_deposit(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        with pytest.raises(InvalidMatchStateError):
            create_match(
                booking_code=booking.booking_code,
                creator=db.session.get(User, creator.id),
                title="Kèo chưa trả cọc",
            )


def test_match_pages_show_open_match_and_request_state(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    response = client.get("/matches")
    assert response.status_code == 200
    assert "Kèo giao hữu cuối tuần" in response.get_data(as_text=True)

    login(client, email=player.email)
    response = client.post(
        f"/matches/{match_id}/requests",
        data={"message": "Đội mình muốn tham gia."},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Đang chờ duyệt" in page
    assert "Đội mình muốn tham gia." not in page
