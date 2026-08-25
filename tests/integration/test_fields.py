from dataclasses import dataclass
from datetime import time

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Field,
    FieldStatus,
    FieldTypeCode,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import FieldError, create_field, create_venue, register_user


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
        user = register_user(
            full_name="Nguyễn Văn A",
            email=email,
            phone="0901234567",
            password=PASSWORD,
        )
        user.role = role.value
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 302


def create_venue_for_owner(
    app,
    owner_id: int,
    *,
    name: str = "Sân bóng Minh Anh",
    status: VenueStatus = VenueStatus.PENDING,
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name=name,
            address="123 Nguyễn Hữu Thọ",
            province_code="79",
            ward_code="27475",
            phone="0909876543",
            description=None,
            opening_time=time(6, 0),
            closing_time=time(23, 0),
        )
        venue.status = status.value
        db.session.commit()
        return venue.id


def field_form_data(**overrides):
    data = {
        "name": "  Sân số 1  ",
        "field_type": FieldTypeCode.FOOTBALL_7.value,
        "surface_type": "  Cỏ nhân tạo  ",
        "capacity": "14",
        "venue_id": "999999",
        "status": FieldStatus.ACTIVE.value,
    }
    data.update(overrides)
    return data


def create_field_for_owner(
    app,
    *,
    owner_id: int,
    venue_id: int,
    name: str = "Sân số 1",
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        field = create_field(
            owner=owner,
            venue_id=venue_id,
            name=name,
            field_type=FieldTypeCode.FOOTBALL_7.value,
            surface_type="Cỏ nhân tạo",
            capacity=14,
        )
        return field.id


def test_only_owner_can_open_field_management_pages(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)

    assert client.get(f"/owner/venues/{venue_id}/fields").status_code == 302

    player = create_user(app, email="player@example.com")
    login(client, email=player.email)

    assert client.get(f"/owner/venues/{venue_id}/fields").status_code == 403
    assert client.get(f"/owner/venues/{venue_id}/fields/new").status_code == 403


def test_owner_creates_normalized_inactive_field(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/new",
        data=field_form_data(),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/owner/venues/{venue_id}/fields"
    )
    with app.app_context():
        field = db.session.scalar(db.select(Field))
        assert field is not None
        assert field.venue_id == venue_id
        assert field.name == "Sân số 1"
        assert field.field_type.code == FieldTypeCode.FOOTBALL_7.value
        assert field.surface_type == "Cỏ nhân tạo"
        assert field.capacity == 14
        assert field.status == FieldStatus.INACTIVE.value


def test_invalid_capacity_does_not_create_field(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/new",
        data=field_form_data(capacity="0"),
    )

    assert response.status_code == 200
    assert "Sức chứa phải lớn hơn 0" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Field.id))) == 0


def test_owner_cannot_create_field_for_another_owners_venue(app, client):
    owner_a = create_user(
        app,
        email="owner-a@example.com",
        role=UserRole.OWNER,
    )
    owner_b = create_user(
        app,
        email="owner-b@example.com",
        role=UserRole.OWNER,
    )
    venue_b_id = create_venue_for_owner(app, owner_b.id)
    login(client, email=owner_a.email)

    response = client.post(
        f"/owner/venues/{venue_b_id}/fields/new",
        data=field_form_data(),
    )

    assert response.status_code == 403
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Field.id))) == 0


def test_duplicate_name_is_blocked_only_within_the_same_venue(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    first_venue_id = create_venue_for_owner(app, owner.id, name="Cơ sở A")
    second_venue_id = create_venue_for_owner(app, owner.id, name="Cơ sở B")
    login(client, email=owner.email)

    first_response = client.post(
        f"/owner/venues/{first_venue_id}/fields/new",
        data=field_form_data(),
    )
    duplicate_response = client.post(
        f"/owner/venues/{first_venue_id}/fields/new",
        data=field_form_data(name="sân SỐ 1"),
    )
    other_venue_response = client.post(
        f"/owner/venues/{second_venue_id}/fields/new",
        data=field_form_data(),
    )

    assert first_response.status_code == 302
    assert duplicate_response.status_code == 200
    assert "đã có một sân cùng tên" in duplicate_response.get_data(as_text=True)
    assert other_venue_response.status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Field.id))) == 2


def test_owner_updates_own_field_without_changing_status(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    field_id = create_field_for_owner(
        app,
        owner_id=owner.id,
        venue_id=venue_id,
    )
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/edit",
        data=field_form_data(
            name="Sân trung tâm",
            field_type=FieldTypeCode.FOOTBALL_5.value,
            capacity="10",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        field = db.session.get(Field, field_id)
        assert field.name == "Sân trung tâm"
        assert field.field_type.code == FieldTypeCode.FOOTBALL_5.value
        assert field.capacity == 10
        assert field.status == FieldStatus.INACTIVE.value


def test_owner_cannot_edit_another_owners_field(app, client):
    owner_a = create_user(
        app,
        email="owner-a@example.com",
        role=UserRole.OWNER,
    )
    owner_b = create_user(
        app,
        email="owner-b@example.com",
        role=UserRole.OWNER,
    )
    venue_b_id = create_venue_for_owner(app, owner_b.id)
    field_b_id = create_field_for_owner(
        app,
        owner_id=owner_b.id,
        venue_id=venue_b_id,
    )
    login(client, email=owner_a.email)

    response = client.post(
        f"/owner/venues/{venue_b_id}/fields/{field_b_id}/edit",
        data=field_form_data(name="Tên bị giả mạo"),
    )

    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(Field, field_b_id).name == "Sân số 1"


def test_public_venue_detail_only_lists_active_fields(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner.id,
        status=VenueStatus.ACTIVE,
    )
    field_id = create_field_for_owner(
        app,
        owner_id=owner.id,
        venue_id=venue_id,
        name="Sân chưa có giá",
    )

    inactive_response = client.get(f"/venues/{venue_id}")
    assert inactive_response.status_code == 200
    assert "Sân chưa có giá" not in inactive_response.get_data(as_text=True)

    with app.app_context():
        field = db.session.get(Field, field_id)
        field.status = FieldStatus.ACTIVE.value
        db.session.commit()

    active_response = client.get(f"/venues/{venue_id}")
    assert active_response.status_code == 200
    assert "Sân chưa có giá" in active_response.get_data(as_text=True)
    assert "Sân bóng đá 7 người" in active_response.get_data(as_text=True)


def test_create_field_rolls_back_when_commit_fails(app, monkeypatch):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)

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

        with pytest.raises(FieldError):
            create_field(
                owner=owner_model,
                venue_id=venue_id,
                name="Sân lỗi",
            field_type=FieldTypeCode.FOOTBALL_5.value,
                surface_type=None,
                capacity=10,
            )

        assert rollback_called is True
        assert db.session.scalar(db.select(db.func.count(Field.id))) == 0
