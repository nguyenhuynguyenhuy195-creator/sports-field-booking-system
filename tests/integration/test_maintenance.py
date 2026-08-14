from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
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


def test_only_owner_can_open_maintenance_pages(app, client):
    user = create_user(app, email="user@example.com")
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    url = f"/owner/venues/{venue_id}/fields/{field_id}/maintenances"

    login(client, email=user.email)
    assert client.get(url).status_code == 403

    client.post("/auth/logout")
    login(client, email=owner.email)
    response = client.get(url)
    assert response.status_code == 200
    assert "Lịch bảo trì" in response.get_data(as_text=True)


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
