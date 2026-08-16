from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Payment,
    PaymentProvider,
    PaymentStatus,
    User,
)
from app.services import (
    InvalidPaymentStateError,
    PaymentPermissionError,
    create_booking,
    expire_stale_bookings,
    pay_contribution_with_mock,
    top_up_booking_with_mock,
)
from tests.integration.test_bookings import (
    booking_day,
    booking_form_data,
    create_bookable_field,
    create_user,
    login,
)


def test_home_page_explains_current_deposit_policy(client):
    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Đặt sân: cọc 30%, phần còn lại trả tại sân" in page
    assert "Tìm đối thủ: mỗi đội cọc 15%" in page
    assert "Tìm thêm người: người ghép trả tại sân" in page
    assert "Hai đội chia 50/50" not in page
    assert "Chia theo từng người tham gia" not in page


def _create_booking(app, *, player_id: int, field_id: int, mode: str):
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player_id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=mode,
            requested_players=(3 if mode == BookingMode.FIND_PLAYERS.value else None),
        )
        return booking.booking_code


def test_legacy_opponent_deposit_and_creator_top_up_are_auditable(app):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=booking_day(),
    )
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingMode.FIND_OPPONENT.value,
    )

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        contributions = list(
            db.session.scalars(
                db.select(BookingContribution)
                .where(BookingContribution.booking_id == booking.id)
                .order_by(BookingContribution.id)
            )
        )
        assert booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
        assert booking.total_amount == Decimal("400000.00")
        assert booking.deposit_amount == Decimal("120000.00")
        assert [item.amount_due for item in contributions] == [
            Decimal("60000.00"),
            Decimal("60000.00"),
        ]

        first_payment = pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=contributions[0].id,
            payer=db.session.get(User, player.id),
        )
        assert first_payment.provider == PaymentProvider.MOCK.value
        assert first_payment.status == PaymentStatus.SUCCESS.value
        assert booking.status == BookingStatus.PARTIALLY_PAID.value
        assert booking.paid_amount == Decimal("60000.00")

        legacy_matchmaking_deadline = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(minutes=1)
        booking.matchmaking_deadline = legacy_matchmaking_deadline
        booking.funding_deadline = legacy_matchmaking_deadline + timedelta(minutes=30)
        db.session.commit()
        top_up = top_up_booking_with_mock(
            booking_code=booking_code,
            payer=db.session.get(User, player.id),
            now=legacy_matchmaking_deadline + timedelta(minutes=1),
        )
        db.session.refresh(booking)
        db.session.refresh(contributions[1])
        assert top_up.amount == Decimal("60000.00")
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount
        assert contributions[1].status == ContributionStatus.WAIVED.value
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 2


def test_find_players_creates_only_creator_deposit(app):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingMode.FIND_PLAYERS.value,
    )

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        contributions = list(
            db.session.scalars(
                db.select(BookingContribution).where(
                    BookingContribution.booking_id == booking.id
                )
            )
        )
        assert booking.requested_players == 3
        assert len(contributions) == 1
        assert contributions[0].contribution_type == ContributionType.CREATOR.value
        assert contributions[0].amount_due == booking.deposit_amount


def test_payment_rejects_other_user_and_duplicate_attempt(app):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    other = create_user(app, email="other@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingMode.DIRECT_BOOKING.value,
    )

    with app.app_context():
        contribution = db.session.scalar(db.select(BookingContribution))
        with pytest.raises(PaymentPermissionError):
            pay_contribution_with_mock(
                booking_code=booking_code,
                contribution_id=contribution.id,
                payer=db.session.get(User, other.id),
            )
        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=contribution.id,
            payer=db.session.get(User, player.id),
        )
        with pytest.raises(InvalidPaymentStateError):
            pay_contribution_with_mock(
                booking_code=booking_code,
                contribution_id=contribution.id,
                payer=db.session.get(User, player.id),
            )


def test_mock_payment_route_updates_booking_and_renders_deposit_copy(app, client):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingMode.DIRECT_BOOKING.value,
    )
    with app.app_context():
        contribution_id = db.session.scalar(db.select(BookingContribution.id))

    login(client, email=player.email)
    response = client.post(
        f"/bookings/{booking_code}/contributions/{contribution_id}/payments/mock",
        follow_redirects=True,
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Đã thanh toán cọc" in page
    assert "Còn lại trả tại sân" in page
    assert "Lịch sử thanh toán" in page
    with app.app_context():
        booking = db.session.scalar(db.select(Booking))
        assert booking.status == BookingStatus.PAID.value


def test_find_players_quote_has_no_external_online_contribution(app, client):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    venue_id, field_id = create_bookable_field(app, owner_id=owner.id)
    login(client, email=player.email)

    response = client.post(
        f"/venues/{venue_id}/fields/{field_id}/bookings/quote",
        data=booking_form_data(
            booking_day(),
            booking_mode=BookingMode.FIND_PLAYERS.value,
            requested_players="3",
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["deposit_amount"] == "120000"
    assert payload["venue_balance"] == "280000.00"
    assert payload["contribution_plan"] == {
        "creator_amount": "120000",
        "external_amount": "0",
        "external_contributions": [],
        "requested_players": 3,
    }


def test_expiration_marks_creator_contribution_expired(app):
    owner = create_user(app, email="owner@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingMode.DIRECT_BOOKING.value,
    )

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking.initial_payment_due_at = datetime(2020, 1, 1)
        db.session.commit()
        assert expire_stale_bookings(now=datetime(2020, 1, 2)) == 1
        contribution = db.session.scalar(db.select(BookingContribution))
        assert booking.status == BookingStatus.EXPIRED.value
        assert contribution.status == ContributionStatus.EXPIRED.value
