from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.integrations import (
    MomoAPIError,
    MomoClient,
    VnpayClient,
    VnpayError,
    VnpaySignatureError,
    to_vnpay_amount,
)
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
from .maintenance import VIETNAM_TIMEZONE


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


class InvalidVnpaySignatureError(PaymentError):
    """Raised when a VNPAY callback's vnp_SecureHash fails verification."""


class VnpayAmountMismatchError(PaymentError):
    """Raised when a VNPAY callback amount does not match the Payment."""


@dataclass(frozen=True)
class MomoCheckout:
    payment: Payment
    pay_url: str


@dataclass(frozen=True)
class VnpayCheckout:
    payment: Payment
    pay_url: str


@dataclass(frozen=True)
class VnpayIpnResult:
    """What the VNPAY IPN route should reply with — RspCode/Message only.

    Distinct from vnp_ResponseCode/vnp_TransactionStatus (VNPAY's own
    transaction outcome, read from the callback payload): this is our
    website's acknowledgement back to VNPAY's IPN caller.
    """

    rsp_code: str
    message: str
    payment: Payment | None = None


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
    _require_momo_enabled()
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
    _require_momo_enabled()
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


def start_vnpay_payment(
    *,
    booking_code: str,
    contribution_id: int,
    payer: User,
    return_url: str,
    ip_addr: str,
    bank_code: str | None = None,
    client: VnpayClient | None = None,
    now: datetime | None = None,
) -> VnpayCheckout:
    """Create or resume one VNPAY Sandbox checkout for a contribution.

    Step 2 scope only: builds a PENDING Payment + signed checkout URL. No
    Return/IPN verification, no SUCCESS transition, happens here.
    """
    _require_vnpay_enabled()
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
    return _start_vnpay_checkout(
        booking=booking,
        contribution=contribution,
        payer=payer,
        return_url=return_url,
        ip_addr=ip_addr,
        bank_code=bank_code,
        client=client,
        current_utc=current_utc,
    )


def start_vnpay_top_up(
    *,
    booking_code: str,
    payer: User,
    return_url: str,
    ip_addr: str,
    bank_code: str | None = None,
    client: VnpayClient | None = None,
    now: datetime | None = None,
) -> VnpayCheckout:
    """Create the creator's 30-minute opponent-deposit top-up VNPAY checkout."""
    _require_vnpay_enabled()
    _validate_payer(payer)
    current_utc = _normalize_utc(now)
    booking = _lock_booking(booking_code)
    _validate_top_up(booking=booking, payer=payer, current_utc=current_utc)
    top_up = _get_or_create_top_up_contribution(booking=booking, payer=payer)
    return _start_vnpay_checkout(
        booking=booking,
        contribution=top_up,
        payer=payer,
        return_url=return_url,
        ip_addr=ip_addr,
        bank_code=bank_code,
        client=client,
        current_utc=current_utc,
    )


def process_momo_payment_notification(
    payload: dict,
    *,
    client: MomoClient | None = None,
    now: datetime | None = None,
) -> Payment:
    """Verify and apply a server-to-server IPN idempotently."""
    _require_momo_enabled()
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
    _require_momo_enabled()
    momo = client or MomoClient.from_app_config()
    return _verified_momo_payment(
        payload=payload,
        momo=momo,
        lock_for_update=False,
    )


def inspect_vnpay_return(
    payload: dict,
    *,
    client: VnpayClient | None = None,
) -> Payment:
    """Verify a browser return and read its payment without changing state.

    Browser Return is never the source of truth: no lock, no mutation. It
    only tells the user what the DB (already updated by the IPN, if it has
    arrived) currently says.
    """
    _require_vnpay_enabled()
    try:
        vnpay = client or VnpayClient.from_app_config()
    except VnpayError as exc:
        raise PaymentError(str(exc)) from exc
    return _verified_vnpay_payment(
        payload=payload,
        vnpay=vnpay,
        lock_for_update=False,
    )


def process_vnpay_ipn(
    payload: dict,
    *,
    client: VnpayClient | None = None,
    now: datetime | None = None,
) -> VnpayIpnResult:
    """Verify and apply a server-to-server VNPAY IPN (GET) idempotently.

    Returns a VnpayIpnResult carrying the RspCode/Message the route must
    reply with — never raises for the ordinary "can't confirm" cases
    (unknown order, bad signature, bad amount), so the IPN endpoint always
    gets a clean, provider-contract response instead of a 500.
    """
    _require_vnpay_enabled()
    try:
        vnpay = client or VnpayClient.from_app_config()
    except VnpayError as exc:
        return VnpayIpnResult(rsp_code="99", message=str(exc))
    current_utc = _normalize_utc(now)

    try:
        payment = _verified_vnpay_payment(
            payload=payload,
            vnpay=vnpay,
            lock_for_update=True,
        )
    except InvalidVnpaySignatureError:
        return VnpayIpnResult(rsp_code="97", message="Invalid signature")
    except PaymentNotFoundError:
        return VnpayIpnResult(rsp_code="01", message="Order not found")
    except VnpayAmountMismatchError:
        return VnpayIpnResult(rsp_code="04", message="Invalid amount")

    if _vnpay_success_was_recorded(payment) or payment.status in {
        PaymentStatus.FAILED.value,
        PaymentStatus.CANCELLED.value,
    }:
        # Duplicate/late-arriving callback for a Payment that already has a
        # recorded, final outcome (SUCCESS; EXPIRED with a VNPAY success
        # already recorded; or a terminal FAILED/CANCELLED) — idempotent
        # no-op, no second side effect.
        #
        # status == PENDING or a not-yet-recorded EXPIRED both fall through
        # to real processing below: EXPIRED alone (without result_code=="00"
        # + provider_trans_id already set) does NOT prove VNPAY's success was
        # ever recorded for this Payment, so short-circuiting here would
        # silently drop a genuine "VNPAY says paid" notification.
        return VnpayIpnResult(
            rsp_code="02",
            message="Order already confirmed",
            payment=payment,
        )

    response_code = str(payload.get("vnp_ResponseCode", ""))
    transaction_status = str(payload.get("vnp_TransactionStatus", ""))
    provider_trans_id = str(payload.get("vnp_TransactionNo", "")) or None
    is_success = response_code == "00" and transaction_status == "00"

    payment.result_code = response_code
    if not is_success:
        payment.status = PaymentStatus.FAILED.value
        _commit_payment()
        return VnpayIpnResult(rsp_code="00", message="Confirm Success", payment=payment)

    if not provider_trans_id:
        raise PaymentError("VNPAY báo thành công nhưng không trả mã giao dịch.")

    paid_at = _parse_vnpay_pay_date(payload.get("vnp_PayDate")) or current_utc
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
        _record_late_vnpay_success_for_refund(
            payment=payment,
            booking=booking,
            contribution=contribution,
            provider_trans_id=provider_trans_id,
            paid_at=paid_at,
        )
        _commit_payment()
        return VnpayIpnResult(rsp_code="00", message="Confirm Success", payment=payment)

    _apply_success_to_payment(
        payment=payment,
        booking=booking,
        contribution=contribution,
        provider_trans_id=provider_trans_id,
        paid_at=paid_at,
    )
    _commit_payment()
    return VnpayIpnResult(rsp_code="00", message="Confirm Success", payment=payment)


def _verified_vnpay_payment(
    *,
    payload: dict,
    vnpay: VnpayClient,
    lock_for_update: bool,
) -> Payment:
    try:
        vnpay.verify_callback_params(payload)
    except VnpaySignatureError as exc:
        raise InvalidVnpaySignatureError(str(exc)) from exc

    if str(payload.get("vnp_TmnCode", "")) != vnpay.tmn_code:
        raise InvalidVnpaySignatureError(
            "Mã terminal VNPAY (vnp_TmnCode) trong callback không khớp."
        )

    order_id = str(payload.get("vnp_TxnRef", ""))
    statement = db.select(Payment).where(
        Payment.order_id == order_id,
        Payment.provider == PaymentProvider.VNPAY.value,
    )
    if lock_for_update:
        statement = with_update_lock(statement, Payment)
    payment = db.session.scalar(statement)
    if payment is None:
        raise PaymentNotFoundError("Không tìm thấy giao dịch VNPAY.")

    try:
        callback_amount = Decimal(str(payload.get("vnp_Amount", "")))
    except Exception as exc:
        raise VnpayAmountMismatchError(
            "Số tiền callback VNPAY không hợp lệ."
        ) from exc
    expected_amount = Decimal(to_vnpay_amount(payment.amount))
    if callback_amount != expected_amount:
        raise VnpayAmountMismatchError(
            "Số tiền callback VNPAY không khớp giao dịch."
        )
    return payment


def _record_late_vnpay_success_for_refund(
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

    from .refund import RefundError, queue_late_vnpay_payment_refund

    try:
        queue_late_vnpay_payment_refund(
            booking=booking,
            contribution=contribution,
            payment=payment,
            now=paid_at,
        )
    except RefundError as exc:
        db.session.rollback()
        raise PaymentError(
            "Không thể ghi nhận giao dịch VNPAY đến muộn để hoàn tiền."
        ) from exc


def _parse_vnpay_pay_date(value: object) -> datetime | None:
    """Parse vnp_PayDate (yyyyMMddHHmmss, Vietnam local time) into naive UTC."""
    if not value:
        return None
    try:
        vn_time = datetime.strptime(str(value), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return vn_time.replace(tzinfo=VIETNAM_TIMEZONE).astimezone(timezone.utc).replace(
        tzinfo=None
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


def _get_or_create_top_up_contribution(
    *,
    booking: Booking,
    payer: User,
) -> BookingContribution:
    """Reuse the creator's pending TOP_UP contribution, or open one.

    Shared, provider-agnostic bootstrap so a new provider (VNPAY) does not
    need its own copy of the waive-other-pending-slots logic.
    """
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
    if top_up is not None:
        return top_up

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
    return top_up


def _start_vnpay_checkout(
    *,
    booking: Booking,
    contribution: BookingContribution,
    payer: User,
    return_url: str,
    ip_addr: str,
    bank_code: str | None,
    client: VnpayClient | None,
    current_utc: datetime,
) -> VnpayCheckout:
    existing = db.session.scalar(
        db.select(Payment)
        .where(
            Payment.contribution_id == contribution.id,
            Payment.provider == PaymentProvider.VNPAY.value,
            Payment.status == PaymentStatus.PENDING.value,
        )
        .order_by(Payment.id.desc())
    )
    if existing is not None and existing.checkout_url:
        # Double-click / retry: reuse the same PENDING row and URL instead
        # of creating another Payment or re-signing a new one. No config
        # needed on this path, so it works even if VNPAY_* config is broken.
        return VnpayCheckout(payment=existing, pay_url=existing.checkout_url)

    # Validate the gateway client and return_url BEFORE any Payment row is
    # created/committed, so a missing/invalid VNPAY_TMN_CODE, VNPAY_HASH_SECRET
    # or return_url (VNPAY_RETURN_URL) never leaves an orphan PENDING row.
    try:
        vnpay = client or VnpayClient.from_app_config()
    except VnpayError as exc:
        raise PaymentError(str(exc)) from exc
    if not return_url:
        raise PaymentError("Thiếu Return URL để tạo giao dịch VNPAY.")

    if existing is not None:
        payment = existing
    else:
        payment = Payment(
            booking_id=booking.id,
            contribution_id=contribution.id,
            payer_id=payer.id,
            provider=PaymentProvider.VNPAY.value,
            payment_method=PaymentMethod.VNPAY_GATEWAY.value,
            amount=contribution.remaining_amount,
            order_id=f"VNPAYPAY{booking.id}{uuid4().hex[:16].upper()}",
            request_id=uuid4().hex,
            provider_trans_id=None,
            status=PaymentStatus.PENDING.value,
            result_code=None,
        )
        db.session.add(payment)
        _commit_payment()

    try:
        checkout_url = vnpay.build_payment_url(
            order_id=payment.order_id,
            amount=Decimal(payment.amount),
            order_info=f"Thanh toan coc booking {booking.booking_code}",
            return_url=return_url,
            ip_addr=ip_addr,
            create_date=_vnpay_create_date(current_utc),
            expire_date=_vnpay_expire_date(
                contribution=contribution,
                current_utc=current_utc,
            ),
            bank_code=bank_code,
        )
    except VnpayError as exc:
        raise PaymentError(str(exc)) from exc
    payment.checkout_url = checkout_url
    _commit_payment()
    return VnpayCheckout(payment=payment, pay_url=payment.checkout_url)


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


def _vnpay_success_was_recorded(payment: Payment) -> bool:
    """VNPAY-specific counterpart to _provider_success_was_recorded.

    MoMo's helper hardcodes MoMo's own "0" success sentinel, so it cannot be
    reused here: VNPAY's success sentinel is "00". A separate function keeps
    MoMo's helper/behavior untouched.
    """
    return bool(
        payment.status == PaymentStatus.SUCCESS.value
        or (
            payment.status == PaymentStatus.EXPIRED.value
            and payment.result_code == "00"
            and payment.provider_trans_id
        )
    )


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


def _require_momo_enabled() -> None:
    if not current_app.config.get("MOMO_ENABLED"):
        raise PaymentError("Hệ thống chỉ sử dụng thanh toán mô phỏng.")


def _require_vnpay_enabled() -> None:
    if not current_app.config.get("VNPAY_ENABLED"):
        raise PaymentError("Thanh toán VNPAY thử nghiệm chưa được bật.")


def _vnpay_create_date(current_utc: datetime) -> str:
    """Format vnp_CreateDate as yyyyMMddHHmmss in Vietnam local time (GMT+7)."""
    vn_time = current_utc.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TIMEZONE)
    return vn_time.strftime("%Y%m%d%H%M%S")


_VNPAY_DEFAULT_EXPIRE_MINUTES = 15


def _vnpay_expire_date(
    *,
    contribution: BookingContribution,
    current_utc: datetime,
) -> str:
    """Format vnp_ExpireDate as yyyyMMddHHmmss in Vietnam local time (GMT+7).

    Required by VNPAY PAY 2.1.0. Prefers the contribution's own payment
    deadline (contribution.expires_at) so the VNPAY session cannot outlive
    our own hold; falls back to a fixed session window when no deadline is
    recorded. Always strictly after vnp_CreateDate (current_utc).
    """
    deadline = contribution.expires_at
    if deadline is None or deadline <= current_utc:
        deadline = current_utc + timedelta(minutes=_VNPAY_DEFAULT_EXPIRE_MINUTES)
    vn_time = deadline.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TIMEZONE)
    return vn_time.strftime("%Y%m%d%H%M%S")
