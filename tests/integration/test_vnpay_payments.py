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
    decide_match_request,
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


# --- Harden 4: vnp_ExpireDate is always present, GMT+7, after create_date -----


def test_vnp_expire_date_uses_contribution_deadline_in_vietnam_time():
    from app.services.payment import _vnpay_expire_date

    class FakeContribution:
        expires_at = datetime(2026, 9, 12, 5, 0, 0)  # naive UTC, after now

    current_utc = datetime(2026, 9, 12, 3, 30, 0)
    result = _vnpay_expire_date(contribution=FakeContribution(), current_utc=current_utc)
    assert result == "20260912120000"  # 05:00 UTC + 7h = 12:00 Asia/Ho_Chi_Minh


def test_vnp_expire_date_falls_back_to_fifteen_minutes_when_no_deadline():
    from app.services.payment import _vnpay_expire_date

    class FakeContribution:
        expires_at = None

    current_utc = datetime(2026, 9, 12, 3, 30, 0)
    result = _vnpay_expire_date(contribution=FakeContribution(), current_utc=current_utc)
    assert result == "20260912104500"  # 03:30 UTC + 15m = 03:45 UTC = 10:45 VN


def test_vnp_expire_date_falls_back_when_deadline_already_passed():
    from app.services.payment import _vnpay_expire_date

    class FakeContribution:
        expires_at = datetime(2026, 9, 12, 3, 0, 0)  # before current_utc

    current_utc = datetime(2026, 9, 12, 3, 30, 0)
    result = _vnpay_expire_date(contribution=FakeContribution(), current_utc=current_utc)
    assert result == "20260912104500"  # falls back, not the stale deadline


def test_checkout_url_always_includes_vnp_expire_date_after_create_date(app):
    case = create_direct_booking(app, email_prefix="expiredate")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        params = query_dict(checkout.pay_url)
        assert "vnp_ExpireDate" in params
        assert len(params["vnp_ExpireDate"]) == 14
        # Fixed-width yyyyMMddHHmmss -> lexicographic order == chronological.
        assert params["vnp_ExpireDate"] > params["vnp_CreateDate"]


def test_checkout_url_expire_date_matches_contribution_deadline(app):
    case = create_direct_booking(app, email_prefix="expiredate-real")
    with app.app_context():
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        deadline = contribution.expires_at
        assert deadline is not None  # CREATOR contribution always has one
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        params = query_dict(checkout.pay_url)
        expected_vn = deadline + timedelta(hours=7)
        assert params["vnp_ExpireDate"] == expected_vn.strftime("%Y%m%d%H%M%S")


# --- Harden 5: vnp_TxnRef is alphanumeric only (no "-") ------------------------


def test_vnp_txn_ref_is_alphanumeric_only_and_within_length_limit(app):
    import re

    case = create_direct_booking(app, email_prefix="txnref-alnum")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        order_id = checkout.payment.order_id
        params = query_dict(checkout.pay_url)
        assert params["vnp_TxnRef"] == order_id
        assert re.fullmatch(r"[A-Za-z0-9]+", order_id)
        assert "-" not in order_id
        assert len(order_id) <= 100


# --- Step 4: UI visibility ------------------------------------------------------


def test_vnpay_buttons_hidden_when_disabled(app, client):
    case = create_direct_booking(app, email_prefix="ui-disabled")
    app.config["VNPAY_ENABLED"] = False
    with app.app_context():
        email = db.session.get(User, case["player_id"]).email
    login(client, email=email)

    response = client.get(f"/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" not in page
    assert "payments/vnpay" not in page
    assert "Thanh toán mô phỏng" in page  # MOCK button unaffected


def test_vnpay_buttons_visible_for_direct_booking_creator_when_enabled(app, client):
    case = create_direct_booking(app, email_prefix="ui-direct")
    with app.app_context():
        email = db.session.get(User, case["player_id"]).email
    login(client, email=email)

    response = client.get(f"/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Thanh toán qua VNPAY" in page
    assert "Thanh toán mô phỏng" in page  # MOCK still shown alongside — no regression


def test_vnpay_qr_option_removed_from_ui_only_one_vnpay_button_remains(app, client):
    """The separate VNPAY-QR button was removed from the User UI (VNPAYQR
    stays fully supported at the VnpayClient/service layer for potential
    future reuse — see test_bank_code_vnpayqr_adds_vnp_bank_code_without_changing_payment_method
    and the QR routing-mode tests below). Only the single "Thanh toán qua
    VNPAY" action remains, and it must never send bank_code.
    """
    case = create_direct_booking(app, email_prefix="ui-normal")
    with app.app_context():
        email = db.session.get(User, case["player_id"]).email
    login(client, email=email)

    response = client.get(f"/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert "Quét VNPAY-QR" not in page
    assert "VNPAYQR" not in page
    assert page.count('name="bank_code"') == 0
    assert page.count('action="/bookings/') >= 1  # the single VNPAY form is present


def test_vnpay_buttons_visible_for_find_opponent_creator(app, client):
    owner = create_user(app, email="fo-ui-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fo-ui-creator@example.com")
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
        booking_code = booking.booking_code
    login(client, email=creator.email)

    response = client.get(f"/bookings/{booking_code}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Thanh toán qua VNPAY" in page
    assert "Quét VNPAY-QR" not in page


def test_vnpay_buttons_visible_for_find_opponent_opponent(app, client):
    owner = create_user(app, email="fo-opp-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fo-opp-creator@example.com")
    opponent = create_user(app, email="fo-opp-opponent@example.com")
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
            title="Kèo kiểm thử UI VNPAY",
            description="Kiểm tra nút VNPAY trên trang opponent.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000001",
            share_contact=True,
        )
        request_to_join_match(
            match_id=match.id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        match_id = match.id
    login(client, email=opponent.email)

    response = client.get(f"/matches/{match_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Thanh toán qua VNPAY" in page
    assert "Quét VNPAY-QR" not in page


def test_find_players_participant_has_no_online_payment_action_even_when_enabled(
    app, client
):
    from tests.integration.test_matchmaking import _create_match, _create_split_booking

    owner = create_user(app, email="fp-ui-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="fp-ui-creator@example.com")
    player = create_user(app, email="fp-ui-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=1,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)
    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, player.id),
            contact_phone="0901000009",
            share_contact=True,
        )
        decide_match_request(
            match_id=match_id,
            participant_id=participant.id,
            creator=db.session.get(User, creator.id),
            accept=True,
        )
    login(client, email=player.email)

    response = client.get(f"/matches/{match_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" not in page
    assert "payments/vnpay" not in page


def test_owner_view_never_shows_vnpay_action(app, client):
    case = create_direct_booking(app, email_prefix="ui-owner")
    login(client, email="ui-owner-owner@example.com")

    response = client.get(f"/owner/bookings/{case['booking_code']}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "VNPAY" not in page
    assert "payments/vnpay" not in page


# --- Step 4: cleanup B - VNPAY_VERSION / VNPAY_LOCALE actually used ------------


def test_custom_vnpay_version_and_locale_are_used_in_checkout_url(app):
    case = create_direct_booking(app, email_prefix="verlocale")
    app.config["VNPAY_VERSION"] = "2.2.0"
    app.config["VNPAY_LOCALE"] = "en"
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        params = query_dict(checkout.pay_url)
        assert params["vnp_Version"] == "2.2.0"
        assert params["vnp_Locale"] == "en"


def test_default_vnpay_version_and_locale_when_not_customized(app):
    case = create_direct_booking(app, email_prefix="verlocale-default")
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        params = query_dict(checkout.pay_url)
        assert params["vnp_Version"] == "2.1.0"
        assert params["vnp_Locale"] == "vn"


# --- Step 5 Fix 1: PENDING checkout reuse must match the routing mode ---------


def test_normal_to_normal_reuses_same_pending_checkout(app):
    case = create_direct_booking(app, email_prefix="route-normal-normal")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        first = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        second = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
        )
        assert first.payment.id == second.payment.id
        assert first.pay_url == second.pay_url
        assert (
            db.session.scalar(
                db.select(db.func.count(Payment.id)).where(
                    Payment.contribution_id == case["contribution_id"]
                )
            )
            == 1
        )


def test_qr_to_qr_reuses_same_pending_checkout(app):
    case = create_direct_booking(app, email_prefix="route-qr-qr")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        first = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        second = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        assert first.payment.id == second.payment.id
        assert first.pay_url == second.pay_url


def test_qr_to_normal_retires_old_checkout_and_creates_new_one(app):
    case = create_direct_booking(app, email_prefix="route-qr-normal")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        qr_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        normal_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
        )
        assert normal_checkout.payment.id != qr_checkout.payment.id
        retired = db.session.get(Payment, qr_checkout.payment.id)
        # EXPIRED, not CANCELLED: the old signed checkout URL may still be
        # live at VNPAY, and a genuine SUCCESS IPN for it must still be
        # processed (see test_old_expired_checkout_success_before_new_one
        # and test_old_expired_checkout_success_after_new_one_succeeds).
        assert retired.status == PaymentStatus.EXPIRED.value
        assert "vnp_BankCode" not in query_dict(normal_checkout.pay_url)
        assert (
            db.session.scalar(
                db.select(db.func.count(Payment.id)).where(
                    Payment.contribution_id == case["contribution_id"],
                    Payment.provider == PaymentProvider.VNPAY.value,
                )
            )
            == 2
        )
        assert (
            db.session.scalar(
                db.select(db.func.count(Payment.id)).where(
                    Payment.contribution_id == case["contribution_id"],
                    Payment.status == PaymentStatus.PENDING.value,
                )
            )
            == 1
        )


def test_normal_to_qr_retires_old_checkout_and_creates_new_one(app):
    case = create_direct_booking(app, email_prefix="route-normal-qr")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        normal_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
        )
        qr_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        assert qr_checkout.payment.id != normal_checkout.payment.id
        retired = db.session.get(Payment, normal_checkout.payment.id)
        assert retired.status == PaymentStatus.EXPIRED.value
        assert query_dict(qr_checkout.pay_url)["vnp_BankCode"] == "VNPAYQR"


def test_old_expired_checkout_success_before_new_one_applies_normally(app):
    """Case A: the retired (EXPIRED) checkout's own SUCCESS IPN arrives
    before the new checkout ever succeeds. It must NOT be treated as
    already-confirmed (02) — it is the real, still-outstanding payment for
    this contribution and must be applied exactly like any normal success.
    """
    case = create_direct_booking(app, email_prefix="expired-success-first")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        old_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
            client=vnpay,
        )
        start_vnpay_payment(  # switch routing mode -> retires old as EXPIRED
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
            client=vnpay,
        )
        old_payment = db.session.get(Payment, old_checkout.payment.id)
        assert old_payment.status == PaymentStatus.EXPIRED.value

        payload = vnpay_callback_payload(old_payment, vnpay, transaction_no="111111")
        result = process_vnpay_ipn(payload, client=vnpay)

        assert result.rsp_code == "00"  # NOT "02" — must not be short-circuited
        old_payment = db.session.get(Payment, old_checkout.payment.id)
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert old_payment.status == PaymentStatus.SUCCESS.value
        assert old_payment.provider_trans_id == "111111"
        assert contribution.status == ContributionStatus.PAID.value
        assert contribution.amount_paid == Decimal("120000")
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == Decimal("120000")  # paid exactly once


def test_old_expired_checkout_success_after_new_one_succeeds_queues_refund(app):
    """Case B: the NEW checkout succeeds first (fulfils the contribution),
    then the old EXPIRED checkout's SUCCESS IPN arrives late. It must follow
    the existing late-payment/refund-queue path — never double-count the
    booking, never get silently dropped either.
    """
    case = create_direct_booking(app, email_prefix="expired-success-second")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        old_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
            client=vnpay,
        )
        new_checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
            client=vnpay,
        )
        old_payment = db.session.get(Payment, old_checkout.payment.id)
        assert old_payment.status == PaymentStatus.EXPIRED.value

        new_payload = vnpay_callback_payload(
            new_checkout.payment, vnpay, transaction_no="222222"
        )
        new_result = process_vnpay_ipn(new_payload, client=vnpay)
        assert new_result.rsp_code == "00"
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert contribution.status == ContributionStatus.PAID.value
        assert booking.paid_amount == Decimal("120000")

        old_payload = vnpay_callback_payload(
            old_payment, vnpay, transaction_no="111111"
        )
        old_result = process_vnpay_ipn(old_payload, client=vnpay)

        # Processed (recorded + queued for refund) — not silently dropped.
        assert old_result.rsp_code == "00"
        old_payment = db.session.get(Payment, old_checkout.payment.id)
        booking = db.session.get(Booking, case["booking_id"])
        refund = db.session.scalar(
            db.select(Refund).where(Refund.payment_id == old_payment.id)
        )
        assert old_payment.status == PaymentStatus.EXPIRED.value
        assert old_payment.provider_trans_id == "111111"
        assert booking.paid_amount == Decimal("120000")  # NOT doubled
        assert refund is not None
        assert refund.status == RefundStatus.PENDING.value
        assert refund.amount == old_payment.amount


def test_switching_routing_mode_does_not_alter_paid_amounts(app):
    case = create_direct_booking(app, email_prefix="route-amounts-unchanged")
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code="VNPAYQR",
        )
        start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            bank_code=None,
        )
        booking = db.session.get(Booking, case["booking_id"])
        contribution = db.session.get(BookingContribution, case["contribution_id"])
        assert booking.paid_amount == 0
        assert contribution.amount_paid == 0
        assert contribution.status == ContributionStatus.PENDING.value


def test_switching_routing_mode_never_retires_a_success_payment(app):
    case = create_direct_booking(app, email_prefix="route-success-untouched")
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
        success_payment_id = checkout.payment.id
        assert (
            db.session.get(Payment, success_payment_id).status
            == PaymentStatus.SUCCESS.value
        )

        # Contribution is now PAID; any further checkout attempt (even a
        # routing-mode switch) must be rejected before it can ever touch the
        # SUCCESS row.
        with pytest.raises(PaymentError):
            start_vnpay_payment(
                booking_code=case["booking_code"],
                contribution_id=case["contribution_id"],
                payer=player,
                return_url="https://example.test/payments/vnpay/return",
                ip_addr="203.0.113.9",
                bank_code="VNPAYQR",
            )
        assert (
            db.session.get(Payment, success_payment_id).status
            == PaymentStatus.SUCCESS.value
        )


# --- Step 5 Fix 2: payment watch after Return / IPN ----------------------------


def test_pending_return_redirects_with_payment_watch_marker(app, client):
    case = create_direct_booking(app, email_prefix="watch-pending")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
        payload = vnpay_callback_payload(checkout.payment, vnpay)
    login(client, email=email)

    response = client.get(
        "/payments/vnpay/return", query_string=payload, follow_redirects=False
    )
    assert response.status_code == 302
    assert f"payment_watch={payment_id}" in response.headers["Location"]

    with app.app_context():
        assert db.session.get(Payment, payment_id).status == PaymentStatus.PENDING.value


def test_booking_detail_renders_watch_marker_for_pending_vnpay_payment(app, client):
    case = create_direct_booking(app, email_prefix="watch-marker-render")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
    login(client, email=email)

    response = client.get(f"/bookings/{case['booking_code']}?payment_watch={payment_id}")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-vnpay-payment-watch" in page
    assert f"/payments/vnpay/{payment_id}/status" in page


def test_status_endpoint_returns_pending(app, client):
    case = create_direct_booking(app, email_prefix="watch-status-pending")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
    login(client, email=email)

    response = client.get(f"/payments/vnpay/{payment_id}/status")
    assert response.status_code == 200
    assert response.get_json() == {"status": "PENDING"}


def test_status_endpoint_returns_success_after_valid_ipn(app, client):
    case = create_direct_booking(app, email_prefix="watch-status-success")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        process_vnpay_ipn(payload, client=vnpay)
    login(client, email=email)

    response = client.get(f"/payments/vnpay/{payment_id}/status")
    assert response.status_code == 200
    assert response.get_json() == {"status": "SUCCESS"}


def test_status_endpoint_rejects_another_user(app, client):
    case = create_direct_booking(app, email_prefix="watch-status-otheruser")
    intruder = create_user(
        app, email="watch-status-otheruser-intruder@example.com"
    )
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
    login(client, email=intruder.email)

    response = client.get(f"/payments/vnpay/{payment_id}/status")
    assert response.status_code == 403


def test_status_endpoint_rejects_nonexistent_payment(app, client):
    case = create_direct_booking(app, email_prefix="watch-status-missing")
    with app.app_context():
        email = db.session.get(User, case["player_id"]).email
    login(client, email=email)

    response = client.get("/payments/vnpay/999999/status")
    assert response.status_code == 404


def test_return_still_does_not_mutate_payment_even_with_watch_flow(app, client):
    case = create_direct_booking(app, email_prefix="watch-return-no-mutate")
    vnpay = build_vnpay_client()
    with app.app_context():
        player = db.session.get(User, case["player_id"])
        email = player.email
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=player,
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
        payload = vnpay_callback_payload(checkout.payment, vnpay)
    login(client, email=email)

    client.get("/payments/vnpay/return", query_string=payload, follow_redirects=False)

    with app.app_context():
        assert db.session.get(Payment, payment_id).status == PaymentStatus.PENDING.value


def test_watch_marker_stops_resolving_once_payment_is_terminal(app):
    """Once status leaves PENDING the marker must stop resolving — this is
    exactly what prevents the client-side poll from ever causing a reload
    loop (no marker on the reloaded page => no new poll is started)."""
    from types import SimpleNamespace

    from app.routes.payments import resolve_watchable_vnpay_payment_id

    case = create_direct_booking(app, email_prefix="watch-no-reload-loop")
    vnpay = build_vnpay_client()
    with app.app_context():
        player_id = case["player_id"]
        checkout = start_vnpay_payment(
            booking_code=case["booking_code"],
            contribution_id=case["contribution_id"],
            payer=db.session.get(User, player_id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = checkout.payment.id
        booking_id = case["booking_id"]
        payload = vnpay_callback_payload(checkout.payment, vnpay)

        with app.test_request_context(f"/bookings/x?payment_watch={payment_id}"):
            assert (
                resolve_watchable_vnpay_payment_id(
                    user=SimpleNamespace(id=player_id), booking_id=booking_id
                )
                == payment_id
            )

        process_vnpay_ipn(payload, client=vnpay)

        with app.test_request_context(f"/bookings/x?payment_watch={payment_id}"):
            assert (
                resolve_watchable_vnpay_payment_id(
                    user=SimpleNamespace(id=player_id), booking_id=booking_id
                )
                is None
            )


# --- Step 5 cleanup: payment_watch must be bound to the viewed resource -------


def test_payment_watch_cannot_activate_across_different_bookings(app, client):
    case_a = create_direct_booking(app, email_prefix="watch-cross-booking")
    with app.app_context():
        player = db.session.get(User, case_a["player_id"])
        email = player.email
        player_id = player.id

    owner_b = create_user(
        app, email="watch-cross-booking-ownerB@example.com", role=UserRole.OWNER
    )
    _, field_id_b = create_bookable_field(app, owner_id=owner_b.id)
    with app.app_context():
        booking_b = create_booking(
            user=db.session.get(User, player_id),
            field_id=field_id_b,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        booking_b_code = booking_b.booking_code

    vnpay = build_vnpay_client()
    with app.app_context():
        checkout_a = start_vnpay_payment(
            booking_code=case_a["booking_code"],
            contribution_id=case_a["contribution_id"],
            payer=db.session.get(User, player_id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_a_id = checkout_a.payment.id

    login(client, email=email)

    # Booking A's payment must NOT activate the watcher on Booking B's page.
    response = client.get(
        f"/bookings/{booking_b_code}?payment_watch={payment_a_id}"
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-vnpay-payment-watch" not in page

    # The same payment must still activate on its OWN booking's page.
    response = client.get(
        f"/bookings/{case_a['booking_code']}?payment_watch={payment_a_id}"
    )
    page = response.get_data(as_text=True)
    assert "data-vnpay-payment-watch" in page


def _setup_opponent_payment_and_two_matches(app, *, email_prefix: str) -> dict:
    owner = create_user(
        app, email=f"{email_prefix}-owner@example.com", role=UserRole.OWNER
    )
    creator_a = create_user(app, email=f"{email_prefix}-creator-a@example.com")
    opponent = create_user(app, email=f"{email_prefix}-opponent@example.com")
    creator_b = create_user(app, email=f"{email_prefix}-creator-b@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    # Separate field for booking B — same date/time as booking A would
    # otherwise conflict as a double-booking on the same field.
    _, field_id_b = create_bookable_field(app, owner_id=owner.id)
    vnpay = build_vnpay_client()

    with app.app_context():
        booking_a = create_booking(
            user=db.session.get(User, creator_a.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        creator_a_contribution = next(
            item for item in booking_a.contributions if item.user_id == creator_a.id
        )
        pay_contribution_with_mock(
            booking_code=booking_a.booking_code,
            contribution_id=creator_a_contribution.id,
            payer=db.session.get(User, creator_a.id),
        )
        match_a = create_match(
            booking_code=booking_a.booking_code,
            creator=db.session.get(User, creator_a.id),
            title="Kèo A",
            description="Kèo kiểm thử payment_watch A.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000001",
            share_contact=True,
        )
        participant = request_to_join_match(
            match_id=match_a.id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        opponent_checkout = start_vnpay_payment(
            booking_code=booking_a.booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id),
            return_url="https://example.test/payments/vnpay/return",
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payment_id = opponent_checkout.payment.id
        match_a_id = match_a.id

        # A second, unrelated FIND_OPPONENT booking/match (different field,
        # so it never conflicts with booking A's own slot).
        booking_b = create_booking(
            user=db.session.get(User, creator_b.id),
            field_id=field_id_b,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        creator_b_contribution = next(
            item for item in booking_b.contributions if item.user_id == creator_b.id
        )
        pay_contribution_with_mock(
            booking_code=booking_b.booking_code,
            contribution_id=creator_b_contribution.id,
            payer=db.session.get(User, creator_b.id),
        )
        match_b = create_match(
            booking_code=booking_b.booking_code,
            creator=db.session.get(User, creator_b.id),
            title="Kèo B",
            description="Kèo không liên quan.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000003",
            share_contact=True,
        )
        match_b_id = match_b.id

    return {
        "opponent_email": opponent.email,
        "payment_id": payment_id,
        "match_a_id": match_a_id,
        "match_b_id": match_b_id,
    }


def test_payment_watch_cannot_activate_on_unrelated_match(app, client):
    scenario = _setup_opponent_payment_and_two_matches(
        app, email_prefix="watch-match-unrelated"
    )
    login(client, email=scenario["opponent_email"])

    response = client.get(
        f"/matches/{scenario['match_b_id']}?payment_watch={scenario['payment_id']}"
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-vnpay-payment-watch" not in page


def test_payment_watch_activates_on_correct_match(app, client):
    scenario = _setup_opponent_payment_and_two_matches(
        app, email_prefix="watch-match-correct"
    )
    login(client, email=scenario["opponent_email"])

    response = client.get(
        f"/matches/{scenario['match_a_id']}?payment_watch={scenario['payment_id']}"
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-vnpay-payment-watch" in page
    assert f"/payments/vnpay/{scenario['payment_id']}/status" in page


# --- Step 5 Fix 3: payment buttons must reset after BFCache restore -----------
# The project has no JS execution test harness (no headless browser runner),
# so these are source-level regression guards on app/static/js/booking-detail.js
# — the same file bookings/detail.html and matches/detail.html both load —
# rather than a behavioral browser test.


def _booking_detail_js_source() -> str:
    from pathlib import Path

    js_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "static"
        / "js"
        / "booking-detail.js"
    )
    return js_path.read_text(encoding="utf-8")


def test_payment_button_js_listens_for_pageshow_and_restores_original_content():
    source = _booking_detail_js_source()
    assert "pageshow" in source
    assert "event.persisted" in source
    assert "originalContent" in source
    assert "button.disabled = false" in source


def test_payment_button_js_restores_inner_html_to_preserve_icons():
    """Regression guard: an earlier version restored button.textContent,
    which silently dropped the VNPAY-QR button's <i class="bi bi-qr-code">
    icon on BFCache restore. Must capture/restore innerHTML instead."""
    source = _booking_detail_js_source()
    assert "const originalContent = button.innerHTML;" in source
    assert "button.innerHTML = button.dataset.originalContent;" in source


def test_payment_button_js_only_resets_buttons_it_disabled_for_submit():
    source = _booking_detail_js_source()
    # Marker set only inside the submit handler, so the countdown-expiry
    # disable path (a different code path, no marker) is never re-enabled.
    assert "data-payment-submitting" in source


def test_payment_button_js_countdown_disable_path_sets_no_submitting_marker():
    """The countdown-expiry disable path must stay a plain, permanent
    disable with no data-payment-submitting marker — otherwise a BFCache
    restore would incorrectly re-enable a button the countdown legitimately
    disabled."""
    source = _booking_detail_js_source()
    countdown_disable_snippet = (
        'querySelectorAll("[data-payment-submit]").forEach((button) => {\n'
        "                    button.disabled = true;\n"
        "                });"
    )
    assert countdown_disable_snippet in source


def test_payment_button_js_keeps_double_submit_protection():
    source = _booking_detail_js_source()
    assert "button.disabled = true" in source
    assert "Đang xử lý" in source


def test_payment_watch_js_polling_is_bounded_and_reloads_once():
    source = _booking_detail_js_source()
    assert "data-vnpay-payment-watch" in source
    assert "MAX_ATTEMPTS" in source
    assert "MAX_CONSECUTIVE_FAILURES" in source
    assert "clearInterval" in source
    assert "window.location.reload" in source


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
