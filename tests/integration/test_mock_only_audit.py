from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mssql
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Field, FieldPriceSlot, User, UserRole
from app.services import create_booking
from app.services.media import _validate_image, MediaValidationError
from app.services.pricing import _get_owned_field, _validate_price_slot_data, PricingError
from tests.integration.test_bookings import booking_day, create_bookable_field, create_user


def test_disabled_momo_callback_returns_404_without_processing(app, monkeypatch):
    app.config["MOMO_ENABLED"] = False
    client = app.test_client()
    # Before the fix, return creates a disabled client and raises an unhandled error.
    assert client.get("/payments/momo/return").status_code == 404
    assert client.post("/payments/momo/ipn", json={}).status_code == 404


def test_sql_server_pricing_parent_lock_is_emitted(app, monkeypatch):
    with app.app_context():
        captured = []
        monkeypatch.setattr(db.session, "get_bind", lambda: SimpleNamespace(dialect=mssql.dialect()))
        monkeypatch.setattr(db.session, "scalar", lambda statement: captured.append(statement) or SimpleNamespace(venue=SimpleNamespace(owner_id=7)))
        _get_owned_field(field_id=1, owner_id=7, lock=True)
        sql = str(captured[0].compile(dialect=mssql.dialect()))
        assert "WITH (UPDLOCK, HOLDLOCK)" in sql


@pytest.mark.parametrize("price", ["100001.50", "100000.001"])
def test_fractional_hourly_vnd_is_rejected_before_storing(price):
    with pytest.raises(PricingError):
        _validate_price_slot_data(day_of_week=0, start_time=time(8), end_time=time(10), hourly_price=Decimal(price))


def test_odd_hourly_price_90_minutes_can_be_booked(app):
    owner = create_user(app, email="vnd-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="vnd-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        slot = db.session.scalar(db.select(FieldPriceSlot).where(FieldPriceSlot.field_id == field_id))
        slot.hourly_price = Decimal("100001")
        db.session.commit()
        booking = create_booking(user=db.session.get(User, player.id), field_id=field_id, booking_date=booking_day(), start_time=time(18), end_time=time(19,30), booking_mode="DIRECT_BOOKING", note=None)
        assert booking.total_amount == Decimal("150002")
        assert sum(p.subtotal for p in booking.price_details) == booking.total_amount


def test_png_signature_without_decodable_image_is_rejected(app):
    with app.app_context(), pytest.raises(MediaValidationError):
        _validate_image(FileStorage(stream=BytesIO(b"\x89PNG\r\n\x1a\nnot-a-real-image"), filename="fake.png", content_type="image/png"))


def test_sqlite_fixture_enforces_foreign_keys(app):
    with app.app_context():
        assert db.session.execute(db.text("PRAGMA foreign_keys")).scalar() == 1


class UtcHostDatetime(datetime):
    """Model a host interpreting naive datetimes as UTC, independent of Windows TZ."""
    def astimezone(self, tz=None):
        if self.tzinfo is None:
            return self.replace(tzinfo=timezone.utc).astimezone(tz)
        return super().astimezone(tz)


def test_availability_hold_uses_vietnam_time_on_utc_host(app):
    from app.services.availability import build_field_availability, AvailabilitySlotStatus
    owner = create_user(app, email="tz-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="tz-player@example.com")
    now = UtcHostDatetime(2026, 9, 8, 10)
    target = now.date() + timedelta(days=7)
    _, field_id = create_bookable_field(app, owner_id=owner.id, target_date=target)
    with app.app_context():
        booking = create_booking(user=db.session.get(User, player.id), field_id=field_id, booking_date=target, start_time=time(18), end_time=time(19), booking_mode="DIRECT_BOOKING", note=None, now=now)
        assert booking.initial_payment_due_at == datetime(2026, 9, 8, 3, 15)
        availability = build_field_availability(field=db.session.get(Field, field_id), booking_date=target, now=now + timedelta(minutes=5))
        assert next(s.status for s in availability.slots if s.start_time == time(18)) == AvailabilitySlotStatus.BOOKED
        expired = build_field_availability(field=db.session.get(Field, field_id), booking_date=target, now=now + timedelta(minutes=16))
        assert next(s.status for s in expired.slots if s.start_time == time(18)) == AvailabilitySlotStatus.AVAILABLE


@pytest.mark.parametrize("method,path", [
    ("post", "/bookings/absent/contributions/999/payments/momo"),
    ("post", "/bookings/absent/payments/momo/top-up"),
    ("get", "/payments/momo/return"),
    ("post", "/payments/momo/ipn"),
])
def test_disabled_momo_routes_do_not_call_services(app, monkeypatch, method, path):
    import app.routes.payments as routes
    def forbidden(*args, **kwargs):
        pytest.fail("Disabled provider reached a service")
    for name in ("start_momo_payment", "start_momo_top_up", "inspect_momo_return", "process_momo_payment_notification"):
        monkeypatch.setattr(routes, name, forbidden)
    assert getattr(app.test_client(), method)(path).status_code == 404


def test_disabled_momo_services_reject_even_injected_client(app, monkeypatch):
    from app.services.payment import start_momo_payment, start_momo_top_up, inspect_momo_return, process_momo_payment_notification, PaymentError
    from app.services.refund import process_pending_momo_refunds
    with app.app_context():
        def forbidden(*args, **kwargs):
            pytest.fail("Disabled MoMo queried the database")
        monkeypatch.setattr(db.session, "scalar", forbidden)
        monkeypatch.setattr(db.session, "scalars", forbidden)
        for call in (
            lambda: start_momo_payment(booking_code="missing", contribution_id=1, payer=None, redirect_url="", ipn_url="", client=object()),
            lambda: start_momo_top_up(booking_code="missing", payer=None, redirect_url="", ipn_url="", client=object()),
            lambda: inspect_momo_return({}, client=object()),
            lambda: process_momo_payment_notification({}, client=object()),
        ):
            with pytest.raises(PaymentError, match="mô phỏng"):
                call()
        assert process_pending_momo_refunds(client=object()) == 0


def test_mock_checkout_stays_usable_after_disabled_callbacks(app):
    from app.models import Payment, PaymentStatus, ContributionStatus
    from tests.integration.test_bookings import login
    owner = create_user(app, email="mock-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="mock-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        booking = create_booking(user=db.session.get(User, player.id), field_id=field_id, booking_date=booking_day(), start_time=time(18), end_time=time(19), booking_mode="DIRECT_BOOKING", note=None)
        code, contribution_id = booking.booking_code, booking.contributions[0].id
    client = app.test_client()
    login(client, email=player.email)
    page = client.get(f"/bookings/{code}").get_data(as_text=True)
    assert f"/contributions/{contribution_id}/payments/mock" in page
    assert f"/contributions/{contribution_id}/payments/momo" not in page
    assert client.post("/payments/momo/ipn", json={"resultCode":0}).status_code == 404
    for _ in range(2):
        assert client.post(f"/bookings/{code}/contributions/{contribution_id}/payments/mock").status_code == 302
    with app.app_context():
        payments = list(db.session.scalars(db.select(Payment)))
        assert len(payments) == 1
        assert payments[0].provider == "MOCK"
        assert payments[0].status == PaymentStatus.SUCCESS.value
        assert payments[0].contribution.status == ContributionStatus.PAID.value


@pytest.mark.parametrize("format,extension,mime", [("PNG","png","image/png"),("JPEG","jpg","image/jpeg"),("WEBP","webp","image/webp")])
def test_image_decode_accepts_supported_real_images(app, format, extension, mime):
    from PIL import Image
    stream = BytesIO()
    Image.new("RGB", (4, 4), "green").save(stream, format=format)
    data = stream.getvalue()
    with app.app_context():
        result = _validate_image(FileStorage(stream=BytesIO(data), filename=f"valid.{extension}", content_type=mime))
        assert result[1:] == (mime, data)
        app.config["MEDIA_MAX_PIXELS"] = 15
        with pytest.raises(MediaValidationError):
            _validate_image(FileStorage(stream=BytesIO(data), filename=f"large.{extension}", content_type=mime))


def test_fk_rejects_orphan_price_slot(app):
    from sqlalchemy.exc import IntegrityError
    with app.app_context():
        db.session.add(FieldPriceSlot(field_id=999999, day_of_week=0, start_time=time(8), end_time=time(9), hourly_price=100000, status="ACTIVE"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_locked_read_refreshes_previously_cached_field(app):
    from app.services.locking import with_update_lock
    owner = create_user(app, email="lock-owner@example.com", role=UserRole.OWNER)
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        cached = db.session.get(Field, field_id)
        db.session.execute(db.text("UPDATE fields SET name = :name WHERE id = :id"), {"name":"Updated elsewhere", "id":field_id})
        assert cached.name != "Updated elsewhere"
        locked = db.session.scalar(with_update_lock(db.select(Field).where(Field.id == field_id), Field))
        assert locked.name == "Updated elsewhere"
        db.session.rollback()


def test_mvp_config_cannot_enable_momo_from_environment(monkeypatch):
    import subprocess
    import sys
    monkeypatch.setenv("MOMO_ENABLED", "true")
    result = subprocess.run([sys.executable, "-B", "-c", "from app import create_app; app=create_app('development'); assert app.config['MOMO_ENABLED'] is False"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_upload_rejects_request_larger_than_limit(app):
    from tests.integration.test_bookings import login
    owner = create_user(app, email="large-owner@example.com", role=UserRole.OWNER)
    client = app.test_client()
    login(client, email=owner.email)
    app.config["MAX_CONTENT_LENGTH"] = 100
    response = client.post("/owner/venues/999/media", data={"image":(BytesIO(b"x"*101), "large.png")}, content_type="multipart/form-data")
    assert response.status_code == 413
