from datetime import datetime, timedelta
from decimal import Decimal

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
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
    UserRole,
)
from app.services import (
    cancel_owner_booking,
    cancel_user_booking,
    decide_match_request,
    pay_contribution_with_mock,
    process_overdue_funding_refunds,
    request_to_join_match,
    withdraw_match_request,
)
from tests.integration.test_bookings import create_bookable_field, create_user, login
from tests.integration.test_matchmaking import _create_match, _create_split_booking


def _prepare_joined_opponent(app):
    owner = create_user(app, email="owner-refund@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator-refund@example.com")
    opponent = create_user(app, email="opponent-refund@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
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
            payer=db.session.get(User, opponent.id),
        )
        return owner, creator, opponent, booking_code, match_id, participant.id


def test_creator_cancels_partial_booking_with_80_20_policy(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )

    with app.app_context():
        booking = cancel_user_booking(
            booking_code=booking_code,
            user=db.session.get(User, creator.id),
        )
        refund = db.session.scalar(db.select(Refund))
        payment = db.session.scalar(db.select(Payment))
        creator_contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.user_id == creator.id
            )
        )

        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.paid_amount == Decimal("12000.00")
        assert booking.cancellation_fee_amount == Decimal("12000.00")
        assert refund.amount == Decimal("48000.00")
        assert refund.status == RefundStatus.SUCCESS.value
        assert payment.status == PaymentStatus.SUCCESS.value
        assert creator_contribution.amount_paid == Decimal("12000.00")
        assert (
            creator_contribution.status
            == ContributionStatus.PARTIALLY_REFUNDED.value
        )


def test_owner_cancels_paid_booking_and_refunds_every_payment(app):
    owner, _, _, booking_code, _, _ = _prepare_joined_opponent(app)

    with app.app_context():
        booking = cancel_owner_booking(
            booking_code=booking_code,
            owner=db.session.get(User, owner.id),
            reason="Sân ngập nước đột xuất.",
        )
        refunds = list(db.session.scalars(db.select(Refund).order_by(Refund.id)))
        payments = list(db.session.scalars(db.select(Payment).order_by(Payment.id)))

        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.paid_amount == Decimal("0.00")
        assert booking.cancellation_fee_amount == Decimal("0.00")
        assert booking.match.status == MatchStatus.CANCELLED.value
        assert len(refunds) == 2
        assert sum(item.amount for item in refunds) == booking.deposit_amount
        assert {item.status for item in refunds} == {RefundStatus.SUCCESS.value}
        assert {item.status for item in payments} == {PaymentStatus.SUCCESS.value}


def test_funding_deadline_refund_job_is_idempotent(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    deadline = datetime(2026, 8, 10, 0, 0)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking.funding_deadline = deadline
        db.session.commit()

        assert process_overdue_funding_refunds(
            now=deadline + timedelta(minutes=1)
        ) == 1
        assert process_overdue_funding_refunds(
            now=deadline + timedelta(minutes=2)
        ) == 0
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1
        db.session.refresh(booking)
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.cancellation_fee_amount == Decimal("12000.00")


def test_paid_participant_withdraws_over_12_hours_with_full_refund(app):
    _, _, opponent, booking_code, match_id, participant_id = (
        _prepare_joined_opponent(app)
    )
    replacement_user = create_user(app, email="replacement@example.com")

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        old_contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id
        participant = withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
        )
        old_contribution = db.session.get(
            BookingContribution, old_contribution_id
        )
        replacement = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id,
                BookingContribution.slot_number == old_contribution.slot_number,
                BookingContribution.status == ContributionStatus.PENDING.value,
            )
        )

        assert participant.status == MatchParticipantStatus.WITHDRAWN.value
        assert old_contribution.status == ContributionStatus.REFUNDED.value
        assert old_contribution.amount_paid == Decimal("0.00")
        assert replacement is not None
        assert replacement.id != old_contribution.id
        assert replacement.amount_due == old_contribution.amount_due
        assert booking.status == BookingStatus.PARTIALLY_PAID.value
        assert booking.paid_amount == Decimal("60000.00")
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1
        assert db.session.get(Match, match_id).status == MatchStatus.OPEN.value

        replacement_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, replacement_user.id),
        )
        decide_match_request(
            match_id=match_id,
            participant_id=replacement_request.id,
            creator=db.session.get(User, booking.user_id),
            accept=True,
        )
        assert replacement_request.contribution_id == replacement.id
        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=replacement.id,
            payer=db.session.get(User, replacement_user.id),
        )
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount


def test_paid_participant_withdraws_inside_12_hours_without_refund(app):
    _, _, opponent, booking_code, match_id, participant_id = (
        _prepare_joined_opponent(app)
    )

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking_start_utc = datetime.combine(
            booking.booking_date,
            booking.start_time,
        ) - timedelta(hours=7)
        participant = withdraw_match_request(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            now=booking_start_utc - timedelta(hours=10),
        )
        contribution = db.session.get(
            BookingContribution,
            db.session.get(MatchParticipant, participant_id).contribution_id,
        )

        assert participant.status == MatchParticipantStatus.WITHDRAWN.value
        assert contribution.status == ContributionStatus.FORFEITED.value
        assert contribution.amount_paid == contribution.amount_due
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 0


def test_creator_cancel_route_renders_refund_history(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    login(client, email=creator.email)

    response = client.post(
        f"/bookings/{booking_code}/cancel",
        follow_redirects=True,
    )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Lịch sử thanh toán" in page
    assert "Lịch sử hoàn tiền" in page
    assert "48.000" in page
    assert "Phí giữ sân" in page
    assert "Còn thiếu:" not in page
    assert "Booking đã được hủy" in page
