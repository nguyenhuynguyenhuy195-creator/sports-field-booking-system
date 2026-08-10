from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    User,
    UserRole,
)

from .locking import with_update_lock


class PaymentError(ValueError):
    """Base error for payment foundation rules."""


class PaymentNotFoundError(PaymentError):
    """Raised when a booking or contribution does not exist."""


class PaymentPermissionError(PaymentError):
    """Raised when a payer does not own a contribution."""


class InvalidPaymentStateError(PaymentError):
    """Raised when payment is not allowed in the current state."""


class PaymentExpiredError(PaymentError):
    """Raised when the payment deadline has passed."""


def pay_contribution_with_mock(
    *,
    booking_code: str,
    contribution_id: int,
    payer: User,
    now: datetime | None = None,
) -> Payment:
    """Record an immediate successful simulated payment in one transaction."""
    _validate_payer(payer)
    current_utc = _normalize_utc(now)
    booking = _lock_booking(booking_code)
    contribution = _lock_contribution(
        booking_id=booking.id,
        contribution_id=contribution_id,
    )
    _validate_payable_contribution(
        booking=booking,
        contribution=contribution,
        payer=payer,
        current_utc=current_utc,
    )
    payment = _record_mock_success(
        booking=booking,
        contribution=contribution,
        payer=payer,
        current_utc=current_utc,
    )
    _commit_payment()
    return payment


def top_up_booking_with_mock(
    *,
    booking_code: str,
    payer: User,
    now: datetime | None = None,
) -> Payment:
    """Let the booking creator pay every remaining unassigned obligation."""
    _validate_payer(payer)
    current_utc = _normalize_utc(now)
    booking = _lock_booking(booking_code)
    if booking.user_id != payer.id:
        raise PaymentPermissionError("Chỉ người tạo booking được trả phần còn thiếu.")
    if booking.status != BookingStatus.PARTIALLY_PAID.value:
        raise InvalidPaymentStateError(
            "Chỉ booking đã thanh toán một phần mới có thể trả phần còn thiếu."
        )
    if booking.funding_deadline is None or booking.funding_deadline <= current_utc:
        raise PaymentExpiredError("Đã hết hạn góp đủ tiền cho booking này.")

    remaining = Decimal(booking.total_amount) - Decimal(booking.paid_amount)
    if remaining <= 0:
        raise InvalidPaymentStateError("Booking đã được thanh toán đủ.")

    pending_statement = db.select(BookingContribution).where(
        BookingContribution.booking_id == booking.id,
        BookingContribution.status == ContributionStatus.PENDING.value,
    )
    pending_records = list(
        db.session.scalars(with_update_lock(pending_statement, BookingContribution))
    )
    for record in pending_records:
        if (
            record.user_id == payer.id
            and record.contribution_type == ContributionType.CREATOR.value
        ):
            continue
        record.status = ContributionStatus.WAIVED.value

    top_up = BookingContribution(
        booking_id=booking.id,
        user_id=payer.id,
        contribution_type=ContributionType.TOP_UP.value,
        slot_number=None,
        amount_due=remaining,
        amount_paid=Decimal("0.00"),
        status=ContributionStatus.PENDING.value,
        expires_at=booking.funding_deadline,
    )
    db.session.add(top_up)
    db.session.flush()
    payment = _record_mock_success(
        booking=booking,
        contribution=top_up,
        payer=payer,
        current_utc=current_utc,
    )
    _commit_payment()
    return payment


def _record_mock_success(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payer: User,
    current_utc: datetime,
) -> Payment:
    amount = contribution.remaining_amount
    if amount <= 0:
        raise InvalidPaymentStateError("Khoản đóng góp này không còn số tiền phải trả.")
    new_paid_amount = Decimal(booking.paid_amount) + amount
    if new_paid_amount > Decimal(booking.total_amount):
        raise InvalidPaymentStateError("Giao dịch sẽ làm tổng tiền vượt tiền sân.")

    unique_token = uuid4().hex.upper()
    payment = Payment(
        booking_id=booking.id,
        contribution_id=contribution.id,
        payer_id=payer.id,
        provider=PaymentProvider.MOCK.value,
        payment_method=PaymentMethod.SIMULATED.value,
        amount=amount,
        order_id=f"MOCK-ORDER-{unique_token}",
        request_id=f"MOCK-REQUEST-{uuid4().hex.upper()}",
        provider_trans_id=f"MOCK-TRANS-{uuid4().hex.upper()}",
        status=PaymentStatus.SUCCESS.value,
        result_code="0",
        paid_at=current_utc,
    )
    db.session.add(payment)
    contribution.amount_paid = Decimal(contribution.amount_due)
    contribution.status = ContributionStatus.PAID.value
    booking.paid_amount = new_paid_amount
    booking.status = (
        BookingStatus.PAID.value
        if new_paid_amount == Decimal(booking.total_amount)
        else BookingStatus.PARTIALLY_PAID.value
    )
    return payment


def _validate_payable_contribution(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payer: User,
    current_utc: datetime,
) -> None:
    if contribution.user_id != payer.id:
        raise PaymentPermissionError("Bạn không có quyền thanh toán khoản này.")
    if booking.status not in {
        BookingStatus.CONFIRMED.value,
        BookingStatus.PARTIALLY_PAID.value,
    }:
        raise InvalidPaymentStateError("Booking hiện không thể nhận thanh toán.")
    if contribution.status != ContributionStatus.PENDING.value:
        raise InvalidPaymentStateError("Khoản đóng góp đã được xử lý.")
    if contribution.expires_at is not None and contribution.expires_at <= current_utc:
        contribution.status = ContributionStatus.EXPIRED.value
        if booking.status == BookingStatus.CONFIRMED.value and Decimal(booking.paid_amount) == 0:
            booking.status = BookingStatus.EXPIRED.value
        _commit_payment()
        raise PaymentExpiredError("Khoản thanh toán đã hết hạn.")


def _lock_booking(booking_code: str) -> Booking:
    statement = with_update_lock(
        db.select(Booking).where(Booking.booking_code == booking_code),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking is None:
        raise PaymentNotFoundError("Không tìm thấy booking.")
    return booking


def _lock_contribution(
    *,
    booking_id: int,
    contribution_id: int,
) -> BookingContribution:
    statement = with_update_lock(
        db.select(BookingContribution).where(
            BookingContribution.id == contribution_id,
            BookingContribution.booking_id == booking_id,
        ),
        BookingContribution,
    )
    contribution = db.session.scalar(statement)
    if contribution is None:
        raise PaymentNotFoundError("Không tìm thấy khoản đóng góp.")
    return contribution


def _validate_payer(payer: User) -> None:
    if payer.role not in {UserRole.USER.value, UserRole.OWNER.value}:
        raise PaymentPermissionError("Tài khoản này không thể thanh toán.")


def _normalize_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _commit_payment() -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise PaymentError("Không thể cập nhật thanh toán lúc này.") from exc
