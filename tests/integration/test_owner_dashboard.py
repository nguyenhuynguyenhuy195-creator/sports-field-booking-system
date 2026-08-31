from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.models import (
    Booking,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    Field,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import get_owner_dashboard_summary
from app.services.maintenance import VIETNAM_TIMEZONE


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(app, *, email: str, role: UserRole) -> CreatedUser:
    with app.app_context():
        user = User(
            full_name=f"Tài khoản {role.value}",
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


def create_venue_field(
    app,
    *,
    owner_id: int,
    venue_name: str,
    field_name: str,
    venue_status: VenueStatus = VenueStatus.ACTIVE,
    field_status: FieldStatus = FieldStatus.ACTIVE,
) -> tuple[int, int]:
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name=venue_name,
            address="1 Đường Thể Thao",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=venue_status.value,
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
            status=field_status.value,
        )
        db.session.add(field)
        db.session.commit()
        return venue.id, field.id


def create_booking(
    app,
    *,
    code: str,
    user_id: int,
    field_id: int,
    booking_at: datetime,
    status: BookingStatus = BookingStatus.CONFIRMED,
    initial_payment_due_at: datetime | None = None,
    paid_amount: Decimal = Decimal("0.00"),
) -> None:
    with app.app_context():
        db.session.add(
            Booking(
                booking_code=code,
                user_id=user_id,
                field_id=field_id,
                booking_date=booking_at.date(),
                start_time=booking_at.time(),
                end_time=(booking_at + timedelta(hours=1)).time(),
                booking_mode=BookingMode.DIRECT_BOOKING.value,
                payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
                total_amount=Decimal("300000.00"),
                deposit_rate=Decimal("0.3000"),
                deposit_amount=Decimal("90000.00"),
                paid_amount=paid_amount,
                status=status.value,
                initial_payment_due_at=initial_payment_due_at,
            )
        )
        db.session.commit()


def create_maintenance(
    app,
    *,
    owner_id: int,
    field_id: int,
    start_at: datetime,
) -> None:
    with app.app_context():
        db.session.add(
            FieldMaintenance(
                field_id=field_id,
                maintenance_date=start_at.date(),
                start_time=start_at.time(),
                end_time=(start_at + timedelta(hours=1)).time(),
                reason="Bảo trì kiểm thử",
                status=FieldMaintenanceStatus.ACTIVE.value,
                created_by=owner_id,
            )
        )
        db.session.commit()


def local_to_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=VIETNAM_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def test_owner_dashboard_permissions(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    user = create_user(app, email="user@example.com", role=UserRole.USER)
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)

    anonymous_response = client.get("/owner")
    assert anonymous_response.status_code == 302
    assert "/auth/login" in anonymous_response.headers["Location"]

    for account in (user, admin):
        login(client, email=account.email)
        assert client.get("/owner").status_code == 403
        assert client.post("/auth/logout").status_code == 302

    login(client, email=owner.email)
    response = client.get("/owner")
    assert response.status_code == 200
    assert b'data-owner-sidebar' in response.data
    assert b'owner.css' in response.data


def test_dashboard_summary_scopes_owner_and_uses_effective_statuses(app):
    owner_a = create_user(app, email="owner-a@example.com", role=UserRole.OWNER)
    owner_b = create_user(app, email="owner-b@example.com", role=UserRole.OWNER)
    customer = create_user(app, email="customer@example.com", role=UserRole.USER)
    now = datetime(2026, 8, 31, 10, 0)

    _, active_field_id = create_venue_field(
        app,
        owner_id=owner_a.id,
        venue_name="Cơ sở A đang hoạt động",
        field_name="Sân A1",
    )
    create_venue_field(
        app,
        owner_id=owner_a.id,
        venue_name="Cơ sở A chờ duyệt",
        field_name="Sân A2",
        venue_status=VenueStatus.PENDING,
        field_status=FieldStatus.INACTIVE,
    )
    _, owner_b_field_id = create_venue_field(
        app,
        owner_id=owner_b.id,
        venue_name="Cơ sở B",
        field_name="Sân B1",
    )

    create_booking(
        app,
        code="OWN-A-TODAY",
        user_id=customer.id,
        field_id=active_field_id,
        booking_at=now + timedelta(hours=2),
        initial_payment_due_at=local_to_utc(now + timedelta(hours=1)),
    )
    create_booking(
        app,
        code="OWN-A-FUTURE",
        user_id=customer.id,
        field_id=active_field_id,
        booking_at=now + timedelta(days=1),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )
    create_booking(
        app,
        code="OWN-A-EFFECTIVE-EXPIRED",
        user_id=customer.id,
        field_id=active_field_id,
        booking_at=now + timedelta(hours=3),
        initial_payment_due_at=local_to_utc(now - timedelta(minutes=1)),
    )
    create_booking(
        app,
        code="OWN-A-CANCELLED",
        user_id=customer.id,
        field_id=active_field_id,
        booking_at=now + timedelta(hours=4),
        status=BookingStatus.CANCELLED,
    )
    create_booking(
        app,
        code="OWN-B-FUTURE",
        user_id=customer.id,
        field_id=owner_b_field_id,
        booking_at=now + timedelta(hours=2),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )

    create_maintenance(
        app,
        owner_id=owner_a.id,
        field_id=active_field_id,
        start_at=now - timedelta(minutes=30),
    )
    create_maintenance(
        app,
        owner_id=owner_a.id,
        field_id=active_field_id,
        start_at=now + timedelta(hours=3),
    )
    create_maintenance(
        app,
        owner_id=owner_b.id,
        field_id=owner_b_field_id,
        start_at=now + timedelta(hours=2),
    )

    with app.app_context():
        summary = get_owner_dashboard_summary(owner_a.id, now=now)
        upcoming_codes = [
            entry.booking.booking_code for entry in summary.upcoming_bookings
        ]

    assert summary.today_booking_count == 1
    assert summary.upcoming_booking_count == 2
    assert upcoming_codes == ["OWN-A-TODAY", "OWN-A-FUTURE"]
    assert summary.venue_count == 2
    assert summary.active_field_count == 1
    assert summary.pending_venue_count == 1
    assert summary.inactive_field_count == 1
    assert summary.current_maintenance_count == 1
    assert summary.upcoming_maintenance_count == 1


def test_owner_mode_switching_and_final_navigation(app):
    owner = create_user(app, email="nav-owner@example.com", role=UserRole.OWNER)
    client = app.test_client()
    login(client, email=owner.email)

    public_response = client.get("/")
    assert public_response.status_code == 200
    assert b'href="/owner"' in public_response.data
    assert "Quản lý sân" in public_response.get_data(as_text=True)

    owner_response = client.get("/owner")
    owner_html = owner_response.get_data(as_text=True)
    assert 'href="/"' in owner_html
    assert "Trang người chơi" in owner_html
    assert "Tổng quan" in owner_html
    assert "Lịch sân" in owner_html
    assert "Booking" in owner_html
    assert "Cơ sở &amp; Sân" in owner_html
    assert "Bảng giá" in owner_html
    assert "Bảo trì" in owner_html
    assert "Tài chính" in owner_html
    assert "Hồ sơ" not in owner_html
    assert 'data-bs-target="#ownerSidebar"' in owner_html
    assert 'href="/owner" aria-current="page"' in owner_html


def test_existing_owner_pages_render_inside_owner_shell(app):
    owner = create_user(app, email="pages-owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_field(
        app,
        owner_id=owner.id,
        venue_name="Cơ sở Owner Shell",
        field_name="Sân Owner Shell",
    )
    client = app.test_client()
    login(client, email=owner.email)

    urls = (
        "/owner/bookings",
        "/owner/venues",
        f"/owner/venues/{venue_id}/fields",
        f"/owner/venues/{venue_id}/fields/{field_id}/prices",
        f"/owner/venues/{venue_id}/fields/{field_id}/maintenances",
    )
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200
        assert b'data-owner-sidebar' in response.data
        assert b'owner.css' in response.data

    pricing_html = client.get(urls[3]).get_data(as_text=True)
    maintenance_html = client.get(urls[4]).get_data(as_text=True)
    assert "owner-sidebar-link owner-sidebar-link-nested active" in pricing_html
    assert "owner-sidebar-link owner-sidebar-link-nested active" in maintenance_html


def test_shared_booking_detail_selects_owner_or_player_shell(app):
    owner = create_user(app, email="detail-owner@example.com", role=UserRole.OWNER)
    customer = create_user(app, email="detail-user@example.com", role=UserRole.USER)
    _, field_id = create_venue_field(
        app,
        owner_id=owner.id,
        venue_name="Cơ sở booking detail",
        field_name="Sân booking detail",
    )
    create_booking(
        app,
        code="DETAIL-SHELL",
        user_id=customer.id,
        field_id=field_id,
        booking_at=datetime(2030, 1, 15, 18, 0),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )

    client = app.test_client()
    login(client, email=owner.email)
    owner_response = client.get("/owner/bookings/DETAIL-SHELL")
    assert owner_response.status_code == 200
    assert b'data-owner-sidebar' in owner_response.data
    assert b'booking-detail.js' in owner_response.data
    assert client.post("/auth/logout").status_code == 302

    login(client, email=customer.email)
    player_response = client.get("/bookings/DETAIL-SHELL")
    assert player_response.status_code == 200
    assert b'data-owner-sidebar' not in player_response.data
    assert b'app-navbar' in player_response.data
    assert b'booking-detail.js' in player_response.data
