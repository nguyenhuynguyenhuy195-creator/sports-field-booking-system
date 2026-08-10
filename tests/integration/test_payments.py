from datetime import datetime, time
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingPaymentMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Payment,
    PaymentProvider,
    PaymentStatus,
    User,
    UserRole,
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


def _create_booking(app, *, player_id: int, field_id: int, mode: str):
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player_id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            payment_mode=mode,
            required_players=(3 if mode == BookingPaymentMode.SPLIT_PLAYERS.value else None),
        )
        return booking.booking_code


def test_opponent_split_initial_payment_and_creator_top_up_are_auditable(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
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
        mode=BookingPaymentMode.SPLIT_OPPONENT.value,
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
        assert [item.amount_due for item in contributions] == [
            Decimal("200000.00"),
            Decimal("200000.00"),
        ]

        first_payment = pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=contributions[0].id,
            payer=db.session.get(User, player.id),
        )
        assert first_payment.provider == PaymentProvider.MOCK.value
        assert first_payment.status == PaymentStatus.SUCCESS.value
        assert booking.status == BookingStatus.PARTIALLY_PAID.value
        assert booking.paid_amount == Decimal("200000.00")

        top_up = top_up_booking_with_mock(
            booking_code=booking_code,
            payer=db.session.get(User, player.id),
        )
        db.session.refresh(booking)
        db.session.refresh(contributions[1])
        assert top_up.amount == Decimal("200000.00")
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.total_amount
        assert contributions[1].status == ContributionStatus.WAIVED.value
        assert contributions[1].amount_due == Decimal("200000.00")
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 2


def test_player_split_uses_field_capacity_and_missing_player_count(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
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
        mode=BookingPaymentMode.SPLIT_PLAYERS.value,
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
        assert booking.split_total_players == 10
        assert booking.split_required_players == 3
        assert contributions[0].contribution_type == ContributionType.CREATOR.value
        assert contributions[0].amount_due == Decimal("280000.00")
        assert [item.amount_due for item in contributions[1:]] == [
            Decimal("40000.00"),
            Decimal("40000.00"),
            Decimal("40000.00"),
        ]
        assert sum(item.amount_due for item in contributions) == booking.total_amount


def test_payment_rejects_other_user_and_duplicate_attempt(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    other = create_user(app, email="other@example.com")
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=booking_day(),
    )
    booking_code = _create_booking(
        app,
        player_id=player.id,
        field_id=field_id,
        mode=BookingPaymentMode.FULL_PAYMENT.value,
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


def test_mock_payment_route_updates_booking_and_renders_history(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
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
        mode=BookingPaymentMode.FULL_PAYMENT.value,
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
    assert "Đã thanh toán đủ" in page
    assert "Lịch sử giao dịch" in page
    with app.app_context():
        booking = db.session.scalar(db.select(Booking))
        assert booking.status == BookingStatus.PAID.value


def test_player_split_quote_returns_contribution_preview(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    venue_id, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=booking_day(),
    )
    login(client, email=player.email)

    response = client.post(
        f"/venues/{venue_id}/fields/{field_id}/bookings/quote",
        data=booking_form_data(
            booking_day(),
            payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
            required_players="3",
        ),
    )

    assert response.status_code == 200
    plan = response.get_json()["contribution_plan"]
    assert plan == {
        "creator_amount": "280000",
        "existing_players": 7,
        "external_amount": "120000",
        "external_contributions": [
            {"amount_due": "40000", "slot_number": 1, "type": "PLAYER"},
            {"amount_due": "40000", "slot_number": 2, "type": "PLAYER"},
            {"amount_due": "40000", "slot_number": 3, "type": "PLAYER"},
        ],
        "required_players": 3,
        "total_players": 10,
    }


def test_expiration_marks_creator_contribution_expired(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
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
        mode=BookingPaymentMode.FULL_PAYMENT.value,
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
