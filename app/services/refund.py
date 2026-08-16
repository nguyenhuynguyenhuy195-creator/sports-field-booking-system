from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.integrations import MomoAPIError, MomoClient
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    MatchStatus,
    MatchParticipant,
    MatchParticipantStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
)

from .locking import with_update_lock


MONEY_QUANTUM = Decimal("0.01")
CREATOR_REFUND_RATE = Decimal("0.80")


class RefundError(ValueError):
    """Base error for refund policies and persistence."""


class InvalidRefundStateError(RefundError):
    """Raised when a refund cannot be applied to the current data."""


@dataclass(frozen=True)
class ParticipantRefundResult:
    refund: Refund
    replacement_contribution: BookingContribution


def apply_owner_cancellation_refunds(
    *,
    booking: Booking,
    reason: str,
    now: datetime | None = None,
) -> list[Refund]:
    """Refund 100% of every net collected payment for an owner cancellation."""
    current_utc = normalize_utc(now)
    booking.status = BookingStatus.REFUND_PENDING.value
    booking.cancellation_reason = reason
    booking.cancellation_fee_amount = Decimal("0.00")
    refunds = _refund_collected_payments(
        booking=booking,
        current_utc=current_utc,
        policy_key="OWNER-CANCEL",
        reason=f"Chủ sân hủy do sự cố: {reason}",
        creator_rate=Decimal("1.00"),
    )
    if all(refund.status == RefundStatus.SUCCESS.value for refund in refunds):
        _finish_cancelled_booking(booking, current_utc=current_utc)
    return refunds


def apply_creator_cancellation_policy(
    *,
    booking: Booking,
    reason: str,
    now: datetime | None = None,
) -> list[Refund]:
    """Forfeit creator money and refund active opponent money in full."""
    current_utc = normalize_utc(now)
    booking.status = BookingStatus.REFUND_PENDING.value
    booking.cancellation_reason = reason
    payments = list(
        db.session.scalars(
            with_update_lock(
                db.select(Payment)
                .where(
                    Payment.booking_id == booking.id,
                    Payment.status == PaymentStatus.SUCCESS.value,
                )
                .order_by(Payment.id),
                Payment,
            )
        )
    )
    refunds: list[Refund] = []
    forfeited_total = Decimal("0.00")
    for payment in payments:
        contribution = db.session.get(BookingContribution, payment.contribution_id)
        if contribution is None:
            raise InvalidRefundStateError("Giao dịch không còn khoản đóng góp gốc.")
        refundable = _remaining_refundable_amount(payment)
        if refundable <= 0:
            continue
        creator_payment = contribution.contribution_type in {
            ContributionType.CREATOR.value,
            ContributionType.TOP_UP.value,
        }
        already_forfeited = contribution.status == ContributionStatus.FORFEITED.value
        if creator_payment or already_forfeited:
            contribution.status = ContributionStatus.FORFEITED.value
            contribution.expires_at = None
            if creator_payment:
                forfeited_total += refundable
            continue
        contribution.status = ContributionStatus.REFUND_PENDING.value
        refund, _ = _record_refund(
            booking=booking,
            contribution=contribution,
            payment=payment,
            amount=refundable,
            reason="Người đặt sân hủy; hoàn 100% tiền cọc của đối thủ.",
            operation_key=f"CREATOR-CANCEL-{payment.id}",
            current_utc=current_utc,
        )
        refunds.append(refund)

    booking.cancellation_fee_amount = forfeited_total.quantize(MONEY_QUANTUM)
    if all(refund.status == RefundStatus.SUCCESS.value for refund in refunds):
        _finish_cancelled_booking(booking, current_utc=current_utc)
    return refunds


def apply_funding_shortfall_refunds(
    *,
    booking: Booking,
    reason: str,
    now: datetime | None = None,
) -> list[Refund]:
    """Refund creator 80%, other payers 100%, and retain the creator's 20%."""
    if booking.booking_mode != BookingMode.FIND_OPPONENT.value:
        raise InvalidRefundStateError(
            "Chính sách thiếu tiền chỉ áp dụng cho lịch đặt có nhiều người đóng."
        )
    current_utc = normalize_utc(now)
    paid_before_refunds = Decimal(booking.paid_amount)
    booking.status = BookingStatus.REFUND_PENDING.value
    booking.cancellation_reason = reason
    refunds = _refund_collected_payments(
        booking=booking,
        current_utc=current_utc,
        policy_key="FUNDING-SHORTFALL",
        reason=reason,
        creator_rate=CREATOR_REFUND_RATE,
    )
    booking.cancellation_fee_amount = (
        paid_before_refunds - sum(
            (Decimal(refund.amount) for refund in refunds),
            Decimal("0.00"),
        )
    ).quantize(MONEY_QUANTUM)
    if all(refund.status == RefundStatus.SUCCESS.value for refund in refunds):
        _finish_cancelled_booking(booking, current_utc=current_utc)
    return refunds


def refund_joined_participant(
    *,
    booking: Booking,
    contribution: BookingContribution,
    participant_id: int,
    now: datetime | None = None,
) -> ParticipantRefundResult:
    """Refund a paid match participant and create a fresh obligation for the slot."""
    if contribution.booking_id != booking.id:
        raise InvalidRefundStateError("Khoản tiền này không thuộc lịch đặt sân.")
    if contribution.contribution_type not in {
        ContributionType.OPPONENT.value,
        ContributionType.PLAYER.value,
    }:
        raise InvalidRefundStateError("Khoản đóng góp này không phải suất ghép kèo.")
    if (
        contribution.status != ContributionStatus.PAID.value
        or Decimal(contribution.amount_paid) <= 0
    ):
        raise InvalidRefundStateError("Suất tham gia này không có tiền để hoàn.")

    payment = _lock_successful_payment(contribution.id)
    if payment is None:
        raise InvalidRefundStateError("Không tìm thấy giao dịch thành công để hoàn.")
    refund_amount = _remaining_refundable_amount(payment)
    if refund_amount != Decimal(contribution.amount_paid):
        raise InvalidRefundStateError("Số tiền có thể hoàn không khớp khoản đã đóng.")

    refund, created = _record_refund(
        booking=booking,
        contribution=contribution,
        payment=payment,
        amount=refund_amount,
        reason="Người tham gia rút khỏi kèo trước giờ bắt đầu trên 12 giờ.",
        operation_key=f"WITHDRAW-{participant_id}",
        current_utc=normalize_utc(now),
    )
    if not created:
        raise InvalidRefundStateError("Yêu cầu rút này đã được hoàn tiền trước đó.")

    booking.status = (
        BookingStatus.PAID.value
        if Decimal(booking.paid_amount) == Decimal(booking.deposit_amount)
        else BookingStatus.PARTIALLY_PAID.value
    )
    contribution.expires_at = None
    db.session.flush()
    replacement = BookingContribution(
        booking_id=booking.id,
        user_id=None,
        contribution_type=contribution.contribution_type,
        slot_number=contribution.slot_number,
        amount_due=Decimal(contribution.amount_due),
        amount_paid=Decimal("0.00"),
        status=ContributionStatus.PENDING.value,
        expires_at=booking.funding_deadline,
    )
    db.session.add(replacement)
    return ParticipantRefundResult(
        refund=refund,
        replacement_contribution=replacement,
    )


def process_overdue_funding_refunds(*, now: datetime | None = None) -> int:
    """Apply the 80/20 funding policy to overdue split bookings idempotently."""
    current_utc = normalize_utc(now)
    statement = with_update_lock(
        db.select(Booking).where(
            Booking.status == BookingStatus.PARTIALLY_PAID.value,
            Booking.funding_deadline.is_not(None),
            Booking.funding_deadline <= current_utc,
            Booking.paid_amount < Booking.deposit_amount,
        ),
        Booking,
    )
    bookings = list(db.session.scalars(statement))
    for booking in bookings:
        apply_funding_shortfall_refunds(
            booking=booking,
            reason="Lịch đặt không được đóng đủ tiền trước hạn 12 giờ.",
            now=current_utc,
        )
    if bookings:
        commit_refunds("Không thể xử lý các lịch đặt thiếu tiền đúng hạn.")
        try:
            process_pending_momo_refunds(now=current_utc)
        except RefundError:
            db.session.rollback()
    return len(bookings)


def process_pending_momo_refunds(
    *,
    booking_id: int | None = None,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> int:
    """Submit/query pending MoMo refunds and finalize successful records."""
    statement = (
        db.select(Refund)
        .join(Refund.payment)
        .where(
            Payment.provider == PaymentProvider.MOMO.value,
            Refund.status.in_(
                (RefundStatus.PENDING.value, RefundStatus.PROCESSING.value)
            ),
        )
        .order_by(Refund.id)
    )
    if booking_id is not None:
        statement = statement.where(Refund.booking_id == booking_id)
    refunds = list(db.session.scalars(with_update_lock(statement, Refund)))
    if not refunds:
        return 0

    try:
        momo = client or MomoClient.from_app_config()
    except MomoAPIError as exc:
        raise RefundError(str(exc)) from exc
    current_utc = normalize_utc(now)
    succeeded = 0
    touched_booking_ids: set[int] = set()
    for refund in refunds:
        payment = refund.payment
        if not payment.provider_trans_id:
            refund.status = RefundStatus.FAILED.value
            refund.result_code = "MISSING_TRANS_ID"
            continue
        try:
            if refund.status == RefundStatus.PENDING.value:
                response = momo.refund_payment(
                    order_id=refund.order_id,
                    request_id=refund.request_id,
                    amount=Decimal(refund.amount),
                    trans_id=payment.provider_trans_id,
                    description=refund.reason,
                )
                result_code = str(response.get("resultCode", ""))
                provider_trans_id = str(response.get("transId", "")) or None
            else:
                response = momo.query_refund(
                    order_id=refund.order_id,
                    request_id=uuid4().hex,
                )
                result_code, provider_trans_id = _parse_refund_query(
                    refund.order_id,
                    response,
                )
        except MomoAPIError as exc:
            raise RefundError(str(exc)) from exc

        refund.result_code = result_code
        if result_code == "0" and provider_trans_id:
            contribution = refund.payment.contribution
            booking = refund.booking
            _apply_refund_success(
                refund=refund,
                booking=booking,
                contribution=contribution,
                provider_trans_id=provider_trans_id,
                current_utc=current_utc,
            )
            touched_booking_ids.add(booking.id)
            succeeded += 1
        elif result_code == "7002":
            refund.status = RefundStatus.PROCESSING.value
        else:
            refund.status = RefundStatus.FAILED.value

    for current_booking_id in touched_booking_ids:
        booking = db.session.get(Booking, current_booking_id)
        if (
            booking is not None
            and booking.status == BookingStatus.REFUND_PENDING.value
            and _all_booking_refunds_succeeded(booking.id)
        ):
            _finish_cancelled_booking(booking, current_utc=current_utc)
    commit_refunds("Không thể cập nhật kết quả hoàn tiền MoMo.")
    return succeeded


def _parse_refund_query(order_id: str, response: dict) -> tuple[str, str | None]:
    if str(response.get("resultCode", "")) != "0":
        return str(response.get("resultCode", "")), None
    for item in response.get("refundTrans") or []:
        if str(item.get("orderId", "")) == order_id:
            return (
                str(item.get("resultCode", "")),
                str(item.get("transId", "")) or None,
            )
    return "7002", None


def _all_booking_refunds_succeeded(booking_id: int) -> bool:
    incomplete = db.session.scalar(
        db.select(db.func.count(Refund.id)).where(
            Refund.booking_id == booking_id,
            Refund.status != RefundStatus.SUCCESS.value,
        )
    )
    return int(incomplete or 0) == 0


def _refund_collected_payments(
    *,
    booking: Booking,
    current_utc: datetime,
    policy_key: str,
    reason: str,
    creator_rate: Decimal,
) -> list[Refund]:
    payments = list(
        db.session.scalars(
            with_update_lock(
                db.select(Payment)
                .where(
                    Payment.booking_id == booking.id,
                    Payment.status == PaymentStatus.SUCCESS.value,
                )
                .order_by(Payment.id),
                Payment,
            )
        )
    )
    refunds: list[Refund] = []
    for payment in payments:
        contribution = db.session.get(BookingContribution, payment.contribution_id)
        if contribution is None:
            raise InvalidRefundStateError("Giao dịch không còn khoản đóng góp gốc.")
        refundable = _remaining_refundable_amount(payment)
        if refundable <= 0:
            continue
        rate = (
            creator_rate
            if contribution.contribution_type
            in {ContributionType.CREATOR.value, ContributionType.TOP_UP.value}
            else Decimal("1.00")
        )
        amount = (refundable * rate).quantize(MONEY_QUANTUM, ROUND_HALF_UP)
        if amount <= 0:
            continue
        contribution.status = ContributionStatus.REFUND_PENDING.value
        refund, _ = _record_refund(
            booking=booking,
            contribution=contribution,
            payment=payment,
            amount=amount,
            reason=reason,
            operation_key=f"{policy_key}-{payment.id}",
            current_utc=current_utc,
        )
        refunds.append(refund)
    return refunds


def _record_refund(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payment: Payment,
    amount: Decimal,
    reason: str,
    operation_key: str,
    current_utc: datetime,
) -> tuple[Refund, bool]:
    order_id = f"{payment.provider}-REFUND-{operation_key}"
    existing = db.session.scalar(db.select(Refund).where(Refund.order_id == order_id))
    if existing is not None:
        return existing, False

    amount = Decimal(amount).quantize(MONEY_QUANTUM)
    if amount <= 0 or amount > _remaining_refundable_amount(payment):
        raise InvalidRefundStateError("Số tiền hoàn không hợp lệ.")
    if amount > Decimal(contribution.amount_paid):
        raise InvalidRefundStateError("Số tiền hoàn vượt khoản đóng góp còn hiệu lực.")
    if amount > Decimal(booking.paid_amount):
        raise InvalidRefundStateError("Số tiền hoàn vượt số tiền lịch đặt đang ghi nhận.")

    is_mock = payment.provider == PaymentProvider.MOCK.value
    refund = Refund(
        booking_id=booking.id,
        payment_id=payment.id,
        recipient_id=payment.payer_id,
        amount=amount,
        reason=reason,
        order_id=order_id,
        request_id=uuid4().hex,
        provider_refund_trans_id=(
            f"MOCK-REFUND-TRANS-{uuid4().hex.upper()}" if is_mock else None
        ),
        status=(
            RefundStatus.SUCCESS.value if is_mock else RefundStatus.PENDING.value
        ),
        result_code="0" if is_mock else None,
        refunded_at=current_utc if is_mock else None,
    )
    db.session.add(refund)
    if not is_mock:
        return refund, True
    _apply_refund_success(
        refund=refund,
        booking=booking,
        contribution=contribution,
        provider_trans_id=refund.provider_refund_trans_id,
        current_utc=current_utc,
    )
    return refund, True


def _apply_refund_success(
    *,
    refund: Refund,
    booking: Booking,
    contribution: BookingContribution,
    provider_trans_id: str | None,
    current_utc: datetime,
) -> None:
    amount = Decimal(refund.amount)
    contribution.amount_paid = (
        Decimal(contribution.amount_paid) - amount
    ).quantize(MONEY_QUANTUM)
    contribution.status = (
        ContributionStatus.REFUNDED.value
        if Decimal(contribution.amount_paid) == 0
        else ContributionStatus.PARTIALLY_REFUNDED.value
    )
    booking.paid_amount = (Decimal(booking.paid_amount) - amount).quantize(
        MONEY_QUANTUM
    )
    refund.provider_refund_trans_id = provider_trans_id
    refund.status = RefundStatus.SUCCESS.value
    refund.result_code = "0"
    refund.refunded_at = current_utc


def _remaining_refundable_amount(payment: Payment) -> Decimal:
    refunded = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Refund.amount), 0)).where(
            Refund.payment_id == payment.id,
            Refund.status.in_(
                (
                    RefundStatus.PENDING.value,
                    RefundStatus.PROCESSING.value,
                    RefundStatus.SUCCESS.value,
                )
            ),
        )
    )
    return (Decimal(payment.amount) - Decimal(refunded or 0)).quantize(MONEY_QUANTUM)


def _lock_successful_payment(contribution_id: int) -> Payment | None:
    return db.session.scalar(
        with_update_lock(
            db.select(Payment).where(
                Payment.contribution_id == contribution_id,
                Payment.status == PaymentStatus.SUCCESS.value,
            ),
            Payment,
        )
    )


def _finish_cancelled_booking(
    booking: Booking,
    *,
    current_utc: datetime,
) -> None:
    pending_contributions = db.session.scalars(
        db.select(BookingContribution).where(
            BookingContribution.booking_id == booking.id,
            BookingContribution.status.in_(
                (ContributionStatus.PENDING.value, ContributionStatus.EXPIRED.value)
            ),
        )
    )
    for contribution in pending_contributions:
        contribution.status = ContributionStatus.WAIVED.value
        contribution.expires_at = None
    if booking.match is not None:
        unresolved_participants = db.session.scalars(
            db.select(MatchParticipant).where(
                MatchParticipant.match_id == booking.match.id,
                MatchParticipant.status.in_(
                    (
                        MatchParticipantStatus.PENDING.value,
                        MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
                    )
                ),
            )
        )
        for participant in unresolved_participants:
            participant.status = MatchParticipantStatus.REJECTED.value
            participant.decided_at = current_utc
            participant.payment_due_at = None
        booking.match.status = MatchStatus.CANCELLED.value
    booking.status = BookingStatus.CANCELLED.value


def normalize_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def commit_refunds(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise RefundError(message) from exc
