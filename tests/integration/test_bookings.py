from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Booking,
    BookingPaymentMode,
    BookingPriceDetail,
    BookingStatus,
    Field,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    PriceSlotStatus,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import (
    BookingError,
    BookingPermissionError,
    BookingUnavailableError,
    MaintenanceError,
    cancel_owner_booking,
    cancel_user_booking,
    create_booking,
    create_maintenance,
    current_vietnam_datetime,
    expire_stale_bookings,
)


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(
    app,
    *,
    email: str,
    role: UserRole = UserRole.USER,
) -> CreatedUser:
    with app.app_context():
        user = User(
            full_name="Người kiểm thử booking",
            email=email,
            role=role.value,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 302


def booking_day(days: int = 7) -> date:
    return current_vietnam_datetime().date() + timedelta(days=days)


def create_bookable_field(
    app,
    *,
    owner_id: int,
    target_date: date | None = None,
    venue_status: VenueStatus = VenueStatus.ACTIVE,
    field_status: FieldStatus = FieldStatus.ACTIVE,
    split_prices: bool = False,
) -> tuple[int, int]:
    selected_date = target_date or booking_day()
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name="Cơ sở booking",
            address="123 Đường Thể Thao",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=venue_status.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name="Sân booking",
            field_type=FieldType.FIVE_A_SIDE.value,
            capacity=10,
            status=field_status.value,
        )
        db.session.add(field)
        db.session.flush()
        if split_prices:
            slots = [
                FieldPriceSlot(
                    field_id=field.id,
                    day_of_week=selected_date.weekday(),
                    start_time=time(17, 0),
                    end_time=time(18, 0),
                    hourly_price=Decimal("200000"),
                    status=PriceSlotStatus.ACTIVE.value,
                ),
                FieldPriceSlot(
                    field_id=field.id,
                    day_of_week=selected_date.weekday(),
                    start_time=time(18, 0),
                    end_time=time(21, 0),
                    hourly_price=Decimal("300000"),
                    status=PriceSlotStatus.ACTIVE.value,
                ),
            ]
        else:
            slots = [
                FieldPriceSlot(
                    field_id=field.id,
                    day_of_week=selected_date.weekday(),
                    start_time=time(6, 0),
                    end_time=time(23, 0),
                    hourly_price=Decimal("200000"),
                    status=PriceSlotStatus.ACTIVE.value,
                )
            ]
        db.session.add_all(slots)
        db.session.commit()
        return venue.id, field.id


def booking_form_data(target_date: date, **overrides):
    data = {
        "booking_date": target_date.isoformat(),
        "start_hour": "18",
        "start_minute": "00",
        "end_hour": "20",
        "end_minute": "00",
        "payment_mode": BookingPaymentMode.FULL_PAYMENT.value,
        "note": "Đặt sân giao hữu",
    }
    data.update(overrides)
    return data


def create_booking_record(
    app,
    *,
    user_id: int,
    field_id: int,
    target_date: date | None = None,
    start_time: time = time(18, 0),
    end_time: time = time(20, 0),
    payment_mode: str = BookingPaymentMode.FULL_PAYMENT.value,
    now: datetime | None = None,
) -> str:
    with app.app_context():
        user = db.session.get(User, user_id)
        booking = create_booking(
            user=user,
            field_id=field_id,
            booking_date=target_date or booking_day(),
            start_time=start_time,
            end_time=end_time,
            payment_mode=payment_mode,
            note="Booking kiểm thử",
            now=now,
        )
        return booking.booking_code


def test_user_creates_confirmed_hold_with_price_snapshot(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    venue_id, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
        split_prices=True,
    )
    login(client, email=player.email)

    response = client.post(
        f"/venues/{venue_id}/fields/{field_id}/bookings/new",
        data=booking_form_data(
            target_date,
            start_hour="17",
            start_minute="30",
            end_hour="19",
            end_minute="00",
            note="  Đá   giao hữu  ",
        ),
    )

    assert response.status_code == 302
    assert "/bookings/BK" in response.headers["Location"]
    with app.app_context():
        booking = db.session.scalar(db.select(Booking))
        details = list(
            db.session.scalars(
                db.select(BookingPriceDetail).order_by(
                    BookingPriceDetail.start_time
                )
            )
        )
        assert booking.status == BookingStatus.CONFIRMED.value
        assert booking.total_amount == Decimal("400000.00")
        assert booking.note == "Đá giao hữu"
        assert booking.initial_payment_due_at is not None
        assert len(details) == 2
        assert [detail.subtotal for detail in details] == [
            Decimal("100000.00"),
            Decimal("300000.00"),
        ]


def test_quote_endpoint_returns_backend_price_without_creating_booking(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    venue_id, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
        split_prices=True,
    )
    login(client, email=player.email)

    response = client.post(
        f"/venues/{venue_id}/fields/{field_id}/bookings/quote",
        data=booking_form_data(
            target_date,
            start_hour="17",
            start_minute="30",
            end_hour="19",
            end_minute="00",
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["total"] == "400000.00"
    assert [segment["subtotal"] for segment in payload["segments"]] == [
        "100000.00",
        "300000.00",
    ]
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Booking.id))) == 0


@pytest.mark.parametrize(
    ("start_time", "end_time", "message"),
    [
        (time(18, 10), time(19, 40), "bước 30 phút"),
        (time(18, 0), time(18, 30), "tối thiểu là 60 phút"),
        (time(5, 0), time(6, 0), "giờ hoạt động"),
    ],
)
def test_service_rejects_invalid_booking_time(
    app,
    start_time,
    end_time,
    message,
):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )

    with app.app_context(), pytest.raises(BookingError) as exc_info:
        create_booking(
            user=db.session.get(User, player.id),
            field_id=field_id,
            booking_date=target_date,
            start_time=start_time,
            end_time=end_time,
            payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
        )

    assert message in str(exc_info.value)


def test_payment_mode_lead_times_and_maximum_advance_are_enforced(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    now = datetime(2026, 8, 10, 10, 0)
    target_date = date(2026, 8, 10)
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )

    with app.app_context():
        player_model = db.session.get(User, player.id)
        with pytest.raises(BookingError, match="ít nhất 1 giờ"):
            create_booking(
                user=player_model,
                field_id=field_id,
                booking_date=target_date,
                start_time=time(10, 30),
                end_time=time(11, 30),
                payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
                now=now,
            )
        with pytest.raises(BookingError, match="ít nhất 13 giờ"):
            create_booking(
                user=player_model,
                field_id=field_id,
                booking_date=target_date,
                start_time=time(22, 0),
                end_time=time(23, 0),
                payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
                now=now,
            )
        with pytest.raises(BookingError, match="tối đa 30 ngày"):
            create_booking(
                user=player_model,
                field_id=field_id,
                booking_date=date(2026, 9, 10),
                start_time=time(18, 0),
                end_time=time(20, 0),
                payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
                now=now,
            )


def test_booking_is_blocked_by_maintenance(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    with app.app_context():
        db.session.add(
            FieldMaintenance(
                field_id=field_id,
                maintenance_date=target_date,
                start_time=time(18, 0),
                end_time=time(20, 0),
                reason="Bảo trì mặt sân",
                status=FieldMaintenanceStatus.ACTIVE.value,
                created_by=owner.id,
            )
        )
        db.session.commit()

        with pytest.raises(BookingUnavailableError, match="bảo trì"):
            create_booking(
                user=db.session.get(User, player.id),
                field_id=field_id,
                booking_date=target_date,
                start_time=time(19, 0),
                end_time=time(21, 0),
                payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
            )


def test_overlapping_booking_is_blocked_but_adjacent_is_allowed(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player_a = create_user(app, email="a@example.com")
    player_b = create_user(app, email="b@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    create_booking_record(
        app,
        user_id=player_a.id,
        field_id=field_id,
        target_date=target_date,
    )

    with app.app_context():
        player = db.session.get(User, player_b.id)
        with pytest.raises(BookingUnavailableError, match="đã có người đặt"):
            create_booking(
                user=player,
                field_id=field_id,
                booking_date=target_date,
                start_time=time(19, 0),
                end_time=time(21, 0),
                payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
            )

        adjacent = create_booking(
            user=player,
            field_id=field_id,
            booking_date=target_date,
            start_time=time(20, 0),
            end_time=time(21, 0),
            payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
        )
        assert adjacent.status == BookingStatus.CONFIRMED.value


def test_expired_payment_hold_no_longer_blocks_time(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player_a = create_user(app, email="a@example.com")
    player_b = create_user(app, email="b@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    code = create_booking_record(
        app,
        user_id=player_a.id,
        field_id=field_id,
        target_date=target_date,
    )

    with app.app_context():
        old_booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == code)
        )
        old_booking.initial_payment_due_at = datetime(2020, 1, 1)
        db.session.commit()

        replacement = create_booking(
            user=db.session.get(User, player_b.id),
            field_id=field_id,
            booking_date=target_date,
            start_time=time(18, 0),
            end_time=time(20, 0),
            payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
        )
        assert replacement.status == BookingStatus.CONFIRMED.value
        assert old_booking.status == BookingStatus.EXPIRED.value


def test_expiration_job_is_idempotent(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = date(2026, 8, 20)
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    code = create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        target_date=target_date,
        now=datetime(2026, 8, 19, 10, 0),
    )

    with app.app_context():
        first_count = expire_stale_bookings(now=datetime(2026, 8, 19, 3, 31))
        second_count = expire_stale_bookings(now=datetime(2026, 8, 19, 3, 32))
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == code)
        )

        assert first_count == 1
        assert second_count == 0
        assert booking.status == BookingStatus.EXPIRED.value


def test_owner_can_cancel_auto_confirmed_booking_but_other_owner_cannot(app):
    owner_a = create_user(app, email="owner-a@example.com", role=UserRole.OWNER)
    owner_b = create_user(app, email="owner-b@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner_a.id,
        target_date=target_date,
    )
    code = create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        target_date=target_date,
    )

    with app.app_context():
        with pytest.raises(BookingPermissionError):
            cancel_owner_booking(
                booking_code=code,
                owner=db.session.get(User, owner_b.id),
                reason="Không thuộc sân của owner này",
            )

        booking = cancel_owner_booking(
            booking_code=code,
            owner=db.session.get(User, owner_a.id),
            reason="Sân gặp sự cố đột xuất",
        )
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.cancellation_reason == "Sân gặp sự cố đột xuất"


def test_user_can_cancel_own_booking_before_two_hour_boundary(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = date(2026, 8, 20)
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    code = create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        target_date=target_date,
        now=datetime(2026, 8, 19, 10, 0),
    )

    with app.app_context():
        cancelled = cancel_user_booking(
            booking_code=code,
            user=db.session.get(User, player.id),
            now=datetime(2026, 8, 19, 10, 10),
        )
        assert cancelled.status == BookingStatus.CANCELLED.value


def test_maintenance_cannot_overlap_occupying_booking(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        target_date=target_date,
    )

    with app.app_context(), pytest.raises(MaintenanceError, match="booking"):
        create_maintenance(
            owner=db.session.get(User, owner.id),
            field_id=field_id,
            maintenance_date=target_date,
            start_time=time(19, 0),
            end_time=time(21, 0),
            reason="Bảo trì khẩn cấp",
        )


def test_booking_routes_enforce_auth_and_ownership(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    other = create_user(app, email="other@example.com")
    target_date = booking_day()
    venue_id, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )
    create_url = f"/venues/{venue_id}/fields/{field_id}/bookings/new"

    assert client.get(create_url).status_code == 302
    login(client, email=player.email)
    response = client.post(create_url, data=booking_form_data(target_date))
    assert response.status_code == 302
    with app.app_context():
        code = db.session.scalar(db.select(Booking.booking_code))

    client.post("/auth/logout")
    login(client, email=other.email)
    assert client.get(f"/bookings/{code}").status_code == 403

    client.post("/auth/logout")
    login(client, email=owner.email)
    owner_response = client.get(f"/owner/bookings/{code}")
    assert owner_response.status_code == 200
    assert code in owner_response.get_data(as_text=True)
    assert "Xác nhận booking" not in owner_response.get_data(as_text=True)
    assert client.post(f"/owner/bookings/{code}/confirm").status_code == 404
    assert client.post(f"/owner/bookings/{code}/reject").status_code == 404


def test_create_booking_rolls_back_booking_and_details_on_commit_failure(
    app,
    monkeypatch,
):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    target_date = booking_day()
    _, field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        target_date=target_date,
    )

    with app.app_context():
        original_rollback = db.session.rollback
        rollback_called = False

        def fail_commit():
            raise SQLAlchemyError("simulated commit failure")

        def track_rollback():
            nonlocal rollback_called
            rollback_called = True
            original_rollback()

        monkeypatch.setattr(db.session, "commit", fail_commit)
        monkeypatch.setattr(db.session, "rollback", track_rollback)

        with pytest.raises(BookingError):
            create_booking(
                user=db.session.get(User, player.id),
                field_id=field_id,
                booking_date=target_date,
                start_time=time(18, 0),
                end_time=time(20, 0),
                payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
            )

        assert rollback_called is True
        assert db.session.scalar(db.select(db.func.count(Booking.id))) == 0
        assert db.session.scalar(
            db.select(db.func.count(BookingPriceDetail.id))
        ) == 0
