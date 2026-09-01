from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Booking,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    Field,
    FieldType,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldStatus,
    FieldTypeCode,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import (
    MaintenanceError,
    OverlappingMaintenanceError,
    cancel_maintenance,
    create_maintenance,
    get_effective_maintenance_status,
    maintenance_blocks_time,
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
            full_name="Người kiểm thử",
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


def create_venue_and_field(
    app,
    *,
    owner_id: int,
    field_name: str = "Sân 1",
) -> tuple[int, int]:
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name="Cơ sở kiểm thử",
            address="1 Đường Thể Thao",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name=field_name,
            field_type_id=db.session.scalar(
                db.select(FieldType.id).where(
                    FieldType.code == FieldTypeCode.FOOTBALL_5.value
                )
            ),
            capacity=10,
            status=FieldStatus.INACTIVE.value,
        )
        db.session.add(field)
        db.session.commit()
        return venue.id, field.id


def future_date(days: int = 7) -> date:
    return date.today() + timedelta(days=days)


def maintenance_form_data(**overrides):
    data = {
        "maintenance_date": future_date().isoformat(),
        "start_hour": "18",
        "start_minute": "00",
        "end_hour": "20",
        "end_minute": "00",
        "reason": "Bảo dưỡng mặt sân",
    }
    data.update(overrides)
    return data


def create_maintenance_record(
    app,
    *,
    owner_id: int,
    field_id: int,
    maintenance_date: date | None = None,
    start_time: time = time(18, 0),
    end_time: time = time(20, 0),
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        maintenance = create_maintenance(
            owner=owner,
            field_id=field_id,
            maintenance_date=maintenance_date or future_date(),
            start_time=start_time,
            end_time=end_time,
            reason="Bảo dưỡng mặt sân",
        )
        return maintenance.id


def create_booking_record(
    app,
    *,
    user_id: int,
    field_id: int,
    booking_date: date,
    status: BookingStatus,
    due_at: datetime | None = None,
    paid_amount: Decimal = Decimal("0.00"),
) -> int:
    with app.app_context():
        booking = Booking(
            booking_code=f"BK-MAINT-{status.value}",
            user_id=user_id,
            field_id=field_id,
            booking_date=booking_date,
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
            payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total_amount=Decimal("300000.00"),
            deposit_rate=Decimal("0.3000"),
            deposit_amount=Decimal("90000.00"),
            paid_amount=paid_amount,
            status=status.value,
            initial_payment_due_at=due_at,
        )
        db.session.add(booking)
        db.session.commit()
        return booking.id


def test_only_owner_can_open_maintenance_pages(app, client):
    user = create_user(app, email="user@example.com")
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    url = f"/owner/venues/{venue_id}/fields/{field_id}/maintenances"

    login(client, email=user.email)
    assert client.get(url).status_code == 403

    client.post("/auth/logout")
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)
    assert client.get(url).status_code == 403

    client.post("/auth/logout")
    login(client, email=owner.email)
    response = client.get(url)
    assert response.status_code == 200
    assert "Lịch bảo trì" in response.get_data(as_text=True)


def test_maintenance_empty_state_is_clear(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)

    response = client.get(
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances"
    )

    assert response.status_code == 200
    assert "Sân chưa có lịch bảo trì" in response.get_data(as_text=True)


def test_owner_creates_active_maintenance_and_reason_is_normalized(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances/new",
        data=maintenance_form_data(reason="  Bảo dưỡng   hệ thống đèn  "),
    )

    assert response.status_code == 302
    with app.app_context():
        maintenance = db.session.scalar(db.select(FieldMaintenance))
        assert maintenance is not None
        assert maintenance.status == FieldMaintenanceStatus.ACTIVE.value
        assert maintenance.created_by == owner.id
        assert maintenance.reason == "Bảo dưỡng hệ thống đèn"


def test_invalid_time_interval_is_rejected(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances/new",
        data=maintenance_form_data(start_hour="20", end_hour="19"),
    )

    assert response.status_code == 200
    assert "Giờ kết thúc phải sau giờ bắt đầu" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(FieldMaintenance.id))
        ) == 0


def test_maintenance_must_stay_within_venue_operating_hours(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)
    create_url = (
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances/new"
    )

    response = client.post(
        create_url,
        data=maintenance_form_data(start_hour="05", end_hour="07"),
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Lịch bảo trì phải nằm trong giờ hoạt động" in html
    assert "06:00–23:00" in html
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(FieldMaintenance.id))
        ) == 0


def test_owner_cannot_manage_another_owners_maintenance(app, client):
    owner_a = create_user(app, email="owner-a@example.com", role=UserRole.OWNER)
    owner_b = create_user(app, email="owner-b@example.com", role=UserRole.OWNER)
    venue_b_id, field_b_id = create_venue_and_field(app, owner_id=owner_b.id)
    maintenance_id = create_maintenance_record(
        app,
        owner_id=owner_b.id,
        field_id=field_b_id,
    )
    login(client, email=owner_a.email)
    base_url = (
        f"/owner/venues/{venue_b_id}/fields/{field_b_id}/maintenances"
    )

    assert client.get(base_url).status_code == 403
    assert (
        client.post(f"{base_url}/new", data=maintenance_form_data()).status_code
        == 403
    )
    assert client.post(f"{base_url}/{maintenance_id}/cancel").status_code == 403


def test_mismatched_maintenance_path_ids_return_not_found(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_a_id, field_a_id = create_venue_and_field(
        app,
        owner_id=owner.id,
        field_name="Sân A",
    )
    venue_b_id, field_b_id = create_venue_and_field(
        app,
        owner_id=owner.id,
        field_name="Sân B",
    )
    maintenance_b_id = create_maintenance_record(
        app,
        owner_id=owner.id,
        field_id=field_b_id,
    )
    login(client, email=owner.email)

    assert client.get(
        f"/owner/venues/{venue_a_id}/fields/{field_b_id}/maintenances"
    ).status_code == 404
    assert client.post(
        f"/owner/venues/{venue_b_id}/fields/{field_a_id}"
        f"/maintenances/{maintenance_b_id}/cancel"
    ).status_code == 404


def test_overlap_is_blocked_but_adjacent_or_other_date_is_allowed(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_maintenance_record(app, owner_id=owner.id, field_id=field_id)
    login(client, email=owner.email)
    create_url = (
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances/new"
    )

    overlap_response = client.post(
        create_url,
        data=maintenance_form_data(start_hour="19", end_hour="21"),
    )
    adjacent_response = client.post(
        create_url,
        data=maintenance_form_data(start_hour="20", end_hour="22"),
    )
    other_date_response = client.post(
        create_url,
        data=maintenance_form_data(
            maintenance_date=future_date(8).isoformat(),
        ),
    )

    assert overlap_response.status_code == 200
    assert "bị chồng" in overlap_response.get_data(as_text=True)
    assert adjacent_response.status_code == 302
    assert other_date_response.status_code == 302
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(FieldMaintenance.id))
        ) == 3


def test_cancelled_maintenance_no_longer_blocks_time(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    maintenance_id = create_maintenance_record(
        app,
        owner_id=owner.id,
        field_id=field_id,
    )
    login(client, email=owner.email)
    base_url = f"/owner/venues/{venue_id}/fields/{field_id}/maintenances"

    cancel_response = client.post(f"{base_url}/{maintenance_id}/cancel")
    recreate_response = client.post(
        f"{base_url}/new",
        data=maintenance_form_data(),
    )

    assert cancel_response.status_code == 302
    assert recreate_response.status_code == 302
    with app.app_context():
        statuses = list(
            db.session.scalars(
                db.select(FieldMaintenance.status).order_by(FieldMaintenance.id)
            )
        )
        assert statuses == [
            FieldMaintenanceStatus.CANCELLED.value,
            FieldMaintenanceStatus.ACTIVE.value,
        ]


@pytest.mark.parametrize(
    ("status", "paid_amount"),
    [
        (BookingStatus.CONFIRMED, Decimal("0.00")),
        (BookingStatus.PARTIALLY_PAID, Decimal("45000.00")),
        (BookingStatus.PAID, Decimal("90000.00")),
        (BookingStatus.REFUND_PENDING, Decimal("90000.00")),
    ],
)
def test_occupying_booking_statuses_block_maintenance(
    app,
    status,
    paid_amount,
):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    target_date = date(2026, 9, 10)
    create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        booking_date=target_date,
        status=status,
        due_at=datetime(2026, 9, 1, 4, 0),
        paid_amount=paid_amount,
    )

    with app.app_context(), pytest.raises(MaintenanceError, match="lịch đặt sân"):
        create_maintenance(
            owner=db.session.get(User, owner.id),
            field_id=field_id,
            maintenance_date=target_date,
            start_time=time(19, 0),
            end_time=time(21, 0),
            reason="Bảo trì khẩn cấp",
            now=datetime(2026, 9, 1, 10, 0),
        )


@pytest.mark.parametrize(
    "status",
    [
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.EXPIRED,
    ],
)
def test_non_occupying_booking_statuses_do_not_block_maintenance(app, status):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    target_date = date(2026, 9, 10)
    create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        booking_date=target_date,
        status=status,
    )

    with app.app_context():
        maintenance = create_maintenance(
            owner=db.session.get(User, owner.id),
            field_id=field_id,
            maintenance_date=target_date,
            start_time=time(19, 0),
            end_time=time(21, 0),
            reason="Bảo trì sau khi giải phóng lịch",
            now=datetime(2026, 9, 1, 10, 0),
        )
        assert maintenance.status == FieldMaintenanceStatus.ACTIVE.value


def test_expired_confirmed_hold_does_not_block_maintenance(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="player@example.com")
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    target_date = date(2026, 9, 10)
    create_booking_record(
        app,
        user_id=player.id,
        field_id=field_id,
        booking_date=target_date,
        status=BookingStatus.CONFIRMED,
        due_at=datetime(2026, 9, 1, 2, 0),
    )

    with app.app_context():
        maintenance = create_maintenance(
            owner=db.session.get(User, owner.id),
            field_id=field_id,
            maintenance_date=target_date,
            start_time=time(19, 0),
            end_time=time(21, 0),
            reason="Bảo trì sau khi hold hết hạn",
            now=datetime(2026, 9, 1, 10, 0),
        )
        assert maintenance.id is not None


def test_maintenance_blocks_only_intersecting_active_interval(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    maintenance_id = create_maintenance_record(
        app,
        owner_id=owner.id,
        field_id=field_id,
    )

    with app.app_context():
        assert maintenance_blocks_time(
            field_id=field_id,
            maintenance_date=future_date(),
            start_time=time(19, 0),
            end_time=time(21, 0),
        )
        assert not maintenance_blocks_time(
            field_id=field_id,
            maintenance_date=future_date(),
            start_time=time(20, 0),
            end_time=time(21, 0),
        )
        owner_model = db.session.get(User, owner.id)
        cancel_maintenance(
            maintenance_id=maintenance_id,
            owner=owner_model,
        )
        assert not maintenance_blocks_time(
            field_id=field_id,
            maintenance_date=future_date(),
            start_time=time(19, 0),
            end_time=time(21, 0),
        )


def test_elapsed_active_maintenance_is_displayed_as_completed(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)

    with app.app_context():
        maintenance = FieldMaintenance(
            field_id=field_id,
            maintenance_date=date(2026, 1, 1),
            start_time=time(18, 0),
            end_time=time(20, 0),
            reason="Lịch đã qua",
            status=FieldMaintenanceStatus.ACTIVE.value,
            created_by=owner.id,
        )
        db.session.add(maintenance)
        db.session.commit()

        assert get_effective_maintenance_status(
            maintenance,
            now=datetime(2026, 1, 1, 21, 0),
        ) == FieldMaintenanceStatus.COMPLETED.value


def test_maintenance_list_separates_upcoming_and_history(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_maintenance_record(
        app,
        owner_id=owner.id,
        field_id=field_id,
    )
    with app.app_context():
        db.session.add_all(
            [
                FieldMaintenance(
                    field_id=field_id,
                    maintenance_date=date(2026, 1, 1),
                    start_time=time(8, 0),
                    end_time=time(9, 0),
                    reason="Bảo trì đã hoàn tất",
                    status=FieldMaintenanceStatus.ACTIVE.value,
                    created_by=owner.id,
                ),
                FieldMaintenance(
                    field_id=field_id,
                    maintenance_date=future_date(10),
                    start_time=time(10, 0),
                    end_time=time(11, 0),
                    reason="Bảo trì đã hủy",
                    status=FieldMaintenanceStatus.CANCELLED.value,
                    created_by=owner.id,
                ),
            ]
        )
        db.session.commit()
    login(client, email=owner.email)

    response = client.get(
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances"
    )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Hiện tại &amp; sắp tới" in html
    assert "Lịch sử bảo trì" in html
    assert "Bảo trì đã hoàn tất" in html
    assert "Bảo trì đã hủy" in html
    assert "Đã hoàn thành" in html
    assert "Đã hủy" in html


def test_create_maintenance_rolls_back_when_commit_fails(app, monkeypatch):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)

    with app.app_context():
        owner_model = db.session.get(User, owner.id)
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

        with pytest.raises(MaintenanceError):
            create_maintenance(
                owner=owner_model,
                field_id=field_id,
                maintenance_date=future_date(),
                start_time=time(18, 0),
                end_time=time(20, 0),
                reason="Bảo dưỡng mặt sân",
            )

        assert rollback_called is True
        assert db.session.scalar(
            db.select(db.func.count(FieldMaintenance.id))
        ) == 0


def test_service_rejects_overlapping_active_maintenance(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_maintenance_record(app, owner_id=owner.id, field_id=field_id)

    with app.app_context(), pytest.raises(OverlappingMaintenanceError):
        owner_model = db.session.get(User, owner.id)
        create_maintenance(
            owner=owner_model,
            field_id=field_id,
            maintenance_date=future_date(),
            start_time=time(17, 0),
            end_time=time(19, 0),
            reason="Bảo trì chồng giờ",
        )
