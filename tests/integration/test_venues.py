from dataclasses import dataclass
from datetime import time

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import User, UserRole, Venue, VenueStatus
from app.services import VenueError, create_venue, register_user


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


def venue_form_data(**overrides):
    data = {
        "name": "  Sân bóng Minh Anh  ",
        "address": "  123 Nguyễn Hữu Thọ  ",
        "district": "  Quận 7  ",
        "city": "  TP. Hồ Chí Minh  ",
        "phone": " 0909876543 ",
        "description": "  Có bãi giữ xe và phòng thay đồ.  ",
        "opening_hour": "06",
        "opening_minute": "00",
        "closing_hour": "23",
        "closing_minute": "00",
        "owner_id": "999999",
        "status": VenueStatus.ACTIVE.value,
    }
    data.update(overrides)
    return data


def create_venue_for_owner(app, owner_id: int, **overrides) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        values = {
            "name": "Sân bóng Minh Anh",
            "address": "123 Nguyễn Hữu Thọ",
            "district": "Quận 7",
            "city": "TP. Hồ Chí Minh",
            "phone": "0909876543",
            "description": "Có bãi giữ xe.",
            "opening_time": time(6, 0),
            "closing_time": time(23, 0),
        }
        values.update(overrides)
        venue = create_venue(owner=owner, **values)
        return venue.id


def moderate_form_data(venue_id: int, decision: VenueStatus, note: str = ""):
    prefix = f"venue-{venue_id}"
    return {
        f"{prefix}-decision": decision.value,
        f"{prefix}-moderation_note": note,
    }


def test_only_owner_can_open_owner_venue_pages(app, client):
    assert client.get("/owner/venues").status_code == 302

    player = create_user(app, email="player@example.com")
    login(client, email=player.email)

    assert client.get("/owner/venues").status_code == 403
    assert client.get("/owner/venues/new").status_code == 403


def test_owner_creates_normalized_pending_venue_without_trusting_form_owner(
    app,
    client,
):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    response = client.post("/owner/venues/new", data=venue_form_data())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/owner/venues")
    with app.app_context():
        venue = db.session.scalar(db.select(Venue))
        assert venue is not None
        assert venue.owner_id == owner.id
        assert venue.name == "Sân bóng Minh Anh"
        assert venue.address == "123 Nguyễn Hữu Thọ"
        assert venue.district == "Quận 7"
        assert venue.city == "TP. Hồ Chí Minh"
        assert venue.phone == "0909876543"
        assert venue.description == "Có bãi giữ xe và phòng thay đồ."
        assert venue.opening_time == time(6, 0)
        assert venue.closing_time == time(23, 0)
        assert venue.status == VenueStatus.PENDING.value


def test_invalid_operating_hours_do_not_create_venue(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    response = client.post(
        "/owner/venues/new",
        data=venue_form_data(
            opening_hour="23",
            opening_minute="00",
            closing_hour="06",
            closing_minute="00",
        ),
    )

    assert response.status_code == 200
    assert "Giờ đóng cửa phải sau giờ mở cửa" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0


def test_pending_and_hidden_venues_are_not_public(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    pending_id = create_venue_for_owner(app, owner.id)

    response = client.get("/venues")

    assert response.status_code == 200
    assert "Sân bóng Minh Anh" not in response.get_data(as_text=True)
    assert client.get(f"/venues/{pending_id}").status_code == 404

    with app.app_context():
        venue = db.session.get(Venue, pending_id)
        venue.status = VenueStatus.HIDDEN.value
        db.session.commit()

    assert client.get(f"/venues/{pending_id}").status_code == 404


def test_owner_updates_own_venue_without_changing_moderation_status(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        db.session.commit()
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(name="Sân bóng Minh Anh Mới"),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.name == "Sân bóng Minh Anh Mới"
        assert venue.status == VenueStatus.ACTIVE.value


def test_owner_cannot_edit_another_owners_venue(app, client):
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
    venue_id = create_venue_for_owner(app, owner_b.id)
    login(client, email=owner_a.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(name="Tên bị giả mạo"),
    )

    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(Venue, venue_id).name == "Sân bóng Minh Anh"


def test_admin_activates_venue_with_audit_and_makes_it_public(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=admin.email)

    response = client.post(
        f"/admin/venues/{venue_id}/moderate",
        data=moderate_form_data(
            venue_id,
            VenueStatus.ACTIVE,
            "Đã xác minh thông tin.",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.status == VenueStatus.ACTIVE.value
        assert venue.reviewed_by == admin.id
        assert venue.reviewed_at is not None
        assert venue.moderation_note == "Đã xác minh thông tin."

    client.post("/auth/logout")
    public_response = client.get(f"/venues/{venue_id}")
    assert public_response.status_code == 200
    assert "Sân bóng Minh Anh" in public_response.get_data(as_text=True)


def test_admin_page_lists_pending_venue_and_moderation_form(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    create_venue_for_owner(app, owner.id)
    login(client, email=admin.email)

    response = client.get("/admin/venues")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Sân bóng Minh Anh" in page
    assert "Đang chờ duyệt" in page
    assert "Duyệt và hiển thị" in page


def test_admin_hides_active_venue_from_public_listing(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        db.session.commit()
    login(client, email=admin.email)

    response = client.post(
        f"/admin/venues/{venue_id}/moderate",
        data=moderate_form_data(
            venue_id,
            VenueStatus.HIDDEN,
            "Tạm ẩn để xác minh lại.",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Venue, venue_id).status == VenueStatus.HIDDEN.value
    assert client.get(f"/venues/{venue_id}").status_code == 404


def test_non_admin_cannot_moderate_venue(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/admin/venues/{venue_id}/moderate",
        data=moderate_form_data(venue_id, VenueStatus.ACTIVE),
    )

    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(Venue, venue_id).status == VenueStatus.PENDING.value


def test_create_venue_rolls_back_when_commit_fails(app, monkeypatch):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )

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

        with pytest.raises(VenueError):
            create_venue(
                owner=owner_model,
                name="Sân lỗi",
                address="123 Đường A",
                district=None,
                city="TP. Hồ Chí Minh",
                phone=None,
                description=None,
                opening_time=time(6, 0),
                closing_time=time(22, 0),
            )

        assert rollback_called is True
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0
