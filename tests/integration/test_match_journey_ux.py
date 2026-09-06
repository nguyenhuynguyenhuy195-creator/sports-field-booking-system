from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    Payment,
    Refund,
    User,
    UserRole,
)
from app.routes.matches import _match_view_status, _opponent_obligation_is_covered
from app.services import (
    current_vietnam_datetime,
    decide_match_request,
    pay_contribution_with_mock,
    request_to_join_match,
    withdraw_match_request,
)
from tests.integration.test_bookings import (
    create_bookable_field,
    create_user,
    login,
)
from tests.integration.test_matchmaking import _create_match, _create_split_booking


def _prepare_match(app, *, mode=BookingMode.FIND_OPPONENT.value):
    owner = create_user(app, email="owner-match-ux@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator-match-ux@example.com")
    player = create_user(app, email="player-match-ux@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=mode,
        requested_players=2 if mode == BookingMode.FIND_PLAYERS.value else None,
    )
    match_id = _create_match(
        app,
        booking_code=booking_code,
        creator_id=creator.id,
    )
    return creator, player, booking_code, match_id


def _join(app, *, match_id, user_id, phone="0901000002", pay=False):
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


def _financial_counts():
    return (
        db.session.scalar(db.select(db.func.count(Payment.id))),
        db.session.scalar(db.select(db.func.count(BookingContribution.id))),
        db.session.scalar(db.select(db.func.sum(Booking.paid_amount))),
        db.session.scalar(db.select(db.func.count(Refund.id))),
    )


def test_first_opponent_still_sees_15_percent_payment_journey(app, client):
    _, player, _, match_id = _prepare_match(app)
    login(client, email=player.email)

    open_page = client.get(f"/matches/{match_id}").get_data(as_text=True)

    assert "Tiền cọc cần thanh toán" in open_page
    assert "60.000" in open_page
    assert "Nhận kèo và thanh toán cọc" in open_page
    assert "Không cần thanh toán lại cọc" not in open_page
    public_list = client.get("/matches").get_data(as_text=True)
    assert "Kèo giao hữu cuối tuần" in public_list
    assert "Đang mở" in public_list

    response = client.post(
        f"/matches/{match_id}/requests",
        data={
            "contact_phone": "0901000002",
            "share_contact": "y",
            "message": "Đội mình nhận kèo.",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Tiền cọc đội bạn (15%)" in html
    assert "Thử thanh toán cọc" in html
    mine = client.get("/matches/mine").get_data(as_text=True)
    assert "Đang mở" in mine
    assert "Đang giữ suất, chờ thanh toán" in mine


def test_replacement_opponent_joins_without_new_charge(app, client):
    creator, first_opponent, booking_code, match_id = _prepare_match(app)
    replacement = create_user(app, email="replacement-match-ux@example.com")
    first_participant_id = _join(
        app,
        match_id=match_id,
        user_id=first_opponent.id,
        pay=True,
    )

    with app.app_context():
        before_withdrawal = _financial_counts()
        withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, first_opponent.id),
        )
        first_participant = db.session.get(MatchParticipant, first_participant_id)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert first_participant.status == MatchParticipantStatus.WITHDRAWN.value
        assert first_participant.contribution.status == ContributionStatus.FORFEITED.value
        assert booking.status == BookingStatus.PAID.value
        assert _financial_counts() == before_withdrawal

    login(client, email=replacement.email)
    open_page = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Không cần thanh toán lại cọc" in open_page
    assert "Tiền cọc cần thanh toán" not in open_page
    assert "Nhận kèo và thanh toán cọc" not in open_page

    response = client.post(
        f"/matches/{match_id}/requests",
        data={
            "contact_phone": "0901000003",
            "share_contact": "y",
            "message": "Đội thay thế nhận kèo.",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Bạn đã tham gia kèo" in html
    assert "Không cần thanh toán lại cọc" in html
    assert "Thử thanh toán cọc" not in html

    with app.app_context():
        replacement_participant = db.session.scalar(
            db.select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == replacement.id,
            )
        )
        assert replacement_participant.status == MatchParticipantStatus.JOINED.value
        assert replacement_participant.contribution_id is None
        assert _financial_counts() == before_withdrawal
        assert db.session.get(Match, match_id).creator_id == creator.id


def test_past_open_match_uses_effective_status_and_hides_actions_and_contacts(
    app, client
):
    creator, player, _, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id, pay=True)
    with app.app_context():
        match = db.session.get(Match, match_id)
        match.booking.booking_date = current_vietnam_datetime().date() - timedelta(days=1)
        db.session.commit()
        assert match.status == MatchStatus.CONFIRMED.value
        assert _match_view_status(match) == "PAST"

    login(client, email=player.email)
    detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    mine = client.get("/matches/mine").get_data(as_text=True)
    public_list = client.get("/matches").get_data(as_text=True)

    assert "Đã diễn ra" in detail
    assert "Đang mở" not in detail
    assert "Thông tin liên hệ không còn được hiển thị" in detail
    assert "0901000001" not in detail
    assert f'action="/matches/{match_id}/withdraw"' not in detail
    assert f'action="/matches/{match_id}/contact"' not in detail
    assert "Đã diễn ra" in mine
    assert "Đã tham gia" in mine
    assert "Kèo đã khép lại" not in mine
    assert "Kèo giao hữu cuối tuần" not in public_list

    client.post("/auth/logout")
    login(client, email=creator.email)
    creator_detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Thông tin liên hệ không còn được hiển thị" in creator_detail
    assert "0901000002" not in creator_detail
    assert f'action="/matches/{match_id}/close"' not in creator_detail
    assert f'action="/matches/{match_id}/contact"' not in creator_detail
    with app.app_context():
        assert db.session.get(MatchParticipant, participant_id).status == "JOINED"


def test_match_view_status_distinguishes_future_closed_cancelled_and_completed(app):
    creator, _, _, match_id = _prepare_match(app)
    client = app.test_client()
    login(client, email=creator.email)

    future_detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    future_mine = client.get("/matches/mine").get_data(as_text=True)
    assert "Đang mở" in future_detail
    assert "Đang mở" in future_mine

    with app.app_context():
        match = db.session.get(Match, match_id)
        assert _match_view_status(match) == MatchStatus.OPEN.value

        match.status = MatchStatus.CANCELLED.value
        assert _match_view_status(match) == "CLOSED_LISTING"
        db.session.commit()

    closed_detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    closed_mine = client.get("/matches/mine").get_data(as_text=True)
    assert "Đã đóng bài tìm đối thủ" in closed_detail
    assert "Đã đóng bài tìm đối thủ" in closed_mine

    with app.app_context():
        match = db.session.get(Match, match_id)
        match.booking.status = BookingStatus.CANCELLED.value
        assert _match_view_status(match) == MatchStatus.CANCELLED.value
        db.session.commit()

    cancelled_detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Đã hủy" in cancelled_detail
    assert "Đã đóng bài tìm đối thủ" not in cancelled_detail

    with app.app_context():
        match = db.session.get(Match, match_id)
        match.status = MatchStatus.COMPLETED.value
        assert _match_view_status(match) == MatchStatus.COMPLETED.value
        db.session.commit()

    completed_detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Đã hoàn thành" in completed_detail


def test_past_find_players_hides_join_accept_reject_and_remaining_copy(app, client):
    creator, player, _, match_id = _prepare_match(
        app, mode=BookingMode.FIND_PLAYERS.value
    )
    _join(app, match_id=match_id, user_id=player.id)
    with app.app_context():
        match = db.session.get(Match, match_id)
        match.booking.booking_date = current_vietnam_datetime().date() - timedelta(days=1)
        db.session.commit()

    login(client, email=creator.email)
    detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    mine = client.get("/matches/mine").get_data(as_text=True)

    assert "Đã diễn ra" in detail
    assert "Kèo đã khép lại" in detail
    assert "Còn thiếu" not in detail
    assert f"/matches/{match_id}/requests/" not in detail
    assert ">Chấp nhận<" not in detail
    assert ">Từ chối<" not in detail
    assert "Kèo đã khép lại" in mine


def test_missing_zalo_is_distinct_from_hidden_existing_zalo(app, client):
    _, player, _, match_id = _prepare_match(app)
    _join(app, match_id=match_id, user_id=player.id, pay=True)
    with app.app_context():
        match = db.session.get(Match, match_id)
        match.creator_contact_phone = None
        db.session.commit()

    login(client, email=player.email)
    html = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Chưa cung cấp số Zalo" in html
    assert "Thông tin liên hệ không còn được hiển thị" not in html


def test_future_find_players_full_is_clear_and_has_no_payment_copy(app, client):
    creator, player, _, match_id = _prepare_match(
        app, mode=BookingMode.FIND_PLAYERS.value
    )
    participant_id = _join(app, match_id=match_id, user_id=player.id)
    with app.app_context():
        match = db.session.get(Match, match_id)
        match.required_players = 1
        decide_match_request(
            match_id=match_id,
            participant_id=participant_id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
        assert match.status == MatchStatus.FULL.value

    login(client, email=player.email)
    detail = client.get(f"/matches/{match_id}").get_data(as_text=True)
    mine = client.get("/matches/mine").get_data(as_text=True)

    assert "Đã đủ người" in detail
    assert "Đã đủ người" in mine
    assert "Đã tham gia" in mine
    assert "Tiền cọc đội bạn" not in detail
    assert "Thanh toán cọc" not in detail


@pytest.mark.parametrize(
    ("contribution_type", "contribution_status", "paid_amount_adjustment"),
    [
        (
            ContributionType.OPPONENT.value,
            ContributionStatus.FORFEITED.value,
            Decimal("-0.01"),
        ),
        (
            ContributionType.CREATOR.value,
            ContributionStatus.FORFEITED.value,
            Decimal("0.00"),
        ),
        (
            ContributionType.OPPONENT.value,
            ContributionStatus.REFUNDED.value,
            Decimal("0.00"),
        ),
    ],
)
def test_only_full_forfeited_opponent_contribution_covers_replacement(
    app,
    contribution_type,
    contribution_status,
    paid_amount_adjustment,
):
    _, _, _, match_id = _prepare_match(app)
    with app.app_context():
        match = db.session.get(Match, match_id)
        contribution = next(
            item
            for item in match.booking.contributions
            if item.contribution_type == ContributionType.OPPONENT.value
        )
        contribution.contribution_type = contribution_type
        contribution.status = contribution_status
        contribution.amount_paid = (
            Decimal(contribution.amount_due) + paid_amount_adjustment
        )
        with db.session.no_autoflush:
            assert not _opponent_obligation_is_covered(match)


@pytest.mark.parametrize(
    "stored_status",
    [
        MatchStatus.OPEN.value,
        MatchStatus.FULL.value,
        MatchStatus.CONFIRMED.value,
    ],
)
def test_effective_match_status_changes_at_booking_start_boundary(app, stored_status):
    _, _, _, match_id = _prepare_match(app)
    with app.app_context():
        match = db.session.get(Match, match_id)
        match.status = stored_status
        start_utc = datetime.combine(
            match.booking.booking_date,
            match.booking.start_time,
        ) - timedelta(hours=7)

        assert _match_view_status(
            match,
            now=start_utc - timedelta(microseconds=1),
        ) == stored_status
        assert _match_view_status(match, now=start_utc) == "PAST"
        assert _match_view_status(
            match,
            now=start_utc + timedelta(microseconds=1),
        ) == "PAST"
