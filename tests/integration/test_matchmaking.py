from datetime import datetime, time, timedelta, timezone

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingPaymentMode,
    BookingStatus,
    ContributionStatus,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    MatchType,
    User,
    UserRole,
)
from app.services import (
    DuplicateMatchRequestError,
    InvalidMatchStateError,
    create_booking,
    create_match,
    decide_match_request,
    expire_stale_match_participants,
    pay_contribution_with_mock,
    request_to_join_match,
    top_up_booking_with_mock,
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
    payment_mode: str,
    required_players: int | None = None,
) -> str:
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator_id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            payment_mode=payment_mode,
            required_players=required_players,
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
    match_type: str | None = None,
) -> int:
    with app.app_context():
        match = create_match(
            booking_code=booking_code,
            creator=db.session.get(User, creator_id),
            title="Kèo giao hữu cuối tuần",
            description="Chơi vui, đúng giờ.",
            skill_level="INTERMEDIATE",
            match_type=match_type,
        )
        return match.id


def test_empty_match_list_guides_user_to_booking_flow(app, client):
    player = create_user(app, email="player@example.com")
    login(client, email=player.email)

    response = client.get("/matches")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Chưa có kèo đang mở" in html
    assert "Tìm sân để đặt" in html
    assert 'href="/venues"' in html
    assert "Xem kèo của tôi" in html
    assert 'href="/matches/mine"' in html
    assert "hoàn thành khoản thanh toán đầu tiên" not in html


def test_opponent_request_payment_confirms_match_and_booking(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
    )
    match_id = _create_match(
        app,
        booking_code=booking_code,
        creator_id=creator.id,
    )

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
        match = db.session.get(Match, match_id)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert participant.payment_due_at is None
        assert match.status == MatchStatus.CONFIRMED.value
        assert booking.status == BookingStatus.PAID.value


def test_expired_opponent_request_reopens_the_same_payment_slot(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    first = create_user(app, email="first@example.com")
    second = create_user(app, email="second@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
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
        db.session.refresh(first_request)
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
        assert second_request.contribution.user_id == second.id


def test_player_match_becomes_full_only_after_every_player_joins(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    players = [
        create_user(app, email=f"player{number}@example.com")
        for number in range(1, 4)
    ]
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
        required_players=3,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        for index, player in enumerate(players, start=1):
            participant = request_to_join_match(
                match_id=match_id,
                user=db.session.get(User, player.id),
            )
            decide_match_request(
                match_id=match_id,
                participant_id=participant.id,
                creator=db.session.get(User, creator.id),
                accept=True,
            )
            pay_contribution_with_mock(
                booking_code=booking_code,
                contribution_id=participant.contribution_id,
                payer=db.session.get(User, player.id),
            )
            match = db.session.get(Match, match_id)
            assert match.status == (
                MatchStatus.FULL.value if index == 3 else MatchStatus.OPEN.value
            )
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert booking.status == BookingStatus.PAID.value
        assert db.session.scalar(
            db.select(db.func.count(MatchParticipant.id)).where(
                MatchParticipant.status == MatchParticipantStatus.JOINED.value
            )
        ) == 3


def test_creator_top_up_joins_accepted_user_and_future_users_owe_zero(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    first = create_user(app, email="first@example.com")
    second = create_user(app, email="second@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
        required_players=3,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        first_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, first.id),
        )
        decide_match_request(
            match_id=match_id,
            participant_id=first_request.id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
        top_up_booking_with_mock(
            booking_code=booking_code,
            payer=db.session.get(User, creator.id),
        )
        db.session.refresh(first_request)
        assert first_request.status == MatchParticipantStatus.JOINED.value
        assert first_request.contribution.status == ContributionStatus.WAIVED.value

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
        assert second_request.status == MatchParticipantStatus.JOINED.value
        assert second_request.payment_due_at is None
        assert second_request.contribution.status == ContributionStatus.WAIVED.value


def test_duplicate_active_request_is_rejected(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
        required_players=2,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        user = db.session.get(User, player.id)
        request_to_join_match(match_id=match_id, user=user)
        with pytest.raises(DuplicateMatchRequestError):
            request_to_join_match(match_id=match_id, user=user)


def test_cannot_create_match_before_first_payment(app):
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
            payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
        )
        with pytest.raises(InvalidMatchStateError):
            create_match(
                booking_code=booking.booking_code,
                creator=db.session.get(User, creator.id),
                title="Kèo chưa trả tiền",
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
        payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
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

