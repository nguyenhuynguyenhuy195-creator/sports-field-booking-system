from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import event

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
from app.services import get_owner_schedule_summary
from app.services.maintenance import VIETNAM_TIMEZONE


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class Account:
    id: int
    email: str


def create_account(app, *, email: str, role: UserRole) -> Account:
    with app.app_context():
        user = User(full_name=email.split("@")[0], email=email, role=role.value)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return Account(id=user.id, email=user.email)


def login(client, account: Account) -> None:
    response = client.post(
        "/auth/login",
        data={"email": account.email, "password": PASSWORD},
    )
    assert response.status_code == 302


def create_venue(
    app,
    *,
    owner_id: int,
    name: str,
    opening_time: time = time(6, 0),
    closing_time: time = time(23, 0),
) -> int:
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name=name,
            address="1 Đường Lịch Sân",
            city="TP. Hồ Chí Minh",
            opening_time=opening_time,
            closing_time=closing_time,
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.commit()
        return venue.id


def create_field(
    app,
    *,
    venue_id: int,
    name: str,
    status: FieldStatus = FieldStatus.ACTIVE,
) -> int:
    with app.app_context():
        field = Field(
            venue_id=venue_id,
            name=name,
            field_type_id=db.session.scalar(
                db.select(FieldType.id).where(
                    FieldType.code == FieldTypeCode.FOOTBALL_5.value
                )
            ),
            capacity=10,
            status=status.value,
        )
        db.session.add(field)
        db.session.commit()
        return field.id


def create_booking(
    app,
    *,
    code: str,
    user_id: int,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    status: BookingStatus,
    due_at: datetime | None = None,
    paid_amount: Decimal = Decimal("0.00"),
) -> int:
    with app.app_context():
        booking = Booking(
            booking_code=code,
            user_id=user_id,
            field_id=field_id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
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


def create_maintenance(
    app,
    *,
    owner_id: int,
    field_id: int,
    maintenance_date: date,
    start_time: time,
    end_time: time,
    status: FieldMaintenanceStatus = FieldMaintenanceStatus.ACTIVE,
    reason: str = "Bảo trì phút lẻ",
) -> int:
    with app.app_context():
        maintenance = FieldMaintenance(
            field_id=field_id,
            maintenance_date=maintenance_date,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            status=status.value,
            created_by=owner_id,
        )
        db.session.add(maintenance)
        db.session.commit()
        return maintenance.id


def local_to_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=VIETNAM_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def test_owner_schedule_permissions_and_canonical_venue_redirect(app, client):
    owner = create_account(app, email="schedule-owner@example.com", role=UserRole.OWNER)
    user = create_account(app, email="schedule-user@example.com", role=UserRole.USER)
    admin = create_account(app, email="schedule-admin@example.com", role=UserRole.ADMIN)
    venue_id = create_venue(app, owner_id=owner.id, name="Cơ sở đầu tiên")

    anonymous = client.get("/owner/schedule")
    assert anonymous.status_code == 302
    assert "/auth/login" in anonymous.headers["Location"]

    for account in (user, admin):
        login(client, account)
        assert client.get("/owner/schedule").status_code == 403
        assert client.post("/auth/logout").status_code == 302

    login(client, owner)
    response = client.get("/owner/schedule?date=2026-09-01")
    assert response.status_code == 302
    assert "date=2026-09-01" in response.headers["Location"]
    assert f"venue_id={venue_id}" in response.headers["Location"]
    assert "view=matrix" in response.headers["Location"]

    page = client.get(response.headers["Location"])
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Lịch sân" in html
    assert 'href="/owner/schedule"' in html
    assert 'aria-current="page"' in html


def test_schedule_scopes_owner_and_validates_venue_and_field_context(app):
    owner_a = create_account(app, email="scope-a@example.com", role=UserRole.OWNER)
    owner_b = create_account(app, email="scope-b@example.com", role=UserRole.OWNER)
    venue_a1 = create_venue(app, owner_id=owner_a.id, name="Venue A1")
    venue_a2 = create_venue(app, owner_id=owner_a.id, name="Venue A2")
    venue_b = create_venue(app, owner_id=owner_b.id, name="Venue B riêng tư")
    field_a1 = create_field(app, venue_id=venue_a1, name="Sân A1")
    field_a2 = create_field(app, venue_id=venue_a2, name="Sân A2")
    create_field(app, venue_id=venue_b, name="Sân B riêng tư")

    client = app.test_client()
    login(client, owner_a)
    response = client.get(
        f"/owner/schedule?date=2026-09-01&venue_id={venue_a1}&view=matrix"
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Sân A1" in html
    assert "Venue B riêng tư" not in html
    assert "Sân B riêng tư" not in html

    assert client.get(
        f"/owner/schedule?date=2026-09-01&venue_id={venue_b}"
    ).status_code == 403
    assert client.get(
        f"/owner/schedule?date=2026-09-01&venue_id={venue_a1}&field_id={field_a2}"
    ).status_code == 404
    assert client.get(
        f"/owner/schedule?date=2026-09-01&venue_id={venue_a1}&field_id={field_a1}"
    ).status_code == 200


def test_schedule_effective_statuses_exact_maintenance_and_inactive_field(app):
    owner = create_account(app, email="semantic-owner@example.com", role=UserRole.OWNER)
    customer = create_account(
        app,
        email="semantic-user@example.com",
        role=UserRole.USER,
    )
    target_date = date(2026, 9, 2)
    now = datetime(2026, 9, 2, 8, 0)
    venue_id = create_venue(
        app,
        owner_id=owner.id,
        name="Venue semantic",
        opening_time=time(6, 15),
        closing_time=time(12, 20),
    )
    active_field_id = create_field(app, venue_id=venue_id, name="Sân active")
    inactive_field_id = create_field(
        app,
        venue_id=venue_id,
        name="Sân inactive",
        status=FieldStatus.INACTIVE,
    )

    create_booking(
        app,
        code="SCHEDULE-CONFIRMED",
        user_id=customer.id,
        field_id=active_field_id,
        booking_date=target_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        status=BookingStatus.CONFIRMED,
        due_at=local_to_utc(now + timedelta(minutes=30)),
    )
    stale_id = create_booking(
        app,
        code="SCHEDULE-STALE",
        user_id=customer.id,
        field_id=active_field_id,
        booking_date=target_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status=BookingStatus.CONFIRMED,
        due_at=local_to_utc(now - timedelta(minutes=1)),
    )
    create_booking(
        app,
        code="SCHEDULE-HISTORY",
        user_id=customer.id,
        field_id=active_field_id,
        booking_date=target_date,
        start_time=time(6, 30),
        end_time=time(7, 30),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )
    create_booking(
        app,
        code="SCHEDULE-PENDING",
        user_id=customer.id,
        field_id=active_field_id,
        booking_date=target_date,
        start_time=time(11, 0),
        end_time=time(12, 0),
        status=BookingStatus.PENDING,
    )
    create_maintenance(
        app,
        owner_id=owner.id,
        field_id=inactive_field_id,
        maintenance_date=target_date,
        start_time=time(10, 7),
        end_time=time(10, 43),
    )
    create_maintenance(
        app,
        owner_id=owner.id,
        field_id=active_field_id,
        maintenance_date=target_date,
        start_time=time(6, 5),
        end_time=time(6, 35),
        status=FieldMaintenanceStatus.COMPLETED,
        reason="Bảo trì lịch sử",
    )

    with app.app_context():
        summary = get_owner_schedule_summary(
            owner.id,
            schedule_date=target_date,
            venue_id=venue_id,
            now=now,
        )
        blocks = [block for column in summary.columns for block in column.blocks]
        booking_blocks = {
            block.booking.booking_code: block
            for block in blocks
            if block.booking is not None
        }
        maintenance_blocks = [block for block in blocks if block.maintenance]
        stale_status = db.session.get(Booking, stale_id).status

    assert [field.name for field in summary.fields] == ["Sân active", "Sân inactive"]
    assert summary.grid_start == time(6, 30)
    assert summary.grid_end == time(12, 0)
    assert [guide.label for guide in summary.guides] == [
        "06:30",
        "07:00",
        "07:30",
        "08:00",
        "08:30",
        "09:00",
        "09:30",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "12:00",
    ]
    assert [guide.offset_minutes for guide in summary.guides] == list(
        range(0, 331, 30)
    )
    assert "SCHEDULE-CONFIRMED" in booking_blocks
    assert "SCHEDULE-HISTORY" in booking_blocks
    assert booking_blocks["SCHEDULE-HISTORY"].is_historical is True
    assert "SCHEDULE-STALE" not in booking_blocks
    assert "SCHEDULE-PENDING" not in booking_blocks
    assert stale_status == BookingStatus.CONFIRMED.value

    odd_minute = next(
        block for block in maintenance_blocks if block.start_time == time(10, 7)
    )
    assert odd_minute.offset_minutes == 217
    assert odd_minute.duration_minutes == 36
    clipped = next(
        block for block in maintenance_blocks if block.start_time == time(6, 5)
    )
    assert clipped.is_historical is True
    assert clipped.offset_minutes == 0
    assert clipped.duration_minutes == 5
    assert clipped.start_time == time(6, 5)
    assert clipped.end_time == time(6, 35)


def test_matrix_mobile_field_selection_list_view_and_empty_wording(app):
    owner = create_account(app, email="views-owner@example.com", role=UserRole.OWNER)
    customer = create_account(app, email="views-user@example.com", role=UserRole.USER)
    target_date = date(2026, 9, 3)
    venue_id = create_venue(app, owner_id=owner.id, name="Venue views")
    field_a = create_field(app, venue_id=venue_id, name="Sân Alpha")
    field_b = create_field(app, venue_id=venue_id, name="Sân Beta")
    create_booking(
        app,
        code="VIEW-BOOKING",
        user_id=customer.id,
        field_id=field_b,
        booking_date=target_date,
        start_time=time(18, 0),
        end_time=time(19, 0),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )
    create_maintenance(
        app,
        owner_id=owner.id,
        field_id=field_b,
        maintenance_date=target_date,
        start_time=time(19, 7),
        end_time=time(20, 12),
        reason="Kiểm tra đèn",
    )

    client = app.test_client()
    login(client, owner)
    matrix = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}"
        f"&field_id={field_b}&view=matrix"
    )
    matrix_html = matrix.get_data(as_text=True)
    assert matrix.status_code == 200
    assert "owner-schedule-matrix" in matrix_html
    assert "Sân Beta" in matrix_html
    assert "18:00–19:00" in matrix_html
    assert "19:07–20:12" in matrix_html
    assert f'<option value="{field_b}" selected>' in matrix_html
    assert "/owner/bookings/VIEW-BOOKING" in matrix_html

    unfiltered = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}"
        "&view=matrix"
    )
    unfiltered_html = unfiltered.get_data(as_text=True)
    assert "Sân Alpha" in unfiltered_html
    assert "Sân Beta" in unfiltered_html
    assert (
        f"/owner/schedule?date={target_date.isoformat()}&amp;venue_id={venue_id}"
        "&amp;view=list"
    ) in unfiltered_html

    agenda = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}"
        f"&field_id={field_b}&view=list"
    )
    agenda_html = agenda.get_data(as_text=True)
    assert agenda.status_code == 200
    assert "owner-schedule-agenda" in agenda_html
    assert "VIEW-BOOKING" in agenda_html
    assert "Kiểm tra đèn" in agenda_html

    empty = client.get(
        f"/owner/schedule?date=2026-09-10&venue_id={venue_id}"
        f"&field_id={field_a}&view=list"
    )
    empty_html = empty.get_data(as_text=True)
    assert empty.status_code == 200
    assert "Không có lịch" in empty_html
    assert "Có thể đặt" not in empty_html


def test_matrix_many_fields_uses_internal_width_and_all_or_selected_filter(app):
    owner = create_account(app, email="many-fields-owner@example.com", role=UserRole.OWNER)
    customer = create_account(
        app,
        email="many-fields-user@example.com",
        role=UserRole.USER,
    )
    target_date = date(2026, 9, 5)
    venue_id = create_venue(app, owner_id=owner.id, name="Venue nhiều sân")
    field_ids = [
        create_field(app, venue_id=venue_id, name=f"Sân {index:02d}")
        for index in range(1, 11)
    ]
    create_booking(
        app,
        code="MANY-FIELD-BOOKING",
        user_id=customer.id,
        field_id=field_ids[0],
        booking_date=target_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        status=BookingStatus.PAID,
        paid_amount=Decimal("90000.00"),
    )
    create_maintenance(
        app,
        owner_id=owner.id,
        field_id=field_ids[-1],
        maintenance_date=target_date,
        start_time=time(15, 15),
        end_time=time(16, 0),
        reason="Bảo trì sân thứ mười",
    )

    client = app.test_client()
    login(client, owner)
    all_fields = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}&view=matrix"
    )
    all_html = all_fields.get_data(as_text=True)

    assert all_fields.status_code == 200
    assert 'id="ownerScheduleField"' in all_html
    assert '<option value="" selected>Tất cả sân</option>' in all_html
    assert "--owner-field-count: 10" in all_html
    assert "--owner-matrix-min-width: 2374px" in all_html
    assert all_html.count('class="owner-schedule-timeline"') == 10
    assert "MANY-FIELD-BOOKING" in all_html
    assert "Bảo trì sân thứ mười" in all_html

    blank_filter = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}"
        "&field_id=&view=matrix"
    )
    assert blank_filter.status_code == 200

    selected_field = client.get(
        f"/owner/schedule?date={target_date.isoformat()}&venue_id={venue_id}"
        f"&field_id={field_ids[-1]}&view=matrix"
    )
    selected_html = selected_field.get_data(as_text=True)

    assert selected_field.status_code == 200
    assert f'<option value="{field_ids[-1]}" selected>' in selected_html
    assert "--owner-field-count: 1" in selected_html
    assert "--owner-matrix-min-width: 304px" in selected_html
    assert selected_html.count('class="owner-schedule-timeline"') == 1
    assert "Bảo trì sân thứ mười" in selected_html


def test_matrix_small_field_counts_keep_an_even_width_floor(app):
    owner = create_account(app, email="small-matrix-owner@example.com", role=UserRole.OWNER)
    target_date = date(2026, 9, 6)
    venue_ids = {
        count: create_venue(
            app,
            owner_id=owner.id,
            name=f"Venue {count} sân",
        )
        for count in (1, 2, 3)
    }
    for count, venue_id in venue_ids.items():
        for index in range(1, count + 1):
            create_field(app, venue_id=venue_id, name=f"Sân {count}-{index}")

    client = app.test_client()
    login(client, owner)

    for count, venue_id in venue_ids.items():
        response = client.get(
            f"/owner/schedule?date={target_date.isoformat()}"
            f"&venue_id={venue_id}&view=matrix"
        )
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert f"--owner-field-count: {count}" in html
        assert f"--owner-matrix-min-width: {74 + (count * 230)}px" in html
        assert html.count('class="owner-schedule-timeline"') == count


def test_schedule_uses_four_batched_reads_for_normal_venue_day(app):
    owner = create_account(app, email="batch-owner@example.com", role=UserRole.OWNER)
    venue_id = create_venue(app, owner_id=owner.id, name="Venue batch")
    create_field(app, venue_id=venue_id, name="Sân batch A")
    create_field(app, venue_id=venue_id, name="Sân batch B")

    with app.app_context():
        statements: list[str] = []

        def record_select(_conn, _cursor, statement, *_args):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", record_select)
        try:
            get_owner_schedule_summary(
                owner.id,
                schedule_date=date(2026, 9, 4),
                venue_id=venue_id,
                now=datetime(2026, 9, 4, 8, 0),
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", record_select)

    assert len(statements) == 4


def test_schedule_rejects_invalid_query_parameters(app):
    owner = create_account(app, email="invalid-owner@example.com", role=UserRole.OWNER)
    client = app.test_client()
    login(client, owner)

    assert client.get("/owner/schedule?date=not-a-date").status_code == 400
    assert client.get("/owner/schedule?venue_id=abc").status_code == 400
    assert client.get("/owner/schedule?field_id=0").status_code == 400
    assert client.get("/owner/schedule?view=calendar").status_code == 400


def test_schedule_date_controls_share_vietnam_date_across_year_boundary(
    app,
    monkeypatch,
):
    owner = create_account(app, email="date-owner@example.com", role=UserRole.OWNER)
    venue_id = create_venue(app, owner_id=owner.id, name="Venue date state")
    create_field(app, venue_id=venue_id, name="Sân date state")
    helper_calls = 0

    def vietnam_now_crossing_midnight():
        nonlocal helper_calls
        helper_calls += 1
        if helper_calls == 1:
            return datetime(2026, 1, 1, 0, 0, 1)
        return datetime(2026, 1, 2, 0, 0, 1)

    monkeypatch.setattr(
        "app.routes.owner.current_vietnam_datetime",
        vietnam_now_crossing_midnight,
    )
    client = app.test_client()
    login(client, owner)

    response = client.get(
        f"/owner/schedule?date=2025-12-31&venue_id={venue_id}&view=matrix"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert helper_calls == 1
    assert 'type="date" name="date" value="2025-12-31"' in html
    assert "31/12/2025" in html
    previous_href = (
        f'href="/owner/schedule?date=2025-12-30&amp;venue_id={venue_id}'
        '&amp;view=matrix" aria-label="Ngày trước"'
    )
    today_href = (
        'class="owner-schedule-today" '
        f'href="/owner/schedule?date=2026-01-01&amp;venue_id={venue_id}'
        '&amp;view=matrix"'
    )
    next_href = (
        f'href="/owner/schedule?date=2026-01-01&amp;venue_id={venue_id}'
        '&amp;view=matrix" aria-label="Ngày sau"'
    )
    assert previous_href in html
    assert today_href in html
    assert next_href in html

    helper_calls = 0
    response = client.get("/owner/schedule")
    assert response.status_code == 302
    assert "date=2026-01-01" in response.headers["Location"]
    assert helper_calls == 1
