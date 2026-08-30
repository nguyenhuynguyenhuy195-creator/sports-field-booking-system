import hashlib
import hmac
from datetime import datetime, time, timedelta, timezone

import pytest

from app.extensions import db
from app.integrations import MomoAPIError, MomoClient
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
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
    PaymentError,
    cancel_owner_booking,
    cancel_user_booking,
    create_booking,
    create_match,
    expire_stale_bookings,
    pay_contribution_with_mock,
    process_momo_payment_notification,
    process_pending_momo_refunds,
    request_to_join_match,
    start_momo_payment,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)


SECRET = "sandbox-secret"


def sign(fields: dict) -> str:
    raw = "&".join(f"{key}={value}" for key, value in fields.items())
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


def build_client():
    def transport(path, payload, timeout):
        if path.endswith("/create"):
            response = {
                "partnerCode": "sandbox-partner",
                "orderId": payload["orderId"],
                "requestId": payload["requestId"],
                "amount": payload["amount"],
                "responseTime": 123456789,
                "message": "Successful.",
                "resultCode": 0,
                "payUrl": "https://test-payment.momo.vn/pay/test",
            }
            response["signature"] = sign(
                {
                    "accessKey": "sandbox-access",
                    "amount": response["amount"],
                    "message": response["message"],
                    "orderId": response["orderId"],
                    "partnerCode": response["partnerCode"],
                    "payUrl": response["payUrl"],
                    "requestId": response["requestId"],
                    "responseTime": response["responseTime"],
                    "resultCode": response["resultCode"],
                }
            )
            return response
        if path.endswith("/refund"):
            return {
                "orderId": payload["orderId"],
                "requestId": payload["requestId"],
                "amount": payload["amount"],
                "transId": 554433,
                "resultCode": 0,
                "message": "Successful.",
            }
        raise AssertionError(path)

    return MomoClient(
        partner_code="sandbox-partner",
        access_key="sandbox-access",
        secret_key=SECRET,
        transport=transport,
    )


def payment_notification(payment: Payment) -> dict:
    payload = {
        "amount": int(payment.amount),
        "extraData": "",
        "message": "Successful.",
        "orderId": payment.order_id,
        "orderInfo": f"Cọc booking {payment.booking.booking_code}",
        "orderType": "momo_wallet",
        "partnerCode": "sandbox-partner",
        "payType": "qr",
        "requestId": payment.request_id,
        "responseTime": 123456999,
        "resultCode": 0,
        "transId": 998877,
    }
    payload["signature"] = sign({"accessKey": "sandbox-access", **payload})
    return payload


def create_direct_momo_checkout(app, *, email_prefix: str) -> dict:
    owner = create_user(
        app,
        email=f"{email_prefix}-owner@example.com",
        role=UserRole.OWNER,
    )
    player = create_user(app, email=f"{email_prefix}-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    momo = build_client()

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id
            )
        )
        checkout = start_momo_payment(
            booking_code=booking.booking_code,
            contribution_id=contribution.id,
            payer=db.session.get(User, player.id),
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
            client=momo,
        )
        return {
            "booking_code": booking.booking_code,
            "booking_id": booking.id,
            "contribution_id": contribution.id,
            "payment_id": checkout.payment.id,
            "deadline": booking.initial_payment_due_at,
            "payload": payment_notification(checkout.payment),
            "momo": momo,
            "player_id": player.id,
        }


def test_momo_ipn_is_idempotent_and_owner_refund_completes(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    client = build_client()

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id
            )
        )
        checkout = start_momo_payment(
            booking_code=booking.booking_code,
            contribution_id=contribution.id,
            payer=db.session.get(User, player.id),
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
            client=client,
        )
        assert checkout.pay_url.startswith("https://test-payment.momo.vn/")
        assert checkout.payment.status == PaymentStatus.PENDING.value

        payload = payment_notification(checkout.payment)
        before_deadline = booking.initial_payment_due_at - timedelta(seconds=1)
        processed = process_momo_payment_notification(
            payload,
            client=client,
            now=before_deadline,
        )
        repeated = process_momo_payment_notification(
            payload,
            client=client,
            now=before_deadline,
        )
        db.session.refresh(booking)
        assert processed.id == repeated.id
        assert processed.status == PaymentStatus.SUCCESS.value
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount

        cancel_owner_booking(
            booking_code=booking.booking_code,
            owner=db.session.get(User, owner.id),
            reason="Sân ngập nước.",
        )
        refund = db.session.scalar(db.select(Refund))
        assert booking.status == BookingStatus.REFUND_PENDING.value
        assert refund.status == RefundStatus.PENDING.value

        assert process_pending_momo_refunds(
            booking_id=booking.id,
            client=client,
        ) == 1
        db.session.refresh(booking)
        db.session.refresh(refund)
        assert refund.status == RefundStatus.SUCCESS.value
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.paid_amount == 0


def test_late_momo_ipn_expires_unpaid_booking_and_queues_refund(app):
    case = create_direct_momo_checkout(app, email_prefix="late")
    late_now = case["deadline"] + timedelta(seconds=1)

    with app.app_context():
        processed = process_momo_payment_notification(
            case["payload"],
            client=case["momo"],
            now=late_now,
        )
        repeated = process_momo_payment_notification(
            case["payload"],
            client=case["momo"],
            now=late_now + timedelta(seconds=1),
        )
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(
            BookingContribution,
            case["contribution_id"],
        )
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == processed.id)
        )

        assert repeated.id == processed.id
        assert processed.status == PaymentStatus.EXPIRED.value
        assert processed.result_code == "0"
        assert processed.provider_trans_id == "998877"
        assert processed.paid_at == late_now
        assert booking.status == BookingStatus.EXPIRED.value
        assert booking.paid_amount == 0
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == 0
        assert refund.status == RefundStatus.PENDING.value
        assert refund.amount == processed.amount
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1

        assert process_pending_momo_refunds(
            booking_id=booking.id,
            client=case["momo"],
        ) == 1
        db.session.refresh(booking)
        db.session.refresh(contribution)
        db.session.refresh(refund)
        assert refund.status == RefundStatus.SUCCESS.value
        assert booking.status == BookingStatus.EXPIRED.value
        assert booking.paid_amount == 0
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == 0


def test_late_momo_ipn_does_not_revive_persisted_expired_booking(app):
    case = create_direct_momo_checkout(app, email_prefix="persisted-expired")
    late_now = case["deadline"] + timedelta(seconds=1)

    with app.app_context():
        assert expire_stale_bookings(now=late_now) == 1
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(
            BookingContribution,
            case["contribution_id"],
        )
        assert booking.status == BookingStatus.EXPIRED.value
        assert contribution.status == ContributionStatus.EXPIRED.value

        payment = process_momo_payment_notification(
            case["payload"],
            client=case["momo"],
            now=late_now + timedelta(seconds=1),
        )
        db.session.refresh(booking)
        db.session.refresh(contribution)
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment.id)
        )

        assert payment.status == PaymentStatus.EXPIRED.value
        assert booking.status == BookingStatus.EXPIRED.value
        assert booking.paid_amount == 0
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == 0
        assert refund.status == RefundStatus.PENDING.value


def test_late_momo_ipn_does_not_revive_cancelled_booking(app):
    case = create_direct_momo_checkout(app, email_prefix="cancelled")

    with app.app_context():
        booking = cancel_user_booking(
            booking_code=case["booking_code"],
            user=db.session.get(User, case["player_id"]),
        )
        cancelled_status = booking.status
        contribution = db.session.get(
            BookingContribution,
            case["contribution_id"],
        )
        cancelled_contribution_status = contribution.status

        payment = process_momo_payment_notification(
            case["payload"],
            client=case["momo"],
            now=case["deadline"] - timedelta(seconds=1),
        )
        db.session.refresh(booking)
        db.session.refresh(contribution)
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment.id)
        )

        assert cancelled_status == BookingStatus.CANCELLED.value
        assert payment.status == PaymentStatus.EXPIRED.value
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.paid_amount == 0
        assert contribution.status == cancelled_contribution_status
        assert contribution.status != ContributionStatus.PAID.value
        assert contribution.amount_paid == 0
        assert refund.status == RefundStatus.PENDING.value


def test_late_opponent_ipn_expires_participant_without_funding_booking(app):
    owner = create_user(app, email="late-opponent-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="late-opponent-creator@example.com")
    opponent = create_user(app, email="late-opponent@example.com")
    replacement = create_user(app, email="late-opponent-replacement@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    momo = build_client()

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
            title="Kèo kiểm thử late payment",
            description="Kiểm tra participant không được join sau hạn.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000001",
            share_contact=True,
        )
        accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        participant = request_to_join_match(
            match_id=match.id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
            now=accepted_at,
        )
        opponent_contribution = participant.contribution
        checkout = start_momo_payment(
            booking_code=booking.booking_code,
            contribution_id=opponent_contribution.id,
            payer=db.session.get(User, opponent.id),
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
            client=momo,
            now=accepted_at,
        )
        payload = payment_notification(checkout.payment)
        late_now = participant.payment_due_at + timedelta(seconds=1)

        payment = process_momo_payment_notification(
            payload,
            client=momo,
            now=late_now,
        )
        db.session.refresh(booking)
        db.session.refresh(match)
        db.session.refresh(participant)
        db.session.refresh(opponent_contribution)
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment.id)
        )

        assert payment.status == PaymentStatus.EXPIRED.value
        assert booking.status == BookingStatus.PARTIALLY_PAID.value
        assert booking.paid_amount == creator_contribution.amount_paid
        assert participant.status == MatchParticipantStatus.EXPIRED.value
        assert match.status == MatchStatus.OPEN.value
        assert opponent_contribution.status == ContributionStatus.PENDING.value
        assert opponent_contribution.user_id is None
        assert opponent_contribution.amount_paid == 0
        assert refund.status == RefundStatus.PENDING.value

        replacement_participant = request_to_join_match(
            match_id=match.id,
            user=db.session.get(User, replacement.id),
            contact_phone="0901000003",
            share_contact=True,
            now=late_now + timedelta(seconds=1),
        )
        replacement_checkout = start_momo_payment(
            booking_code=booking.booking_code,
            contribution_id=replacement_participant.contribution_id,
            payer=db.session.get(User, replacement.id),
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
            client=momo,
            now=late_now + timedelta(seconds=1),
        )
        assert replacement_participant.contribution_id == opponent_contribution.id
        assert replacement_checkout.payment.id != payment.id
        assert replacement_checkout.payment.payer_id == replacement.id

        assert process_pending_momo_refunds(
            booking_id=booking.id,
            client=momo,
        ) == 1
        db.session.refresh(booking)
        db.session.refresh(replacement_participant)
        db.session.refresh(opponent_contribution)
        assert booking.status == BookingStatus.PARTIALLY_PAID.value
        assert booking.paid_amount == creator_contribution.amount_paid
        assert (
            replacement_participant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
        assert opponent_contribution.status == ContributionStatus.PENDING.value
        assert opponent_contribution.user_id == replacement.id


def test_momo_browser_return_stays_pending_until_verified_ipn(
    app,
    client,
    monkeypatch,
):
    owner = create_user(app, email="return-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="return-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    momo = build_client()

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id
            )
        )
        checkout = start_momo_payment(
            booking_code=booking.booking_code,
            contribution_id=contribution.id,
            payer=db.session.get(User, player.id),
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
            client=momo,
        )
        payload = payment_notification(checkout.payment)
        booking_code = booking.booking_code
        payment_id = checkout.payment.id
        contribution_id = contribution.id

    monkeypatch.setattr(
        MomoClient,
        "from_app_config",
        classmethod(lambda cls: momo),
    )
    login(client, email=player.email)

    response = client.get(
        "/payments/momo/return",
        query_string=payload,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Đang chờ MoMo xác nhận" in response.get_data(as_text=True)

    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        contribution = db.session.get(BookingContribution, contribution_id)
        assert payment.status == PaymentStatus.PENDING.value
        assert booking.status == BookingStatus.CONFIRMED.value
        assert contribution.status == ContributionStatus.PENDING.value

    ipn_response = client.post("/payments/momo/ipn", json=payload)
    assert ipn_response.status_code == 200

    with app.app_context():
        assert db.session.get(Payment, payment_id).status == PaymentStatus.SUCCESS.value
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert booking.status == BookingStatus.PAID.value
        assert (
            db.session.get(BookingContribution, contribution_id).status
            == ContributionStatus.PAID.value
        )


def test_momo_checkout_retries_same_request_after_network_error(app):
    owner = create_user(app, email="retry-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="retry-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    calls = []

    def transport(path, payload, timeout):
        calls.append(payload.copy())
        if len(calls) == 1:
            raise MomoAPIError("Mất kết nối thử nghiệm.")
        response = {
            "partnerCode": "sandbox-partner",
            "orderId": payload["orderId"],
            "requestId": payload["requestId"],
            "amount": payload["amount"],
            "responseTime": 123456789,
            "message": "Successful.",
            "resultCode": 0,
            "payUrl": "https://test-payment.momo.vn/pay/retry",
        }
        response["signature"] = sign(
            {
                "accessKey": "sandbox-access",
                "amount": response["amount"],
                "message": response["message"],
                "orderId": response["orderId"],
                "partnerCode": response["partnerCode"],
                "payUrl": response["payUrl"],
                "requestId": response["requestId"],
                "responseTime": response["responseTime"],
                "resultCode": response["resultCode"],
            }
        )
        return response

    client = MomoClient(
        partner_code="sandbox-partner",
        access_key="sandbox-access",
        secret_key=SECRET,
        transport=transport,
    )

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id
            )
        )
        kwargs = {
            "booking_code": booking.booking_code,
            "contribution_id": contribution.id,
            "payer": db.session.get(User, player.id),
            "redirect_url": "https://example.test/payments/momo/return",
            "ipn_url": "https://example.test/payments/momo/ipn",
            "client": client,
        }
        with pytest.raises(PaymentError, match="Mất kết nối"):
            start_momo_payment(**kwargs)

        pending = db.session.scalar(db.select(Payment))
        checkout = start_momo_payment(**kwargs)

        assert checkout.payment.id == pending.id
        assert calls[0]["orderId"] == calls[1]["orderId"]
        assert calls[0]["requestId"] == calls[1]["requestId"]
        assert checkout.pay_url.endswith("/retry")
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 1
