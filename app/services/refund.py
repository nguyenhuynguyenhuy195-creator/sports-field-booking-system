from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.integrations import MomoAPIError, MomoClient, VnpayClient, VnpayError
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
from .maintenance import VIETNAM_TIMEZONE


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
    """Cancel the booking immediately and queue a 100% refund of every net
    collected payment for an owner cancellation.

    Cancellation (releasing the field slot, closing the match, waiving any
    still-unpaid contributions) happens right away and is never gated on the
    refund actually completing — VNPAY/MoMo refunds are asynchronous and can
    stay PENDING/PROCESSING for a while. See _apply_refund_success for the
    separate financial step (reducing paid_amount/amount_paid) that only
    runs once a Refund actually reaches SUCCESS.
    """
    current_utc = normalize_utc(now)
    booking.cancellation_reason = reason
    booking.cancellation_fee_amount = Decimal("0.00")
    refunds = _refund_collected_payments(
        booking=booking,
        current_utc=current_utc,
        policy_key="OWNER-CANCEL",
        reason=f"Chủ sân hủy do sự cố: {reason}",
        creator_rate=Decimal("1.00"),
    )
    _cancel_booking_now(booking, current_utc=current_utc)
    return refunds


def apply_creator_cancellation_policy(
    *,
    booking: Booking,
    reason: str,
    now: datetime | None = None,
) -> list[Refund]:
    """Cancel the booking immediately, forfeit creator money, and queue a
    100% refund of active opponent money. See apply_owner_cancellation_refunds
    for why cancellation cleanup is never gated on refund completion.
    """
    current_utc = normalize_utc(now)
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
    _cancel_booking_now(booking, current_utc=current_utc)
    return refunds


def apply_funding_shortfall_refunds(
    *,
    booking: Booking,
    reason: str,
    now: datetime | None = None,
) -> list[Refund]:
    """Cancel an underfunded booking immediately; refund creator 80%, other
    payers 100%, and retain the creator's 20%. See
    apply_owner_cancellation_refunds for why cancellation cleanup is never
    gated on refund completion.
    """
    if booking.booking_mode != BookingMode.FIND_OPPONENT.value:
        raise InvalidRefundStateError(
            "Chính sách thiếu tiền chỉ áp dụng cho lịch đặt có nhiều người đóng."
        )
    current_utc = normalize_utc(now)
    paid_before_refunds = Decimal(booking.paid_amount)
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
    _cancel_booking_now(booking, current_utc=current_utc)
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
        process_pending_provider_refunds(now=current_utc)
    return len(bookings)


def process_pending_momo_refunds(
    *,
    booking_id: int | None = None,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> int:
    """Submit/query pending MoMo refunds and finalize successful records."""
    if not current_app.config.get("MOMO_ENABLED"):
        return 0
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
                payment=payment,
                booking=booking,
                contribution=contribution,
                provider_trans_id=provider_trans_id,
                current_utc=current_utc,
            )
            succeeded += 1
        elif result_code == "7002":
            refund.status = RefundStatus.PROCESSING.value
        else:
            refund.status = RefundStatus.FAILED.value

    commit_refunds("Không thể cập nhật kết quả hoàn tiền MoMo.")
    return succeeded


def process_pending_vnpay_refunds(
    *,
    booking_id: int | None = None,
    client: VnpayClient | None = None,
    now: datetime | None = None,
) -> int:
    """Submit durable VNPAY Sandbox refund records to the real VNPAY refund
    API, ONE REFUND AT A TIME, each locked, submitted, and persisted (or
    rolled back) independently in its own commit.

    This matters because VNPAY refunds are external, irreversible actions:
    if Refund A gets a verified SUCCESS and Refund B then hits a network
    error, a single shared commit at the end of the batch would roll BOTH
    back on B's failure — silently erasing our record of money VNPAY has
    already returned, and risking a duplicate submission for A on retry.
    Committing per refund makes that impossible: once A's outcome is
    committed, nothing that happens to B (or C, D, ...) afterward can touch
    it, and B is left safely retryable with the same request_id.
    """
    if not current_app.config.get("VNPAY_ENABLED"):
        return 0
    id_statement = (
        db.select(Refund.id)
        .join(Refund.payment)
        .where(
            Payment.provider == PaymentProvider.VNPAY.value,
            Refund.status.in_(
                (RefundStatus.PENDING.value, RefundStatus.PROCESSING.value)
            ),
        )
        .order_by(Refund.id)
    )
    if booking_id is not None:
        id_statement = id_statement.where(Refund.booking_id == booking_id)
    refund_ids = list(db.session.scalars(id_statement))
    if not refund_ids:
        return 0

    try:
        vnpay = client or VnpayClient.from_app_config()
    except VnpayError as exc:
        raise RefundError(str(exc)) from exc

    succeeded = 0
    for refund_id in refund_ids:
        if _process_one_pending_vnpay_refund(refund_id, vnpay=vnpay, now=now):
            succeeded += 1
    return succeeded


def _process_one_pending_vnpay_refund(
    refund_id: int,
    *,
    vnpay: VnpayClient,
    now: datetime | None,
) -> bool:
    """Lock, submit, and persist the outcome of exactly one VNPAY Refund,
    committing (or rolling back) before returning. Returns True only if this
    refund reached SUCCESS during this call.
    """
    refund = db.session.scalar(
        with_update_lock(db.select(Refund).where(Refund.id == refund_id), Refund)
    )
    if refund is None or refund.status not in {
        RefundStatus.PENDING.value,
        RefundStatus.PROCESSING.value,
    }:
        # Already handled (by this same batch's earlier iteration reusing a
        # stale id, or a concurrent call) since the id list was read.
        db.session.rollback()
        return False

    if refund.status == RefundStatus.PROCESSING.value:
        # VNPAY has no official "query a specific refund" endpoint —
        # querydr reports the ORIGINAL PAYMENT transaction, which by
        # this point already shows success and cannot be used to tell
        # whether THIS refund specifically completed. Resubmitting
        # blindly could double-refund. Leave it durable; an operator
        # can reconcile it manually against the VNPAY merchant portal.
        db.session.rollback()
        return False

    payment = refund.payment
    current_utc = normalize_utc(now)
    if not payment.provider_trans_id:
        refund.status = RefundStatus.FAILED.value
        refund.result_code = "MISSING_TRANS_ID"
        commit_refunds("Không thể cập nhật kết quả hoàn tiền VNPAY.")
        return False

    try:
        response = vnpay.refund(
            request_id=_valid_vnpay_refund_request_id(refund.request_id),
            txn_ref=payment.order_id,
            amount=Decimal(refund.amount),
            transaction_no=payment.provider_trans_id,
            transaction_date=_original_vnpay_transaction_date(payment),
            create_date=_vnpay_refund_create_date(current_utc),
            ip_addr=current_app.config.get("VNPAY_REFUND_IP_ADDR", "127.0.0.1"),
            order_info=f"Hoan tien giao dich {payment.order_id}",
            full_refund=_refund_is_full_original_amount(refund, payment),
            create_by=current_app.config.get("VNPAY_REFUND_CREATE_BY", "system"),
            version=current_app.config.get("VNPAY_VERSION", "2.1.0"),
        )
    except VnpayError:
        # Network/API failure for THIS refund only. Nothing has been
        # persisted for it yet, so a plain rollback leaves it exactly as it
        # was — still PENDING, same request_id — safely retryable later,
        # without touching any other refund's already-committed outcome.
        db.session.rollback()
        return False

    response_code = str(response.get("vnp_ResponseCode", ""))
    transaction_status = str(response.get("vnp_TransactionStatus", ""))
    provider_trans_id = str(response.get("vnp_TransactionNo", "")) or None
    refund.result_code = response_code

    succeeded = False
    if response_code == "00" and transaction_status == "00":
        contribution = payment.contribution
        booking = refund.booking
        _apply_refund_success(
            refund=refund,
            payment=payment,
            booking=booking,
            contribution=contribution,
            provider_trans_id=provider_trans_id,
            current_utc=current_utc,
        )
        succeeded = True
    elif response_code == "00" and transaction_status in {"05", "06"}:
        refund.status = RefundStatus.PROCESSING.value
    elif response_code == "94":
        # VNPAY: refund request already received and is being processed
        # (e.g. a duplicate submission while the earlier one is still in
        # flight) — not a rejection. Leave it durable for reconciliation,
        # same as the "05"/"06" transactionStatus case above.
        refund.status = RefundStatus.PROCESSING.value
    else:
        refund.status = RefundStatus.FAILED.value

    commit_refunds("Không thể cập nhật kết quả hoàn tiền VNPAY.")
    return succeeded


def process_pending_provider_refunds(
    *,
    booking_id: int | None = None,
    now: datetime | None = None,
) -> int:
    """Best-effort attempt at every provider's durable pending refunds.

    Generalizes the old MoMo-only "attempt after cancellation commit" step
    so VNPAY refunds get the same treatment. Each provider is tried
    independently: a failure reaching one gateway (network error, bad
    config) never blocks the attempt at the other, and never erases the
    durable Refund(PENDING) row either way — it can always be retried
    later (by this same function or the refunds CLI).
    """
    succeeded = 0
    for attempt in (process_pending_vnpay_refunds, process_pending_momo_refunds):
        try:
            succeeded += attempt(booking_id=booking_id, now=now)
        except RefundError:
            db.session.rollback()
    return succeeded


def _refund_is_full_original_amount(refund: Refund, payment: Payment) -> bool:
    """True only when `refund` refunds the FULL original Payment amount and
    no other accepted/successful refund exists for that Payment — VNPAY's
    "full" refund (vnp_TransactionType 02). Anything else — a partial amount,
    or a refund that only completes what an earlier refund left over — is a
    "partial" refund (03), even if it happens to exhaust what remains.

    A funding-shortfall refund (80% of the payment) never qualifies, since
    its amount is less than the original payment amount. And a second refund
    that finishes off a payment already partially refunded never qualifies
    either, even if its amount equals the remaining balance, because a prior
    accepted refund already exists for this payment.
    """
    if Decimal(refund.amount) != Decimal(payment.amount):
        return False
    other_accepted_refund_exists = db.session.scalar(
        db.select(db.func.count(Refund.id)).where(
            Refund.payment_id == payment.id,
            Refund.id != refund.id,
            Refund.status.in_(
                (
                    RefundStatus.PENDING.value,
                    RefundStatus.PROCESSING.value,
                    RefundStatus.SUCCESS.value,
                )
            ),
        )
    )
    return int(other_accepted_refund_exists or 0) == 0


def _valid_vnpay_refund_request_id(request_id: str) -> str:
    """Refund.request_id is already uuid4().hex (32 alphanumeric chars),
    which satisfies VNPAY's vnp_RequestId limit (max 32 alphanumeric) as-is.
    Regenerate defensively only if it somehow isn't valid.
    """
    if request_id and len(request_id) <= 32 and request_id.isalnum():
        return request_id
    return uuid4().hex


def _original_vnpay_transaction_date(payment: Payment) -> str:
    """The original PAY request's vnp_CreateDate (GMT+7, yyyyMMddHHmmss).

    Prefers parsing it back out of the checkout_url we ourselves signed at
    PAY time (see payment.py:_vnpay_create_date) so it exactly matches what
    VNPAY has on file for the original transaction. Falls back to deriving
    one from paid_at/created_at only if the URL is missing or unparsable.
    """
    checkout_url = payment.checkout_url
    if checkout_url:
        query = parse_qs(urlsplit(checkout_url).query)
        values = query.get("vnp_CreateDate")
        if values and len(values[0]) == 14 and values[0].isdigit():
            return values[0]
    reference = payment.paid_at or payment.created_at
    vn_time = reference.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TIMEZONE)
    return vn_time.strftime("%Y%m%d%H%M%S")


def _vnpay_refund_create_date(current_utc: datetime) -> str:
    """vnp_CreateDate for the refund REQUEST itself (now, GMT+7)."""
    vn_time = current_utc.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TIMEZONE)
    return vn_time.strftime("%Y%m%d%H%M%S")


def queue_late_momo_payment_refund(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payment: Payment,
    now: datetime | None = None,
) -> Refund:
    """Queue a verified provider success that arrived after the obligation closed."""
    if (
        payment.provider != PaymentProvider.MOMO.value
        or payment.status != PaymentStatus.EXPIRED.value
        or payment.result_code != "0"
        or not payment.provider_trans_id
    ):
        raise InvalidRefundStateError(
            "Giao dịch đến muộn chưa có đủ dữ liệu MoMo để hoàn tiền."
        )
    refund, _ = _record_refund(
        booking=booking,
        contribution=contribution,
        payment=payment,
        amount=Decimal(payment.amount),
        reason=(
            "MoMo xác nhận thanh toán sau khi khoản cọc đã hết hiệu lực; "
            "hoàn lại toàn bộ cho người trả."
        ),
        operation_key=f"LATE-PAYMENT-{payment.id}",
        current_utc=normalize_utc(now),
        require_recorded_balance=False,
    )
    return refund


def queue_late_vnpay_payment_refund(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payment: Payment,
    now: datetime | None = None,
) -> Refund:
    """Queue a verified VNPAY success that arrived after the obligation closed.

    Step 3 only queues the Refund as PENDING; submitting it to VNPAY's
    refund API is Step 6 (process_pending_vnpay_refunds).
    """
    if (
        payment.provider != PaymentProvider.VNPAY.value
        or payment.status != PaymentStatus.EXPIRED.value
        or payment.result_code != "00"
        or not payment.provider_trans_id
    ):
        raise InvalidRefundStateError(
            "Giao dịch VNPAY đến muộn chưa có đủ dữ liệu để hoàn tiền."
        )
    refund, _ = _record_refund(
        booking=booking,
        contribution=contribution,
        payment=payment,
        amount=Decimal(payment.amount),
        reason=(
            "VNPAY xác nhận thanh toán sau khi khoản cọc đã hết hiệu lực; "
            "hoàn lại toàn bộ cho người trả."
        ),
        operation_key=f"LATE-PAYMENT-{payment.id}",
        current_utc=normalize_utc(now),
        require_recorded_balance=False,
    )
    return refund


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
    require_recorded_balance: bool = True,
) -> tuple[Refund, bool]:
    order_id = f"{payment.provider}-REFUND-{operation_key}"
    existing = db.session.scalar(db.select(Refund).where(Refund.order_id == order_id))
    if existing is not None:
        return existing, False

    amount = Decimal(amount).quantize(MONEY_QUANTUM)
    if amount <= 0 or amount > _remaining_refundable_amount(payment):
        raise InvalidRefundStateError("Số tiền hoàn không hợp lệ.")
    if require_recorded_balance and amount > Decimal(contribution.amount_paid):
        raise InvalidRefundStateError("Số tiền hoàn vượt khoản đóng góp còn hiệu lực.")
    if require_recorded_balance and amount > Decimal(booking.paid_amount):
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
        payment=payment,
        booking=booking,
        contribution=contribution,
        provider_trans_id=refund.provider_refund_trans_id,
        current_utc=current_utc,
    )
    return refund, True


def _apply_refund_success(
    *,
    refund: Refund,
    payment: Payment,
    booking: Booking,
    contribution: BookingContribution,
    provider_trans_id: str | None,
    current_utc: datetime,
) -> None:
    amount = Decimal(refund.amount)
    # Late-success sentinel is provider-specific: MoMo's is "0", VNPAY's is
    # "00" (see _record_late_momo_success_for_refund /
    # _record_late_vnpay_success_for_refund in payment.py). Hardcoding "0"
    # here would never match a VNPAY late payment, so a VNPAY refund for
    # money that was NEVER added to booking.paid_amount/contribution
    # would incorrectly subtract it anyway — a real accounting bug.
    late_success_code = (
        "00" if payment.provider == PaymentProvider.VNPAY.value else "0"
    )
    rejected_late_payment = bool(
        payment.status == PaymentStatus.EXPIRED.value
        and payment.result_code == late_success_code
        and payment.provider_trans_id
    )
    if not rejected_late_payment:
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
    # result_code is provider-specific ("0" for MoMo/MOCK, "00" for VNPAY) and
    # is always set by the caller before invoking this function — do not
    # overwrite it here with a MoMo-only sentinel.
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


def _cancel_booking_now(
    booking: Booking,
    *,
    current_utc: datetime,
) -> None:
    """Immediate cancellation cleanup — always runs the moment a valid
    cancellation is accepted, independent of whether any queued Refund has
    actually completed with the provider yet:
    - booking becomes CANCELLED (releasing its field time slot immediately —
      CANCELLED is not an occupying status)
    - any contribution nobody ever paid is waived, not left dangling
    - an attached match and its unresolved participants are closed

    This is deliberately separate from the FINANCIAL side of a refund
    (reducing booking.paid_amount / contribution.amount_paid, marking a
    contribution REFUNDED) — that only ever happens in _apply_refund_success,
    once a Refund actually reaches SUCCESS.
    """
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
