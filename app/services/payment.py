from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.integrations import MomoAPIError, MomoClient
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
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


@dataclass(frozen=True)
class MomoCheckout:
    payment: Payment
    pay_url: str


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
        raise PaymentPermissionError("Chỉ người đặt sân được trả phần còn thiếu.")
    if booking.status != BookingStatus.PARTIALLY_PAID.value:
        raise InvalidPaymentStateError(
            "Chỉ lịch đặt đã thanh toán một phần mới có thể trả phần còn thiếu."
        )
    if booking.booking_mode != BookingMode.FIND_OPPONENT.value:
        raise InvalidPaymentStateError(
            "Chỉ lịch đặt tìm đối thủ mới có phần cọc cần trả bổ sung."
        )
    if booking.funding_deadline is None or booking.funding_deadline <= current_utc:
        raise PaymentExpiredError("Đã hết hạn đóng đủ tiền cho lịch đặt này.")
    if (
        booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
        and booking.matchmaking_deadline is not None
        and current_utc < booking.matchmaking_deadline
    ):
        raise InvalidPaymentStateError(
            "Chỉ có thể trả phần cọc đối thủ còn thiếu trong cửa sổ 30 phút."
        )

    remaining = Decimal(booking.deposit_amount) - Decimal(booking.paid_amount)
    if remaining <= 0:
        raise InvalidPaymentStateError("Lịch đặt sân đã được thanh toán đủ.")

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
    from .matchmaking import join_waived_match_participants

    join_waived_match_participants(
        booking_id=booking.id,
        joined_at=current_utc,
    )
    _commit_payment()
    return payment


def start_momo_payment(
    *,
    booking_code: str,
    contribution_id: int,
    payer: User,
    redirect_url: str,
    ipn_url: str,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> MomoCheckout:
    """Create or resume one MoMo Sandbox checkout for a contribution."""
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
    return _start_momo_checkout(
        booking=booking,
        contribution=contribution,
        payer=payer,
        redirect_url=redirect_url,
        ipn_url=ipn_url,
        client=client,
    )


def start_momo_top_up(
    *,
    booking_code: str,
    payer: User,
    redirect_url: str,
    ipn_url: str,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> MomoCheckout:
    """Create the creator's 30-minute opponent-deposit top-up checkout."""
    _validate_payer(payer)
    current_utc = _normalize_utc(now)
    booking = _lock_booking(booking_code)
    _validate_top_up(booking=booking, payer=payer, current_utc=current_utc)

    top_up = db.session.scalar(
        with_update_lock(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id,
                BookingContribution.user_id == payer.id,
                BookingContribution.contribution_type == ContributionType.TOP_UP.value,
                BookingContribution.status == ContributionStatus.PENDING.value,
            ),
            BookingContribution,
        )
    )
    if top_up is None:
        remaining = Decimal(booking.deposit_amount) - Decimal(booking.paid_amount)
        pending_records = list(
            db.session.scalars(
                with_update_lock(
                    db.select(BookingContribution).where(
                        BookingContribution.booking_id == booking.id,
                        BookingContribution.status == ContributionStatus.PENDING.value,
                    ),
                    BookingContribution,
                )
            )
        )
        for record in pending_records:
            if record.contribution_type != ContributionType.CREATOR.value:
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

    return _start_momo_checkout(
        booking=booking,
        contribution=top_up,
        payer=payer,
        redirect_url=redirect_url,
        ipn_url=ipn_url,
        client=client,
    )


def process_momo_payment_notification(
    payload: dict,
    *,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> Payment:
    """Verify and apply a server-to-server IPN idempotently."""
    momo = client or MomoClient.from_app_config()
    current_utc = _normalize_utc(now)
    payment = _verified_momo_payment(
        payload=payload,
        momo=momo,
        lock_for_update=True,
    )

    result_code = str(payload.get("resultCode", ""))
    provider_trans_id = str(payload.get("transId", "")) or None
    if _provider_success_was_recorded(payment):
        if provider_trans_id != payment.provider_trans_id:
            raise PaymentError("Mã giao dịch MoMo không khớp lần xử lý trước.")
        return payment
    if payment.status != PaymentStatus.PENDING.value:
        return payment
    payment.result_code = result_code
    if result_code != "0":
        payment.status = PaymentStatus.FAILED.value
        _commit_payment()
        return payment
    if not provider_trans_id:
        raise PaymentError("MoMo không trả mã giao dịch thành công.")

    booking = _lock_booking_by_id(payment.booking_id)
    contribution = _lock_contribution(
        booking_id=booking.id,
        contribution_id=payment.contribution_id,
    )
    payable_state_changed = (
        booking.status
        not in {
            BookingStatus.CONFIRMED.value,
            BookingStatus.PARTIALLY_PAID.value,
        }
        or contribution.status != ContributionStatus.PENDING.value
        or contribution.user_id != payment.payer_id
    )
    deadline_expired = False
    if not payable_state_changed:
        deadline_expired = _expire_overdue_contribution(
            booking=booking,
            contribution=contribution,
            current_utc=current_utc,
        )
    if payable_state_changed or deadline_expired:
        _record_late_momo_success_for_refund(
            payment=payment,
            booking=booking,
            contribution=contribution,
            provider_trans_id=provider_trans_id,
            paid_at=current_utc,
        )
        _commit_payment()
        return payment
    _apply_success_to_payment(
        payment=payment,
        booking=booking,
        contribution=contribution,
        provider_trans_id=provider_trans_id,
        paid_at=current_utc,
    )
    _commit_payment()
    return payment


def inspect_momo_return(
    payload: dict,
    *,
    client: MomoClient | None = None,
) -> Payment:
    """Verify a browser return and read its payment without changing state."""
    momo = client or MomoClient.from_app_config()
    return _verified_momo_payment(
        payload=payload,
        momo=momo,
        lock_for_update=False,
    )


def _verified_momo_payment(
    *,
    payload: dict,
    momo: MomoClient,
    lock_for_update: bool,
) -> Payment:
    try:
        momo.verify_payment_notification(payload)
    except MomoAPIError as exc:
        raise PaymentError(str(exc)) from exc

    order_id = str(payload.get("orderId", ""))
    statement = db.select(Payment).where(
        Payment.order_id == order_id,
        Payment.provider == PaymentProvider.MOMO.value,
    )
    if lock_for_update:
        statement = with_update_lock(statement, Payment)
    payment = db.session.scalar(statement)
    if payment is None:
        raise PaymentNotFoundError("Không tìm thấy giao dịch MoMo.")
    if str(payload.get("requestId", "")) != payment.request_id:
        raise PaymentError("Mã yêu cầu MoMo không khớp giao dịch.")
    try:
        callback_amount = Decimal(str(payload.get("amount", "")))
    except Exception as exc:
        raise PaymentError("Số tiền callback MoMo không hợp lệ.") from exc
    if callback_amount != Decimal(payment.amount):
        raise PaymentError("Số tiền callback MoMo không khớp giao dịch.")
    return payment


def _start_momo_checkout(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payer: User,
    redirect_url: str,
    ipn_url: str,
    client: MomoClient | None,
) -> MomoCheckout:
    momo = client or MomoClient.from_app_config()
    existing = db.session.scalar(
        db.select(Payment)
        .where(
            Payment.contribution_id == contribution.id,
            Payment.provider == PaymentProvider.MOMO.value,
            Payment.status == PaymentStatus.PENDING.value,
        )
        .order_by(Payment.id.desc())
    )
    if existing is not None:
        if existing.checkout_url:
            return MomoCheckout(payment=existing, pay_url=existing.checkout_url)
        payment = existing
    else:
        payment = Payment(
            booking_id=booking.id,
            contribution_id=contribution.id,
            payer_id=payer.id,
            provider=PaymentProvider.MOMO.value,
            payment_method=PaymentMethod.MOMO_WALLET.value,
            amount=contribution.remaining_amount,
            order_id=f"MOMO-PAY-{booking.id}-{uuid4().hex[:16].upper()}",
            request_id=uuid4().hex,
            provider_trans_id=None,
            status=PaymentStatus.PENDING.value,
            result_code=None,
        )
        db.session.add(payment)
        _commit_payment()

    try:
        response = momo.create_payment(
            order_id=payment.order_id,
            request_id=payment.request_id,
            amount=Decimal(payment.amount),
            order_info=f"Cọc lịch đặt sân {booking.booking_code}",
            redirect_url=redirect_url,
            ipn_url=ipn_url,
        )
    except MomoAPIError as exc:
        raise PaymentError(str(exc)) from exc
    if (
        str(response.get("orderId", "")) != payment.order_id
        or str(response.get("requestId", "")) != payment.request_id
    ):
        raise PaymentError("MoMo trả về sai mã giao dịch.")
    payment.result_code = str(response.get("resultCode", ""))
    if payment.result_code != "0" or not response.get("payUrl"):
        payment.status = PaymentStatus.FAILED.value
        _commit_payment()
        raise PaymentError(
            str(response.get("message") or "MoMo từ chối tạo giao dịch.")
        )
    payment.checkout_url = str(response["payUrl"])
    _commit_payment()
    return MomoCheckout(payment=payment, pay_url=payment.checkout_url)


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
    if new_paid_amount > Decimal(booking.deposit_amount):
        raise InvalidPaymentStateError("Giao dịch sẽ làm tổng tiền vượt khoản cọc.")

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
        if new_paid_amount == Decimal(booking.deposit_amount)
        else BookingStatus.PARTIALLY_PAID.value
    )
    from .matchmaking import mark_participant_joined_after_payment

    mark_participant_joined_after_payment(
        contribution,
        paid_at=current_utc,
    )
    return payment


def _apply_success_to_payment(
    *,
    payment: Payment,
    booking: Booking,
    contribution: BookingContribution,
    provider_trans_id: str,
    paid_at: datetime,
) -> None:
    amount = Decimal(payment.amount)
    if amount != contribution.remaining_amount:
        raise InvalidPaymentStateError(
            "Số tiền MoMo không còn khớp khoản cọc phải trả."
        )
    new_paid_amount = Decimal(booking.paid_amount) + amount
    if new_paid_amount > Decimal(booking.deposit_amount):
        raise InvalidPaymentStateError("Giao dịch sẽ làm tổng tiền vượt khoản cọc.")

    payment.provider_trans_id = provider_trans_id
    payment.status = PaymentStatus.SUCCESS.value
    payment.paid_at = paid_at
    contribution.amount_paid = Decimal(contribution.amount_due)
    contribution.status = ContributionStatus.PAID.value
    contribution.expires_at = None
    booking.paid_amount = new_paid_amount
    booking.status = (
        BookingStatus.PAID.value
        if new_paid_amount == Decimal(booking.deposit_amount)
        else BookingStatus.PARTIALLY_PAID.value
    )

    from .matchmaking import (
        join_waived_match_participants,
        mark_participant_joined_after_payment,
    )

    mark_participant_joined_after_payment(contribution, paid_at=paid_at)
    if contribution.contribution_type == ContributionType.TOP_UP.value:
        join_waived_match_participants(
            booking_id=booking.id,
            joined_at=paid_at,
        )


def _record_late_momo_success_for_refund(
    *,
    payment: Payment,
    booking: Booking,
    contribution: BookingContribution,
    provider_trans_id: str,
    paid_at: datetime,
) -> None:
    """Preserve provider success without applying late money to the booking."""
    payment.provider_trans_id = provider_trans_id
    payment.status = PaymentStatus.EXPIRED.value
    payment.paid_at = paid_at

    from .refund import RefundError, queue_late_momo_payment_refund

    try:
        queue_late_momo_payment_refund(
            booking=booking,
            contribution=contribution,
            payment=payment,
            now=paid_at,
        )
    except RefundError as exc:
        db.session.rollback()
        raise PaymentError(
            "Không thể ghi nhận giao dịch đến muộn để hoàn tiền."
        ) from exc


def _provider_success_was_recorded(payment: Payment) -> bool:
    return bool(
        payment.status == PaymentStatus.SUCCESS.value
        or (
            payment.status == PaymentStatus.EXPIRED.value
            and payment.result_code == "0"
            and payment.provider_trans_id
        )
    )


def _validate_top_up(
    *,
    booking: Booking,
    payer: User,
    current_utc: datetime,
) -> None:
    if booking.user_id != payer.id:
        raise PaymentPermissionError("Chỉ người đặt sân được trả phần còn thiếu.")
    if booking.status != BookingStatus.PARTIALLY_PAID.value:
        raise InvalidPaymentStateError(
            "Chỉ lịch đặt đã thanh toán một phần mới có thể trả phần còn thiếu."
        )
    if booking.booking_mode != BookingMode.FIND_OPPONENT.value:
        raise InvalidPaymentStateError(
            "Chỉ lịch đặt tìm đối thủ mới có phần cọc cần trả bổ sung."
        )
    if booking.funding_deadline is None or booking.funding_deadline <= current_utc:
        raise PaymentExpiredError("Đã hết hạn đóng đủ tiền cho lịch đặt này.")
    if (
        booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
        and booking.matchmaking_deadline is not None
        and current_utc < booking.matchmaking_deadline
    ):
        raise InvalidPaymentStateError(
            "Chỉ có thể trả phần cọc đối thủ còn thiếu trong cửa sổ 30 phút."
        )
    if Decimal(booking.deposit_amount) - Decimal(booking.paid_amount) <= 0:
        raise InvalidPaymentStateError("Lịch đặt sân đã được thanh toán đủ.")


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
        raise InvalidPaymentStateError("Lịch đặt sân hiện không thể nhận thanh toán.")
    if contribution.status != ContributionStatus.PENDING.value:
        raise InvalidPaymentStateError("Khoản đóng góp đã được xử lý.")
    if _expire_overdue_contribution(
        booking=booking,
        contribution=contribution,
        current_utc=current_utc,
    ):
        _commit_payment()
        raise PaymentExpiredError("Khoản thanh toán đã hết hạn.")


def _expire_overdue_contribution(
    *,
    booking: Booking,
    contribution: BookingContribution,
    current_utc: datetime,
) -> bool:
    initial_hold_expired = bool(
        booking.status == BookingStatus.CONFIRMED.value
        and Decimal(booking.paid_amount) == Decimal("0.00")
        and booking.initial_payment_due_at is not None
        and booking.initial_payment_due_at <= current_utc
    )
    contribution_expired = bool(
        contribution.expires_at is not None
        and contribution.expires_at <= current_utc
    )
    if not initial_hold_expired and not contribution_expired:
        return False

    if initial_hold_expired:
        booking.status = BookingStatus.EXPIRED.value
        pending_contributions = list(
            db.session.scalars(
                with_update_lock(
                    db.select(BookingContribution).where(
                        BookingContribution.booking_id == booking.id,
                        BookingContribution.status
                        == ContributionStatus.PENDING.value,
                    ),
                    BookingContribution,
                )
            )
        )
        for pending in pending_contributions:
            pending.status = ContributionStatus.EXPIRED.value
        return True

    from .matchmaking import expire_participant_for_contribution

    participant_expired = expire_participant_for_contribution(
        contribution,
        now=current_utc,
    )
    if not participant_expired:
        contribution.status = ContributionStatus.EXPIRED.value
    return True


def _lock_booking(booking_code: str) -> Booking:
    statement = with_update_lock(
        db.select(Booking).where(Booking.booking_code == booking_code),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking is None:
        raise PaymentNotFoundError("Không tìm thấy lịch đặt sân.")
    return booking


def _lock_booking_by_id(booking_id: int) -> Booking:
    statement = with_update_lock(
        db.select(Booking).where(Booking.id == booking_id),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking is None:
        raise PaymentNotFoundError("Không tìm thấy lịch đặt sân.")
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
