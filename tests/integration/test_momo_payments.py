import hashlib
import hmac
from datetime import time

import pytest

from app.extensions import db
from app.integrations import MomoAPIError, MomoClient
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
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
    create_booking,
    process_momo_payment_notification,
    process_pending_momo_refunds,
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
        processed = process_momo_payment_notification(payload, client=client)
        repeated = process_momo_payment_notification(payload, client=client)
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
    assert "Đang chờ MoMo xác nhận qua IPN" in response.get_data(as_text=True)

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
