"""Phase 4.1A presentation and verified browser-return boundaries."""

import html
import json
import re
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event

from app.extensions import db
from app.integrations import MomoClient
from app.models import Booking, Match, Payment, Refund, User, UserRole, Venue
from app.services import (
    create_booking, create_match, process_momo_payment_notification,
    request_to_join_match, start_momo_payment,
)
from tests.integration.test_bookings import (
    booking_day, booking_form_data, create_bookable_field, create_user, login,
)
from tests.integration.test_momo_payments import build_client, payment_notification, sign


def create_return_journey(app):
    owner = create_user(app, email="journey-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="journey-creator@example.com")
    opponent = create_user(app, email="journey-opponent@example.com")
    venue_id, field_id = create_bookable_field(app, owner_id=owner.id)
    momo = build_client()
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id), field_id=field_id,
            booking_date=booking_day(), start_time=time(18), end_time=time(20),
            booking_mode="FIND_OPPONENT",
        )
        creator_contribution = next(c for c in booking.contributions if c.user_id == creator.id)
        creator_checkout = start_momo_payment(
            booking_code=booking.booking_code, contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator.id), client=momo,
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
        )
        creator_payload = payment_notification(creator_checkout.payment)
        process_momo_payment_notification(creator_payload, client=momo)
        match = create_match(
            booking_code=booking.booking_code, creator=db.session.get(User, creator.id),
            title="Giao hữu cuối tuần", description="Kèo kiểm thử hành trình đặt sân.",
            skill_level="INTERMEDIATE", contact_phone="0901000001", share_contact=True,
        )
        participant = request_to_join_match(
            match_id=match.id, user=db.session.get(User, opponent.id),
            contact_phone="0901000002", share_contact=True,
        )
        opponent_checkout = start_momo_payment(
            booking_code=booking.booking_code, contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id), client=momo,
            redirect_url="https://example.test/payments/momo/return",
            ipn_url="https://example.test/payments/momo/ipn",
        )
        return dict(
            creator=creator, opponent=opponent, momo=momo, venue_id=venue_id,
            field_id=field_id, booking_id=booking.id, booking_code=booking.booking_code,
            match_id=match.id, creator_payment_id=creator_checkout.payment.id,
            opponent_payment_id=opponent_checkout.payment.id,
            creator_payload=creator_payload,
            opponent_payload=payment_notification(opponent_checkout.payment),
        )


@pytest.fixture()
def journey(app, monkeypatch):
    case = create_return_journey(app)
    monkeypatch.setattr(MomoClient, "from_app_config", classmethod(lambda cls: case["momo"]))
    return case


@pytest.mark.parametrize("payer", ["creator", "opponent"])
@pytest.mark.parametrize("status", ["SUCCESS", "PENDING", "FAILED", "EXPIRED"])
def test_verified_return_uses_relationship_and_never_writes(app, client, journey, payer, status):
    with app.app_context():
        # Exercise stored outcomes independently of callback resultCode.
        db.session.get(Payment, journey[f"{payer}_payment_id"]).status = status
        db.session.commit()
        engine = db.engine
    login(client, email=journey[payer].email)
    writes = []

    def record_writes(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {"UPDATE", "INSERT", "DELETE"}:
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", record_writes)
    try:
        response = client.get("/payments/momo/return", query_string={
            **journey[f"{payer}_payload"], "return_to_match": "999999",
            "next": "https://evil.example/", "booking_code": "untrusted",
        })
        expected = (f"/matches/{journey['match_id']}" if payer == "opponent"
                    else f"/bookings/{journey['booking_code']}")
        assert response.status_code == 302
        assert response.location == expected
        assert client.get(response.location).status_code == 200
        assert not writes
    finally:
        event.remove(engine, "before_cursor_execute", record_writes)
    if payer == "opponent":
        assert client.get(f"/bookings/{journey['booking_code']}").status_code == 403


@pytest.mark.parametrize("tamper", ["signature", "amount", "requestId", "orderId"])
def test_invalid_callback_does_not_choose_a_booking_or_match(app, client, journey, tamper):
    login(client, email=journey["opponent"].email)
    payload = dict(journey["opponent_payload"])
    payload[tamper] = 1 if tamper == "amount" else "tampered"
    if tamper != "signature":
        payload.pop("signature")
        payload["signature"] = sign({"accessKey": "sandbox-access", **payload})
    response = client.get("/payments/momo/return", query_string=payload)
    assert response.location == "/bookings"
    with app.app_context():
        assert db.session.get(Payment, journey["opponent_payment_id"]).status == "PENDING"
        assert db.session.get(Booking, journey["booking_id"]).paid_amount == Decimal("60000")


def test_return_without_session_or_with_another_account_is_safe(client, journey):
    response = client.get("/payments/momo/return", query_string=journey["creator_payload"])
    assert urlsplit(response.location).path == "/auth/login"
    assert parse_qs(urlsplit(response.location).query) == {"next": ["/bookings"]}
    assert client.get(response.location).status_code == 200
    response = client.get("/payments/momo/return", query_string=journey["opponent_payload"])
    assert response.location == f"/matches/{journey['match_id']}"
    assert client.get(response.location).status_code == 200
    login(client, email=journey["opponent"].email)
    response = client.get("/payments/momo/return", query_string=journey["creator_payload"])
    assert response.location == "/bookings"


def test_signed_cancel_return_does_not_override_pending_ipn(app, client, journey):
    login(client, email=journey["opponent"].email)
    payload = dict(journey["opponent_payload"])
    payload.pop("signature")
    payload.update(resultCode=1006, message="User cancelled")
    payload["signature"] = sign({"accessKey": "sandbox-access", **payload})
    response = client.get("/payments/momo/return", query_string=payload)
    assert response.location == f"/matches/{journey['match_id']}"
    with app.app_context():
        assert db.session.get(Payment, journey["opponent_payment_id"]).status == "PENDING"


@pytest.mark.parametrize("mode", ["DIRECT_BOOKING", "FIND_PLAYERS"])
def test_non_opponent_confirmation_starts_hidden_and_uses_30_70_quote(client, journey, mode):
    login(client, email=journey["creator"].email)
    base = f"/venues/{journey['venue_id']}/fields/{journey['field_id']}/bookings"
    body = client.get(f"{base}/new").get_data(as_text=True)
    assert '<div data-review-opponent-row hidden>' in body
    data = booking_form_data(
        booking_day(), start_hour="06", end_hour="07", booking_mode=mode,
    )
    if mode == "FIND_PLAYERS":
        data["requested_players"] = "2"
    response = client.post(f"{base}/quote", data=data)
    assert response.status_code == 200
    quote = response.get_json()
    assert Decimal(quote["deposit_amount"]) == Decimal("60000")
    assert Decimal(quote["venue_balance"]) == Decimal("140000")
    assert Decimal(quote["contribution_plan"]["external_amount"]) == 0


def test_initial_deadline_expiry_renders_no_payment_without_persisting_status(app, client, journey):
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, journey["creator"].id), field_id=journey["field_id"],
            booking_date=booking_day(), start_time=time(6), end_time=time(7),
            booking_mode="DIRECT_BOOKING",
        )
        booking.initial_payment_due_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.session.commit()
        booking_id, code = booking.id, booking.booking_code
    login(client, email=journey["creator"].email)
    body = client.get(f"/bookings/{code}").get_data(as_text=True)
    assert "data-payment-submit" not in body
    assert "data-initial-payment-countdown" not in body
    assert "hết hạn" in body
    with app.app_context():
        assert db.session.get(Booking, booking_id).status == "CONFIRMED"


def test_existing_cancelled_match_is_linked_and_never_recreated(app, client, journey):
    with app.app_context():
        db.session.get(Match, journey["match_id"]).status = "CANCELLED"
        db.session.commit()
    login(client, email=journey["creator"].email)
    body = client.get(f"/bookings/{journey['booking_code']}").get_data(as_text=True)
    assert f'href="/matches/{journey["match_id"]}"' in body
    assert "Đăng kèo tìm đối thủ" not in body


def test_started_booking_hides_cancel_and_create_match(app, client, journey, monkeypatch):
    with app.app_context():
        # Remove only the relationship in this isolated fixture to exercise the create CTA.
        booking = db.session.get(Booking, journey["booking_id"])
        target = datetime.combine(booking.booking_date, booking.start_time)
        match = db.session.get(Match, journey["match_id"])
        for participant in list(match.participants):
            db.session.delete(participant)
        db.session.delete(match)
        db.session.commit()
    login(client, email=journey["creator"].email)
    path = f"/bookings/{journey['booking_code']}"
    before = client.get(path).get_data(as_text=True)
    assert "Đăng kèo tìm đối thủ" in before
    assert f'action="{path}/cancel"' in before
    monkeypatch.setattr("app.routes.bookings.current_vietnam_datetime", lambda: target)
    body = client.get(path).get_data(as_text=True)
    assert "Đăng kèo tìm đối thủ" not in body
    assert f'action="{path}/cancel"' not in body


def test_find_players_booking_uses_saved_match_type_and_title(app, client, journey):
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, journey["creator"].id),
            field_id=journey["field_id"],
            booking_date=booking_day(),
            start_time=time(6),
            end_time=time(7),
            booking_mode="FIND_PLAYERS",
            requested_players=2,
        )
        booking.status = "PAID"
        booking.paid_amount = booking.deposit_amount
        db.session.commit()
        match = create_match(
            booking_code=booking.booking_code,
            creator=db.session.get(User, journey["creator"].id),
            title="Tìm thêm người chơi cuối tuần",
            contact_phone="0901000001",
            share_contact=True,
        )
        booking_code = booking.booking_code
        match_id = match.id

    login(client, email=journey["creator"].email)
    body = client.get(f"/bookings/{booking_code}").get_data(as_text=True)

    assert f'href="/matches/{match_id}"' in body
    assert "Kèo liên quan" in body
    assert "Tìm thêm người chơi cuối tuần" in body
    assert "Hiện đang cần thêm 2 người" in body
    assert "Xem và quản lý kèo" in body
    assert body.count("bi-chevron-down") == 3


def test_current_opponent_copy_and_refund_net_amount(app, client, journey):
    login(client, email=journey["creator"].email)
    path = f"/bookings/{journey['booking_code']}"
    body = client.get(path).get_data(as_text=True)
    assert "Kèo liên quan" in body
    assert "Giao hữu cuối tuần" in body
    assert body.count("bi-chevron-down") == 3
    assert "Trạng thái &amp; thanh toán" in body
    assert "Đã thanh toán" in body
    assert "Còn lại trả tại sân" in body
    assert "Bạn sẽ thanh toán phần còn lại trực tiếp tại sân khi đến chơi." in body
    assert "Khoản thanh toán đầu tiên đã thành công" not in body
    assert "còn 70% trả tại sân" not in body and "(85%) trả tại sân" not in body
    with app.app_context():
        booking = db.session.get(Booking, journey["booking_id"])
        opponent_contribution = next(
            contribution for contribution in booking.contributions
            if contribution.contribution_type == "OPPONENT"
        )
        opponent_contribution.amount_paid = opponent_contribution.amount_due
        opponent_contribution.status = "PAID"
        booking.paid_amount = booking.deposit_amount
        booking.status = "PAID"
        db.session.commit()
    db.session.expire_all()
    body = client.get(path).get_data(as_text=True)
    assert "Trạng thái &amp; thanh toán" in body
    assert "Còn lại trả tại sân" in body
    assert "Tổng online" not in body
    with app.app_context():
        booking = db.session.get(Booking, journey["booking_id"])
        booking.status = "REFUND_PENDING"
        db.session.add(Refund(
            booking_id=booking.id, payment_id=journey["creator_payment_id"],
            recipient_id=journey["creator"].id, amount=Decimal("48000"),
            reason="Hoàn phần cọc theo chính sách", order_id="refund-journey",
            request_id="refund-journey-request", status="PROCESSING",
        ))
        db.session.commit()
    db.session.expire_all()
    body = client.get(path).get_data(as_text=True)
    assert "Khoản hoàn đang được xử lý" in body
    assert "Tiền online đang ghi nhận" not in body
    assert "60.000" in body and "48.000" in body
    assert '<details class="booking-disclosure" open>' in body
    assert "Đang xử lý" in body


def test_venue_context_card_map_back_and_direct_access(app, client, journey):
    with app.app_context():
        venue = db.session.get(Venue, journey["venue_id"])
        venue.latitude, venue.longitude = Decimal("10.77"), Decimal("106.70")
        db.session.commit()
    context = dict(q="booking", sport="FOOTBALL", field_type="FOOTBALL_5",
                   min_price="100000", max_price="300000", latitude="10.77",
                   longitude="106.70", sort="nearest", page="1")
    body = client.get("/venues", query_string={
        **context, "next": "https://evil.example", "_external": "true",
    }).get_data(as_text=True)
    links = re.findall(r'href="([^"]*/venues/\d+[^\"]*)"', body)
    assert links
    for link in links:
        parsed = urlsplit(html.unescape(link))
        assert not parsed.netloc
        assert parse_qs(parsed.query) == {k: [v] for k, v in context.items()}
    markers = json.loads(html.unescape(re.search(r"data-venues='([^']+)'", body)[1]))
    assert parse_qs(urlsplit(markers[0]["detail_url"]).query) == {k: [v] for k, v in context.items()}
    detail_path = f"/venues/{journey['venue_id']}"
    full_context = {**context, "province_code": "79", "ward_code": "27475"}
    detail = client.get(detail_path, query_string={
        **full_context, "return_to": "//evil.example", "_scheme": "https",
    }).get_data(as_text=True)
    back = html.unescape(re.search(r'class="venue-back-link" href="([^"]+)"', detail)[1])
    assert urlsplit(back).path == "/venues" and not urlsplit(back).netloc
    assert parse_qs(urlsplit(back).query) == {k: [v] for k, v in full_context.items()}
    assert detail.count('id="venue-fields"') == 1
    assert 'href="#venue-fields"' in detail
    assert detail.index('href="#venue-fields"') < detail.index('id="venue-map-heading"')
    direct = client.get(detail_path).get_data(as_text=True)
    assert 'class="venue-back-link" href="/venues"' in direct
    with client.session_transaction() as session:
        assert "latitude" not in session and "longitude" not in session


@pytest.fixture(autouse=True)
def enable_legacy_momo_in_isolated_tests(app):
    app.config["MOMO_ENABLED"] = True
