from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import pytest

from app.extensions import db
from app.integrations import VnpayClient, to_vnpay_amount
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    MatchParticipantStatus,
    MatchStatus,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
    UserRole,
)
from app.services import (
    PaymentError,
    PaymentExpiredError,
    create_booking,
    create_match,
    inspect_vnpay_return,
    pay_contribution_with_mock,
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


VNPAY_TMN_CODE = "TESTCODE01"
VNPAY_HASH_SECRET = "SECRETKEY123"
VNPAY_PAYMENT_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
VNPAY_API_URL = "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction"


def query_dict(url: str) -> dict:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def build_vnpay_client() -> VnpayClient:
    return VnpayClient(
        tmn_code=VNPAY_TMN_CODE,
        hash_secret=VNPAY_HASH_SECRET,
        payment_url=VNPAY_PAYMENT_URL,
        api_url=VNPAY_API_URL,
    )


def vnpay_callback_payload(
    payment: Payment,
    client: VnpayClient,
    *,
    response_code: str = "00",
    transaction_status: str = "00",
    transaction_no: str = "998877",
    pay_date: str = "20260912103500",
    amount: str | None = None,
    txn_ref: str | None = None,
) -> dict:
    """Build a VNPAY-shaped callback payload signed with the same client
    used as the checkout's gateway — the trusted "fake VNPAY server" side,
    exactly like test_momo_payments.py signs MoMo callbacks with a real
    MomoClient instance rather than re-deriving the hash from our own code.
    """
    payload = {
        "vnp_TmnCode": client.tmn_code,
        "vnp_TxnRef": txn_ref if txn_ref is not None else payment.order_id,
        "vnp_Amount": (
            amount if amount is not None else str(to_vnpay_amount(payment.amount))
        ),
        "vnp_ResponseCode": response_code,
        "vnp_TransactionStatus": transaction_status,
        "vnp_TransactionNo": transaction_no,
        "vnp_BankCode": "NCB",
        "vnp_PayDate": pay_date,
        "vnp_OrderInfo": f"Thanh toan coc booking {payment.booking.booking_code}",
    }
    payload["vnp_SecureHash"] = client._sign(payload)
    return payload


def create_direct_booking(app, *, email_prefix: str) -> dict:
    """400,000 VND booking (2h x 200,000 VND/h) — matches the deposit example."""
    owner = create_user(
        app,
        email=f"{email_prefix}-owner@example.com",
        role=UserRole.OWNER,
    )
    player = create_user(app, email=f"{email_prefix}-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)

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
        return {
            "booking_code": booking.booking_code,
            "booking_id": booking.id,
            "contribution_id": contribution.id,
            "deadline": booking.initial_payment_due_at,
            "player_id": player.id,
        }


# --- Payment row correctness -----------------------------------------------


def test_start_vnpay_payment_creates_pending_payment_with_correct_fields(app):
    case = create_direct_booking(app, email_prefix="basic")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        payment = checkout.payment
        assert payment.provider == PaymentProvider.VNPAY.value
        assert payment.payment_method == PaymentMethod.VNPAY_GATEWAY.value
        assert payment.status == PaymentStatus.PENDING.value
        assert payment.amount == Decimal("120000")  # DB stays plain VND
        assert payment.contribution_id == case["contribution_id"]
        assert payment.checkout_url is not None
        assert payment.checkout_url == checkout.pay_url

        # No SUCCESS/state transition may happen in Step 2.
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.status == BookingStatus.CONFIRMED.value
        assert contribution.status == ContributionStatus.PENDING.value
        assert contribution.amount_paid == 0


def test_checkout_url_uses_vnp_txn_ref_matching_order_id_and_amount_x100(app):
    case = create_direct_booking(app, email_prefix="txnref")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        params = query_dict(checkout.pay_url)
        assert params["vnp_TxnRef"] == checkout.payment.order_id
        assert checkout.payment.amount == Decimal("120000")
        assert params["vnp_Amount"] == "12000000"
        assert params["vnp_TmnCode"]
        assert "vnp_SecureHash" in params


# --- QR optional --------------------------------------------------------------


def test_bank_code_none_omits_vnp_bank_code(app):
    case = create_direct_booking(app, email_prefix="noqr")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
        )
        params = query_dict(checkout.pay_url)
        assert "vnp_BankCode" not in params
        assert checkout.payment.payment_method == PaymentMethod.VNPAY_GATEWAY.value


def test_bank_code_vnpayqr_adds_vnp_bank_code_without_changing_payment_method(app):
    case = create_direct_booking(app, email_prefix="qr")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        params = query_dict(checkout.pay_url)
        assert params["vnp_BankCode"] == "VNPAYQR"
        # PaymentMethod stays the generic gateway value — no VNPAY_QR enum.
        assert checkout.payment.payment_method == PaymentMethod.VNPAY_GATEWAY.value
        assert checkout.payment.provider == PaymentProvider.VNPAY.value


# --- Retry / double-click ------------------------------------------------------


def test_double_click_reuses_pending_payment_instead_of_creating_a_new_one(app):
    case = create_direct_booking(app, email_prefix="retry")
    with app.app_context():
        first = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        second = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        assert first.payment.id == second.payment.id
        assert first.pay_url == second.pay_url
        assert (
            db.session.scalar(
                db.select(db.func.count(Payment.id)).where(
                    Payment.contribution_id == case["contribution_id"],
                    Payment.provider == PaymentProvider.VNPAY.value,
                )
            )
            == 1
        )


# --- Expired contribution -------------------------------------------------------


def test_expired_contribution_is_rejected(app):
    case = create_direct_booking(app, email_prefix="expired")
    late_now = case["deadline"] + timedelta(seconds=1)
    with app.app_context():
        with pytest.raises(PaymentExpiredError):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=db.session.get(User, case["player_id"]),
                return_url="https://example.test/payments/vnpay/return",
                ip_addr="203.0.113.9",
                now=late_now,
            )
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 0


# --- VNPAY_ENABLED=False fail-closed --------------------------------------------


def test_vnpay_disabled_rejects_before_touching_db_or_client(app, monkeypatch):
    case = create_direct_booking(app, email_prefix="disabled")
    app.config["VNPAY_ENABLED"] = False

    def forbidden(*args, **kwargs):
        pytest.fail("Disabled VNPAY reached the database or the gateway client")

    with app.app_context():
        monkeypatch.setattr(db.session, "scalar", forbidden)
        monkeypatch.setattr(db.session, "scalars", forbidden)
        monkeypatch.setattr(VnpayClient, "from_app_config", classmethod(forbidden))
        with pytest.raises(PaymentError, match="VNPAY"):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=object(),
                return_url="https://example.test/payments/vnpay/return",
                ip_addr="203.0.113.9",
            )


def test_vnpay_disabled_route_returns_404(app, client):
    case = create_direct_booking(app, email_prefix="disabled-route")
    app.config["VNPAY_ENABLED"] = False
    login(client, email="disabled-route-player@example.com")
    response = client.post(
        f"/bookings/{case['booking_code']}/contributions/"
        f"{case['contribution_id']}/payments/vnpay",
    )
    assert response.status_code == 404


# --- Invalid config must not leave an orphan PENDING Payment ------------------


def test_missing_tmn_code_does_not_leave_orphan_pending_payment(app):
    case = create_direct_booking(app, email_prefix="badtmn")
    app.config["VNPAY_TMN_CODE"] = ""
    with app.app_context():
        with pytest.raises(PaymentError):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=db.session.get(User, case["player_id"]),
                return_url="https://example.test/payments/vnpay/return",
                ip_addr="203.0.113.9",
            )
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 0


def test_missing_hash_secret_does_not_leave_orphan_pending_payment(app):
    case = create_direct_booking(app, email_prefix="badsecret")
    app.config["VNPAY_HASH_SECRET"] = ""
    with app.app_context():
        with pytest.raises(PaymentError):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=db.session.get(User, case["player_id"]),
                return_url="https://example.test/payments/vnpay/return",
                ip_addr="203.0.113.9",
            )
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 0


def test_missing_return_url_does_not_leave_orphan_pending_payment(app):
    case = create_direct_booking(app, email_prefix="badreturn")
    with app.app_context():
        with pytest.raises(PaymentError, match="Return URL"):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=db.session.get(User, case["player_id"]),
                return_url="",
                ip_addr="203.0.113.9",
            )
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 0


def test_bad_config_route_does_not_leave_orphan_pending_payment(app, client):
    case = create_direct_booking(app, email_prefix="badconfig-route")
    app.config["VNPAY_RETURN_URL"] = ""
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
    login(client, email=email)

    response = client.post(
        f"/bookings/{case['booking_code']}/contributions/"
        f"{case['contribution_id']}/payments/vnpay",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 0


# --- vnp_IpAddr comes from the real request, never hardcoded -------------------


def test_pay_vnpay_route_forwards_client_remote_addr_as_vnp_ip_addr(app, client):
    case = create_direct_booking(app, email_prefix="ipaddr")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
    login(client, email=email)

    response = client.post(
        f"/bookings/{case['booking_code']}/contributions/"
        f"{case['contribution_id']}/payments/vnpay",
        environ_overrides={"REMOTE_ADDR": "198.51.100.7"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    params = query_dict(response.headers["Location"])
    assert params["vnp_IpAddr"] == "198.51.100.7"


# --- DIRECT_BOOKING / FIND_OPPONENT amounts (400,000 VND booking) --------------


def test_direct_booking_creator_deposit_is_thirty_percent(app):
    case = create_direct_booking(app, email_prefix="direct-amount")
    with app.app_context():
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert contribution.contribution_type == ContributionType.CREATOR.value
        assert contribution.amount_due == Decimal("120000")  # 30% of 400,000
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        assert checkout.payment.amount == Decimal("120000")


def test_find_opponent_creator_and_opponent_each_pay_fifteen_percent(app):
    owner = create_user(app, email="fo-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fo-creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        assert booking.total_amount == Decimal("400000")
        creator_contribution = next(
            item for item in booking.contributions
            if item.contribution_type == ContributionType.CREATOR.value
        )
        opponent_contribution = next(
            item for item in booking.contributions
            if item.contribution_type == ContributionType.OPPONENT.value
        )
        # 30% deposit (120,000) split ~50/50 -> 60,000 creator + 60,000 opponent.
        assert creator_contribution.amount_due == Decimal("60000")
        assert opponent_contribution.amount_due == Decimal("60000")

        checkout = start_vnpay_payment(
            booking_code=booking.booking_code,
            contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        assert checkout.payment.amount == Decimal("60000")


# --- Route-level wiring (checkout initiation only, no return/IPN) --------------


def test_pay_vnpay_route_redirects_to_checkout_url_with_bank_code(app, client):
    case = create_direct_booking(app, email_prefix="route")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
    login(client, email=email)

    response = client.post(
        f"/bookings/{case['booking_code']}/contributions/"
        f"{case['contribution_id']}/payments/vnpay",
        data={"bank_code": "VNPAYQR"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    params = query_dict(response.headers["Location"])
    assert params["vnp_BankCode"] == "VNPAYQR"

    with app.app_context():
        payment = db.session.scalar(
            db.select(Payment).where(
                Payment.contribution_id == case["contribution_id"]
            )
        )
        assert payment.provider == PaymentProvider.VNPAY.value
        assert payment.status == PaymentStatus.PENDING.value


# --- Return URL: read-only, never the source of truth -------------------------


def test_vnpay_return_valid_signature_but_pending_payment_does_not_mutate(app):
    case = create_direct_booking(app, email_prefix="return-pending")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        result = inspect_vnpay_return(payload, client=vnpay)
        assert result.id == checkout.payment.id
        assert result.status == PaymentStatus.PENDING.value

        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.status == BookingStatus.CONFIRMED.value
        assert contribution.status == ContributionStatus.PENDING.value
        assert contribution.amount_paid == 0


def test_vnpay_return_tampered_signature_is_rejected(app):
    case = create_direct_booking(app, email_prefix="return-tamper")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        payload["vnp_ResponseCode"] = "24"  # tamper after signing
        with pytest.raises(PaymentError):
            inspect_vnpay_return(payload, client=vnpay)
        assert (
            db.session.get(Payment, checkout.payment.id).status
            == PaymentStatus.PENDING.value
        )


# --- IPN: success applies existing business logic ------------------------------


def test_vnpay_ipn_success_updates_contribution_and_booking(app):
    case = create_direct_booking(app, email_prefix="ipn-success")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        result = process_vnpay_ipn(payload, client=vnpay)

        assert result.rsp_code == "00"
        payment = db.session.get(Payment, checkout.payment.id)
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert payment.status == PaymentStatus.SUCCESS.value
        assert payment.provider_trans_id == "998877"
        assert payment.result_code == "00"
        assert payment.paid_at is not None
        assert contribution.status == ContributionStatus.PAID.value
        assert contribution.amount_paid == Decimal("120000")
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == Decimal("120000")


def test_vnpay_ipn_duplicate_is_idempotent(app):
    case = create_direct_booking(app, email_prefix="ipn-dup")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        first = process_vnpay_ipn(payload, client=vnpay)
        second = process_vnpay_ipn(payload, client=vnpay)

        assert first.rsp_code == "00"
        assert second.rsp_code == "02"
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.paid_amount == Decimal("120000")  # not doubled
        assert contribution.amount_paid == Decimal("120000")  # not doubled


def test_vnpay_ipn_invalid_signature_returns_97_and_does_not_mutate(app):
    case = create_direct_booking(app, email_prefix="ipn-badsig")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        payload["vnp_Amount"] = "1"  # tamper after signing
        result = process_vnpay_ipn(payload, client=vnpay)
        assert result.rsp_code == "97"
        assert (
            db.session.get(Payment, checkout.payment.id).status
            == PaymentStatus.PENDING.value
        )


def test_vnpay_ipn_unknown_txn_ref_returns_01(app):
    case = create_direct_booking(app, email_prefix="ipn-unknown")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(
            checkout.payment, vnpay, txn_ref="NO-SUCH-ORDER"
        )
        result = process_vnpay_ipn(payload, client=vnpay)
        assert result.rsp_code == "01"


def test_vnpay_ipn_amount_mismatch_returns_04_and_does_not_mutate(app):
    case = create_direct_booking(app, email_prefix="ipn-badamount")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        # Payment.amount is 120,000 VND -> correct vnp_Amount is 12,000,000.
        # Sign a callback that (incorrectly) sends the raw VND value.
        payload = vnpay_callback_payload(checkout.payment, vnpay, amount="120000")
        result = process_vnpay_ipn(payload, client=vnpay)
        assert result.rsp_code == "04"
        assert (
            db.session.get(Payment, checkout.payment.id).status
            == PaymentStatus.PENDING.value
        )


def test_vnpay_ipn_response_code_ok_but_transaction_status_not_is_not_success(app):
    case = create_direct_booking(app, email_prefix="ipn-mixed1")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(
            checkout.payment,
            vnpay,
            response_code="00",
            transaction_status="01",
        )
        result = process_vnpay_ipn(payload, client=vnpay)
        payment = db.session.get(Payment, checkout.payment.id)
        assert payment.status != PaymentStatus.SUCCESS.value
        assert payment.status == PaymentStatus.FAILED.value
        assert result.rsp_code == "00"  # we successfully recorded the outcome


def test_vnpay_ipn_transaction_status_ok_but_response_code_not_is_not_success(app):
    case = create_direct_booking(app, email_prefix="ipn-mixed2")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(
            checkout.payment,
            vnpay,
            response_code="24",
            transaction_status="00",
        )
        result = process_vnpay_ipn(payload, client=vnpay)
        payment = db.session.get(Payment, checkout.payment.id)
        assert payment.status != PaymentStatus.SUCCESS.value
        assert payment.status == PaymentStatus.FAILED.value
        assert result.rsp_code == "00"


def test_vnpay_ipn_failed_transaction_marks_payment_failed(app):
    case = create_direct_booking(app, email_prefix="ipn-failed")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(
            checkout.payment,
            vnpay,
            response_code="24",
            transaction_status="02",
        )
        result = process_vnpay_ipn(payload, client=vnpay)
        payment = db.session.get(Payment, checkout.payment.id)
        assert result.rsp_code == "00"
        assert payment.status == PaymentStatus.FAILED.value
        assert payment.result_code == "24"

        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.status == BookingStatus.CONFIRMED.value
        assert contribution.status == ContributionStatus.PENDING.value
        assert contribution.amount_paid == 0


# --- Late success / expired contribution: recorded for refund, never revived --


def test_vnpay_late_success_does_not_revive_expired_booking_and_queues_refund(app):
    case = create_direct_booking(app, email_prefix="ipn-late")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        late_now = case["deadline"] + timedelta(seconds=1)
        result = process_vnpay_ipn(payload, client=vnpay, now=late_now)

        payment = db.session.get(Payment, checkout.payment.id)
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment.id)
        )

        assert result.rsp_code == "00"
        assert payment.status == PaymentStatus.EXPIRED.value
        assert payment.result_code == "00"
        assert payment.provider_trans_id == "998877"
        assert booking.status == BookingStatus.EXPIRED.value
        assert booking.paid_amount == 0
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == 0
        assert refund is not None
        assert refund.status == RefundStatus.PENDING.value
        assert refund.amount == payment.amount

        # A second (duplicate) late IPN must not queue a second Refund.
        repeated = process_vnpay_ipn(payload, client=vnpay, now=late_now)
        assert repeated.rsp_code == "02"
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1


# --- FIND_OPPONENT: opponent success -> MatchParticipant JOINED ----------------


def test_vnpay_ipn_opponent_success_joins_participant(app):
    owner = create_user(app, email="fo-ipn-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fo-ipn-creator@example.com")
    opponent = create_user(app, email="fo-ipn-opponent@example.com")
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
            title="Kèo kiểm thử VNPAY",
            description="Kiểm tra opponent JOINED sau IPN VNPAY thành công.",
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
        checkout = start_vnpay_payment(
            booking_code=booking.booking_code,
            contribution_id=opponent_contribution.id,
            payer=db.session.get(User, opponent.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
            now=accepted_at,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        result = process_vnpay_ipn(payload, client=vnpay, now=accepted_at)

        db.session.refresh(booking)
        db.session.refresh(match)
        db.session.refresh(participant)
        db.session.refresh(opponent_contribution)

        assert result.rsp_code == "00"
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert match.status == MatchStatus.CONFIRMED.value
        assert opponent_contribution.status == ContributionStatus.PAID.value
        assert booking.status == BookingStatus.PAID.value


# --- Harden 1: EXPIRED without a recorded provider success must still ----------
# --- be processed as a fresh late-success, not short-circuited to 02. ----------


def test_late_success_processes_even_if_payment_already_expired_without_recorded_success(
    app,
):
    case = create_direct_booking(app, email_prefix="expired-unrecorded")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
        booking_id = case["booking_id"]
        contribution_id = case["contribution_id"]

        # Force the exact precondition: Payment already EXPIRED, but no
        # VNPAY success was ever actually recorded for it (no
        # provider_trans_id, no result_code). This should not normally
        # happen through the app's own code today, but the IPN guard must
        # not assume "not PENDING" means "already handled" — it must check
        # what was actually recorded.
        payment = db.session.get(Payment, payment_id)
        payment.status = PaymentStatus.EXPIRED.value
        payment.provider_trans_id = None
        payment.result_code = None
        booking = db.session.get(Booking, booking_id)
        contribution = db.session.get(BookingContribution, contribution_id)
        booking.status = BookingStatus.EXPIRED.value
        contribution.status = ContributionStatus.EXPIRED.value
        db.session.commit()

        payload = vnpay_callback_payload(payment, vnpay)
        result = process_vnpay_ipn(payload, client=vnpay)

        payment = db.session.get(Payment, payment_id)
        booking = db.session.get(Booking, booking_id)
        contribution = db.session.get(BookingContribution, contribution_id)
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == payment_id)
        )

        assert result.rsp_code == "00"  # processed now, NOT short-circuited to 02
        assert payment.status == PaymentStatus.EXPIRED.value
        assert payment.provider_trans_id == "998877"
        assert payment.result_code == "00"
        assert payment.paid_at is not None
        assert booking.status == BookingStatus.EXPIRED.value  # not revived
        assert booking.paid_amount == 0  # not increased
        assert contribution.status == ContributionStatus.EXPIRED.value
        assert contribution.amount_paid == 0
        assert refund is not None
        assert refund.status == RefundStatus.PENDING.value
        assert refund.amount == payment.amount
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1

        # Only the SECOND (duplicate) IPN is idempotent now.
        repeated = process_vnpay_ipn(payload, client=vnpay)
        assert repeated.rsp_code == "02"
        assert db.session.scalar(db.select(db.func.count(Refund.id))) == 1


# --- Harden 2: vnp_PayDate is Vietnam local time, converted to UTC -------------


def test_parse_vnpay_pay_date_treats_value_as_vietnam_time_converted_to_utc():
    from app.services.payment import _parse_vnpay_pay_date

    # 20260912103000 = 10:30:00 Asia/Ho_Chi_Minh (UTC+7) -> 03:30:00 UTC.
    assert _parse_vnpay_pay_date("20260912103000") == datetime(2026, 9, 12, 3, 30, 0)
    assert _parse_vnpay_pay_date(None) is None
    assert _parse_vnpay_pay_date("") is None
    assert _parse_vnpay_pay_date("not-a-date") is None


def test_vnpay_ipn_success_stores_paid_at_converted_from_vietnam_time(app):
    case = create_direct_booking(app, email_prefix="ipn-paydate")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(
            checkout.payment, vnpay, pay_date="20260912103000"
        )
        process_vnpay_ipn(payload, client=vnpay)
        payment = db.session.get(Payment, checkout.payment.id)
        assert payment.paid_at == datetime(2026, 9, 12, 3, 30, 0)


# --- Harden 3: vnp_TmnCode must match our configured terminal code -------------


def test_vnpay_ipn_tmn_code_mismatch_is_rejected_without_mutating_db(app):
    case = create_direct_booking(app, email_prefix="ipn-tmncode")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        # Same hash secret, but the payload claims a different terminal —
        # re-signed so the signature itself is still valid, only vnp_TmnCode
        # no longer matches our configured VNPAY_TMN_CODE.
        other_terminal = VnpayClient(
            tmn_code="OTHERCODE99",
            hash_secret=VNPAY_HASH_SECRET,
            payment_url=VNPAY_PAYMENT_URL,
            api_url=VNPAY_API_URL,
        )
        payload["vnp_TmnCode"] = "OTHERCODE99"
        payload["vnp_SecureHash"] = other_terminal._sign(payload)

        result = process_vnpay_ipn(payload, client=vnpay)
        assert result.rsp_code == "97"
        assert (
            db.session.get(Payment, checkout.payment.id).status
            == PaymentStatus.PENDING.value
        )


def test_vnpay_return_tmn_code_mismatch_is_rejected(app):
    case = create_direct_booking(app, email_prefix="return-tmncode")
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        other_terminal = VnpayClient(
            tmn_code="OTHERCODE99",
            hash_secret=VNPAY_HASH_SECRET,
            payment_url=VNPAY_PAYMENT_URL,
            api_url=VNPAY_API_URL,
        )
        payload["vnp_TmnCode"] = "OTHERCODE99"
        payload["vnp_SecureHash"] = other_terminal._sign(payload)

        with pytest.raises(PaymentError):
            inspect_vnpay_return(payload, client=vnpay)
        assert (
            db.session.get(Payment, checkout.payment.id).status
            == PaymentStatus.PENDING.value
        )


@pytest.fixture(autouse=True)
def enable_vnpay_in_isolated_tests(app):
    app.config.update(
        VNPAY_ENABLED=True,
        VNPAY_TMN_CODE="TESTCODE01",
        VNPAY_HASH_SECRET="SECRETKEY123",
        VNPAY_PAYMENT_URL="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        VNPAY_API_URL="https://sandbox.vnpayment.vn/merchant_webapi/api/transaction",
        VNPAY_TIMEOUT_SECONDS=30,
        VNPAY_RETURN_URL="https://example.test/payments/vnpay/return",
    )
