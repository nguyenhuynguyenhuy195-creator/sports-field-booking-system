from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.integrations import VnpayClient
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Payment,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
    UserRole,
)
from app.services import (
    apply_creator_cancellation_policy,
    apply_funding_shortfall_refunds,
    apply_owner_cancellation_refunds,
    cancel_owner_booking,
    create_booking,
    create_match,
    pay_contribution_with_mock,
    process_pending_vnpay_refunds,
    process_vnpay_ipn,
    request_to_join_match,
    start_vnpay_payment,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)
from tests.integration.test_vnpay_payments import (
    VNPAY_API_URL,
    VNPAY_HASH_SECRET,
    VNPAY_PAYMENT_URL,
    VNPAY_TMN_CODE,
    build_vnpay_client,
    create_direct_booking,
    vnpay_callback_payload,
)


_RESPONSE_HASH_FIELDS = (
    "vnp_ResponseId", "vnp_Command", "vnp_ResponseCode", "vnp_Message",
    "vnp_TmnCode", "vnp_TxnRef", "vnp_Amount", "vnp_BankCode", "vnp_PayDate",
    "vnp_TransactionNo", "vnp_TransactionType", "vnp_TransactionStatus",
    "vnp_OrderInfo",
)


def _fake_refund_transport(
    *,
    response_code: str = "00",
    transaction_status: str = "00",
    provider_refund_trans_id: str = "REFUND-TRANS-1",
    captured: list | None = None,
):
    """Build a transport for VnpayClient(...).refund() that behaves like a
    real VNPAY Sandbox: it echoes back whatever vnp_TxnRef/vnp_Amount/
    vnp_TransactionType our own service actually submitted, validly signed,
    with the caller-chosen result_code/transaction_status. No real network
    call is ever made — this is a pure in-process fake.
    """
    signer = build_vnpay_client()

    def transport(url, payload, timeout):
        if captured is not None:
            captured.append(dict(payload))
        response = {
            "vnp_ResponseId": payload["vnp_RequestId"],
            "vnp_Command": "refund",
            "vnp_ResponseCode": response_code,
            "vnp_Message": "Confirm Success" if response_code == "00" else "Failed",
            "vnp_TmnCode": payload["vnp_TmnCode"],
            "vnp_TxnRef": payload["vnp_TxnRef"],
            "vnp_Amount": payload["vnp_Amount"],
            "vnp_BankCode": "NCB",
            "vnp_PayDate": "20260912103500",
            "vnp_TransactionNo": provider_refund_trans_id,
            "vnp_TransactionType": payload["vnp_TransactionType"],
            "vnp_TransactionStatus": transaction_status,
            "vnp_OrderInfo": payload["vnp_OrderInfo"],
        }
        response["vnp_SecureHash"] = signer._pipe_hash(
            response, _RESPONSE_HASH_FIELDS
        )
        return response

    return transport


def _build_refund_client(**transport_kwargs) -> VnpayClient:
    return VnpayClient(
        tmn_code=VNPAY_TMN_CODE,
        hash_secret=VNPAY_HASH_SECRET,
        payment_url=VNPAY_PAYMENT_URL,
        api_url=VNPAY_API_URL,
        transport=_fake_refund_transport(**transport_kwargs),
    )


def _pay_direct_booking_via_vnpay(app, *, email_prefix: str) -> dict:
    """400,000 VND DIRECT_BOOKING, 120,000 VND deposit, paid to SUCCESS via
    the real PAY -> IPN flow (reusing Step 3/5 test helpers)."""
    case = create_direct_booking(app, email_prefix=email_prefix)
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        process_vnpay_ipn(payload, client=vnpay)
        payment_id = checkout.payment.id
    case["payment_id"] = payment_id
    return case


# --- 11-14, 18-20: process_pending_vnpay_refunds correctness -------------------


def test_pending_refund_becomes_success_on_valid_response(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-success")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        assert refund.status == RefundStatus.PENDING.value

        captured: list = []
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert succeeded == 1
        db.session.refresh(refund)
        assert refund.status == RefundStatus.SUCCESS.value
        # Owner cancellation refund is the ONLY refund on this payment, for
        # the full original amount -> VNPAY "full" refund ("02").
        assert captured[0]["vnp_TransactionType"] == "02"
        # VNPAY's own success sentinel ("00") must survive untouched, never
        # overwritten with MoMo/MOCK's "0".
        assert refund.result_code == "00"


def test_provider_refund_transaction_id_is_stored(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-transid")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(provider_refund_trans_id="REFUND-999"),
        )
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        assert refund.provider_refund_trans_id == "REFUND-999"
        assert refund.refunded_at is not None


def test_booking_and_contribution_amounts_decrease_exactly_once(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-once")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        assert booking.paid_amount == Decimal("120000")
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"], client=_build_refund_client()
        )
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.paid_amount == Decimal("0")
        assert contribution.amount_paid == Decimal("0")
        assert contribution.status == ContributionStatus.REFUNDED.value


def test_repeated_processing_does_not_double_subtract(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-idempotent")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        first = process_pending_vnpay_refunds(
            booking_id=case["booking_id"], client=_build_refund_client()
        )
        second = process_pending_vnpay_refunds(
            booking_id=case["booking_id"], client=_build_refund_client()
        )
        assert first == 1
        assert second == 0  # nothing left in PENDING/PROCESSING to resubmit
        booking = db.session.get(Booking, case["booking_id"])
        assert booking.paid_amount == Decimal("0")  # not negative, not doubled


def test_provider_failure_leaves_financial_balances_unchanged(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-failure")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            # A genuine, final rejection — NOT "94" (see
            # test_response_code_94_maps_to_processing_not_failed below,
            # which is what "94" actually means).
            client=_build_refund_client(
                response_code="91", transaction_status="02"
            ),
        )
        assert succeeded == 0
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert refund.status == RefundStatus.FAILED.value
        assert refund.result_code == "91"
        assert booking.paid_amount == Decimal("120000")  # untouched
        assert contribution.amount_paid == Decimal("120000")  # untouched


def test_response_code_94_maps_to_processing_not_failed(app):
    """VNPAY responseCode "94" means the refund request was already received
    and is being processed (e.g. a duplicate submission) — it is not a
    rejection, and must not be treated as FAILED nor change any balance."""
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-code94")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()

        captured: list = []
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(
                response_code="94", transaction_status="", captured=captured
            ),
        )
        assert succeeded == 0
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert refund.status == RefundStatus.PROCESSING.value
        assert booking.paid_amount == Decimal("120000")  # unchanged while PROCESSING
        assert contribution.amount_paid == Decimal("120000")
        assert len(captured) == 1

        # A second pass must not resubmit it either, same as "05"/"06".
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert len(captured) == 1


def test_processing_status_does_not_reduce_balances_and_is_not_resubmitted(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-processing")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()

        captured: list = []
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(
                response_code="00", transaction_status="05", captured=captured
            ),
        )
        assert succeeded == 0
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        booking = db.session.get(Booking, case["booking_id"])
        assert refund.status == RefundStatus.PROCESSING.value
        assert booking.paid_amount == Decimal("120000")  # unchanged while PROCESSING
        assert len(captured) == 1

        # A second pass must NOT resubmit a PROCESSING refund (no VNPAY
        # "query a specific refund" endpoint exists to safely reconcile it).
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert len(captured) == 1
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        assert refund.status == RefundStatus.PROCESSING.value


def test_transaction_status_06_also_maps_to_processing(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-status06")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()

        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(
                response_code="00", transaction_status="06"
            ),
        )
        assert succeeded == 0
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        booking = db.session.get(Booking, case["booking_id"])
        assert refund.status == RefundStatus.PROCESSING.value
        assert booking.paid_amount == Decimal("120000")  # unchanged while PROCESSING


def test_missing_provider_trans_id_fails_safely(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-notransid")
    with app.app_context():
        payment = db.session.get(Payment, case["payment_id"])
        payment.provider_trans_id = None  # simulate a corrupted/legacy record
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()

        captured: list = []
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert succeeded == 0
        assert captured == []  # never even attempted to call VNPAY
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        booking = db.session.get(Booking, case["booking_id"])
        assert refund.status == RefundStatus.FAILED.value
        assert refund.result_code == "MISSING_TRANS_ID"
        assert booking.paid_amount == Decimal("120000")  # untouched


# --- 15-17: full vs partial policy amounts stay correct through the API -------


def test_eighty_percent_creator_refund_stays_partial_and_keeps_twenty_percent_fee(
    app,
):
    owner = create_user(app, email="fs-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fs-creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    vnpay = build_vnpay_client()

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        creator_contribution = next(
            item for item in booking.contributions if item.user_id == creator.id
        )
        checkout = start_vnpay_payment(
            booking_code=booking.booking_code,
            contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        process_vnpay_ipn(payload, client=vnpay)
        payment_id = checkout.payment.id
        booking_id = booking.id
        creator_paid = Decimal(db.session.get(Payment, payment_id).amount)

        booking = db.session.get(Booking, booking_id)
        apply_funding_shortfall_refunds(
            booking=booking,
            reason="Lịch đặt không được đóng đủ tiền trước hạn 12 giờ.",
        )
        db.session.commit()

        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment_id)
        )
        assert refund.amount == (creator_paid * Decimal("0.80")).quantize(
            Decimal("0.01")
        )

        captured: list = []
        process_pending_vnpay_refunds(
            booking_id=booking_id, client=_build_refund_client(captured=captured)
        )
        # 80% of the original amount != the full remaining refundable amount
        # -> must be submitted as a PARTIAL refund ("03"), never "02".
        assert captured[0]["vnp_TransactionType"] == "03"

        booking = db.session.get(Booking, booking_id)
        assert booking.cancellation_fee_amount == (
            creator_paid - refund.amount
        ).quantize(Decimal("0.01"))
        assert booking.cancellation_fee_amount == (
            creator_paid * Decimal("0.20")
        ).quantize(Decimal("0.01"))


def test_owner_cancellation_workflow_attempts_vnpay_refund_automatically(
    app, monkeypatch
):
    """Full integration: cancel_owner_booking's existing best-effort
    provider-refund step (Section 4) must reach VNPAY too, not just MoMo,
    without ever needing a manual process_pending_vnpay_refunds call."""
    case = _pay_direct_booking_via_vnpay(app, email_prefix="owner-cancel-auto")
    fake_client = _build_refund_client()
    monkeypatch.setattr(
        VnpayClient, "from_app_config", classmethod(lambda cls: fake_client)
    )
    with app.app_context():
        owner = db.session.scalar(
            db.select(User).where(User.role == UserRole.OWNER.value)
        )
        cancel_owner_booking(
            booking_code=case["booking_code"],
            owner=owner,
            reason="Sân ngập nước.",
        )
        booking = db.session.get(Booking, case["booking_id"])
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == case["payment_id"])
        )
        assert refund.status == RefundStatus.SUCCESS.value
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.paid_amount == Decimal("0")


def test_find_opponent_opponent_receives_full_refund_on_creator_cancel(app):
    owner = create_user(app, email="cc-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="cc-creator@example.com")
    opponent = create_user(app, email="cc-opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    vnpay = build_vnpay_client()

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        creator_contribution = next(
            item for item in booking.contributions if item.user_id == creator.id
        )
        pay_contribution_with_mock(
            booking_code=booking.booking_code,
            contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator.id),
        )
        match = create_match(
            booking_code=booking.booking_code,
            creator=db.session.get(User, creator.id),
            title="Kèo hoàn tiền VNPAY",
            description="Kiểm tra hoàn 100% cho đối thủ khi creator hủy.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000001",
            share_contact=True,
        )
        participant = request_to_join_match(
            match_id=match.id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        opponent_checkout = start_vnpay_payment(
            booking_code=booking.booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        opponent_payload = vnpay_callback_payload(opponent_checkout.payment, vnpay)
        process_vnpay_ipn(opponent_payload, client=vnpay)
        opponent_payment_id = opponent_checkout.payment.id
        opponent_paid = Decimal(
            db.session.get(Payment, opponent_payment_id).amount
        )
        booking_id = booking.id

        booking = db.session.get(Booking, booking_id)
        apply_creator_cancellation_policy(
            booking=booking, reason="Người tạo kèo hủy."
        )
        db.session.commit()

        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == opponent_payment_id)
        )
        assert refund.amount == opponent_paid  # 100%, not forfeited like creator

        captured: list = []
        process_pending_vnpay_refunds(
            booking_id=booking_id, client=_build_refund_client(captured=captured)
        )
        assert captured[0]["vnp_TransactionType"] == "02"  # covers it in full
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == opponent_payment_id)
        )
        assert refund.status == RefundStatus.SUCCESS.value
        assert refund.result_code == "00"


# --- 21-22: late VNPAY success must never turn into a negative balance --------


def test_late_vnpay_success_refund_does_not_subtract_booking_paid_amount(app):
    case = create_direct_booking(app, email_prefix="late-refund-booking")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        late_now = case["deadline"] + timedelta(seconds=1)
        process_vnpay_ipn(payload, client=vnpay, now=late_now)

        booking = db.session.get(Booking, case["booking_id"])
        assert booking.status == BookingStatus.EXPIRED.value
        assert booking.paid_amount == Decimal("0")  # never added in the first place

        captured: list = []
        succeeded = process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert succeeded == 1
        # A late-payment refund always covers the full original payment and
        # is the only refund ever recorded for it -> full refund ("02").
        assert captured[0]["vnp_TransactionType"] == "02"

        booking = db.session.get(Booking, case["booking_id"])
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == checkout.payment.id)
        )
        assert refund.status == RefundStatus.SUCCESS.value
        assert refund.result_code == "00"
        assert booking.paid_amount == Decimal("0")  # still not negative/decreased


def test_late_vnpay_success_refund_does_not_subtract_contribution_amount_paid(app):
    case = create_direct_booking(app, email_prefix="late-refund-contribution")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        late_now = case["deadline"] + timedelta(seconds=1)
        process_vnpay_ipn(payload, client=vnpay, now=late_now)

        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == Decimal("0")

        process_pending_vnpay_refunds(
            booking_id=case["booking_id"], client=_build_refund_client()
        )

        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert contribution.amount_paid == Decimal("0")  # still not negative
        # Late-success accounting must not silently flip it back to a normal
        # paid/refunded state either — it stays EXPIRED, matching the booking.
        assert contribution.status == ContributionStatus.EXPIRED.value


# --- Full vs partial: a second refund finishing off an already-partially ------
# --- refunded payment must stay "03", even though its own amount happens to --
# --- exhaust what remains. Only the SOLE refund for the full original -------
# --- amount may ever be "02". -------------------------------------------------


def test_second_refund_after_earlier_partial_success_is_submitted_as_partial(app):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="refund-multi-part")
    with app.app_context():
        payment = db.session.get(Payment, case["payment_id"])
        booking = db.session.get(Booking, case["booking_id"])
        # Simulate an earlier partial refund already SUCCESS for this same
        # Payment (120,000 VND total) — 50,000 already refunded elsewhere.
        first_refund = Refund(
            booking_id=booking.id,
            payment_id=payment.id,
            recipient_id=payment.payer_id,
            amount=Decimal("50000"),
            reason="Hoàn một phần đợt 1 (giả lập cho kiểm thử).",
            order_id=f"VNPAY-REFUND-TEST-PART1-{payment.id}",
            request_id=uuid4().hex,
            provider_refund_trans_id="REFUND-PART1",
            status=RefundStatus.SUCCESS.value,
            result_code="00",
            refunded_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(first_refund)
        # A second, still-pending refund for exactly what is left
        # (120,000 - 50,000 = 70,000) — numerically it "finishes off" the
        # payment, but it is NOT the sole/full refund for it.
        second_refund = Refund(
            booking_id=booking.id,
            payment_id=payment.id,
            recipient_id=payment.payer_id,
            amount=Decimal("70000"),
            reason="Hoàn phần còn lại (giả lập cho kiểm thử).",
            order_id=f"VNPAY-REFUND-TEST-PART2-{payment.id}",
            request_id=uuid4().hex,
            status=RefundStatus.PENDING.value,
        )
        db.session.add(second_refund)
        db.session.commit()

        captured: list = []
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(captured=captured),
        )
        assert len(captured) == 1
        assert captured[0]["vnp_TransactionType"] == "03"


# --- Owner cancellation flash message must reflect the ACTUAL refund state ---


def test_owner_cancellation_flash_says_processing_when_refund_not_yet_succeeded(
    app, client, monkeypatch
):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="owner-cancel-processing")
    fake_client = _build_refund_client(response_code="00", transaction_status="05")
    monkeypatch.setattr(
        VnpayClient, "from_app_config", classmethod(lambda cls: fake_client)
    )
    with app.app_context():
        owner_email = db.session.scalar(
            db.select(User.email).where(User.role == UserRole.OWNER.value)
        )
    login(client, email=owner_email)

    response = client.post(
        f"/owner/bookings/{case['booking_code']}/cancel",
        data={"owner-cancel-reason": "Sân gặp sự cố kỹ thuật."},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "đang được xử lý qua cổng thanh toán" in page
    assert "đã được hoàn 100%" not in page


def test_owner_cancellation_flash_says_completed_when_all_refunds_succeed(
    app, client, monkeypatch
):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="owner-cancel-completed")
    fake_client = _build_refund_client()  # default: "00"/"00" -> SUCCESS
    monkeypatch.setattr(
        VnpayClient, "from_app_config", classmethod(lambda cls: fake_client)
    )
    with app.app_context():
        owner_email = db.session.scalar(
            db.select(User.email).where(User.role == UserRole.OWNER.value)
        )
    login(client, email=owner_email)

    response = client.post(
        f"/owner/bookings/{case['booking_code']}/cancel",
        data={"owner-cancel-reason": "Sân gặp sự cố kỹ thuật."},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "đã được hoàn 100%" in page
    assert "đang được xử lý qua cổng thanh toán" not in page


# --- User / Owner / Admin must all render the VNPAY provider label -----------
# --- correctly instead of a blank/missing label. -----------------------------


def test_user_booking_detail_renders_vnpay_provider_label(app, client):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="ui-provider-user")
    with app.app_context():
        email = db.session.get(User, case["player_id"]).email
    login(client, email=email)

    response = client.get(f"/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" in page


def test_owner_booking_detail_renders_vnpay_provider_label(app, client):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="ui-provider-owner")
    with app.app_context():
        owner_email = db.session.scalar(
            db.select(User.email).where(User.role == UserRole.OWNER.value)
        )
    login(client, email=owner_email)

    response = client.get(f"/owner/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" in page


def test_admin_booking_detail_renders_vnpay_provider_label_without_error(app, client):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="ui-provider-admin")
    create_user(
        app, email="ui-provider-admin-admin@example.com", role=UserRole.ADMIN
    )
    login(client, email="ui-provider-admin-admin@example.com")

    response = client.get(f"/admin/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" in page


def test_admin_booking_detail_refund_total_excludes_processing_refund(app, client):
    case = _pay_direct_booking_via_vnpay(app, email_prefix="admin-total-processing")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Sự cố kỹ thuật.")
        db.session.commit()
        process_pending_vnpay_refunds(
            booking_id=case["booking_id"],
            client=_build_refund_client(
                response_code="00", transaction_status="05"
            ),
        )
    create_user(
        app,
        email="admin-total-processing-admin@example.com",
        role=UserRole.ADMIN,
    )
    login(client, email="admin-total-processing-admin@example.com")

    response = client.get(f"/admin/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    # The refund is still PROCESSING, not SUCCESS -> "Đã hoàn" must read 0,
    # never the payment's 120,000 VND.
    assert "<dt>Đã hoàn</dt><dd>0 đ</dd>" in page
