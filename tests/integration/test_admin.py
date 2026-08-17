from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Field,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchParticipantType,
    MatchStatus,
    MatchType,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
    UserRole,
    UserStatus,
    Venue,
    VenueStatus,
)
from app.models.user import utc_now
from app.services import register_user


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(app, *, email: str, role: UserRole = UserRole.USER) -> CreatedUser:
    with app.app_context():
        user = register_user(
            full_name=f"Tài khoản {role.value}",
            email=email,
            phone="0901234567",
            password=PASSWORD,
        )
        user.role = role.value
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )


def seed_monitoring_data(app, *, user_id: int, owner_id: int) -> str:
    with app.app_context():
        field_type = db.session.scalar(
            db.select(FieldType).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        venue = Venue(
            owner_id=owner_id,
            name="Cơ sở Admin Test",
            address="123 Đường Kiểm Thử",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name="Sân kiểm thử",
            field_type_id=field_type.id,
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.flush()

        booking_code = "BK-ADMIN-MONITOR"
        booking = Booking(
            booking_code=booking_code,
            user_id=user_id,
            field_id=field.id,
            booking_date=date.today() + timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 0),
            booking_mode=BookingMode.FIND_PLAYERS.value,
            play_format=None,
            requested_players=2,
            payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total_amount=Decimal("300000"),
            deposit_rate=Decimal("0.3000"),
            deposit_amount=Decimal("90000"),
            paid_amount=Decimal("90000"),
            cancellation_fee_amount=Decimal("0"),
            status=BookingStatus.PAID.value,
            initial_payment_due_at=utc_now() + timedelta(minutes=15),
        )
        db.session.add(booking)
        db.session.flush()

        contribution = BookingContribution(
            booking_id=booking.id,
            user_id=user_id,
            contribution_type=ContributionType.CREATOR.value,
            amount_due=Decimal("90000"),
            amount_paid=Decimal("90000"),
            status=ContributionStatus.PAID.value,
        )
        db.session.add(contribution)
        db.session.flush()

        payment = Payment(
            booking_id=booking.id,
            contribution_id=contribution.id,
            payer_id=user_id,
            provider=PaymentProvider.MOCK.value,
            payment_method=PaymentMethod.SIMULATED.value,
            amount=Decimal("90000"),
            order_id="PAY-ADMIN-MONITOR",
            request_id="REQ-ADMIN-MONITOR",
            provider_trans_id="TRANS-ADMIN-MONITOR",
            status=PaymentStatus.SUCCESS.value,
            result_code="0",
            paid_at=utc_now(),
        )
        db.session.add(payment)
        db.session.flush()

        refund = Refund(
            booking_id=booking.id,
            payment_id=payment.id,
            recipient_id=user_id,
            amount=Decimal("10000"),
            reason="Hoàn tiền kiểm thử hệ thống",
            order_id="REFUND-ADMIN-MONITOR",
            request_id="REFUND-REQ-ADMIN-MONITOR",
            provider_refund_trans_id="REFUND-TRANS-ADMIN-MONITOR",
            status=RefundStatus.SUCCESS.value,
            result_code="0",
            refunded_at=utc_now(),
        )
        db.session.add(refund)

        match = Match(
            creator_id=user_id,
            booking_id=booking.id,
            match_type=MatchType.FIND_PLAYERS.value,
            title="Kèo Admin Test",
            total_players=10,
            required_players=2,
            status=MatchStatus.OPEN.value,
        )
        db.session.add(match)
        db.session.commit()
        return booking_code


def test_admin_pages_require_admin_role(app, client):
    user = create_user(app, email="player-admin-denied@example.com")
    login(client, email=user.email)

    for path in (
        "/admin",
        "/admin/accounts",
        "/admin/monitoring",
        "/admin/monitoring/bookings/UNKNOWN",
    ):
        assert client.get(path).status_code == 403


def test_admin_dashboard_and_navigation_are_available(app, client):
    admin = create_user(app, email="dashboard-admin@example.com", role=UserRole.ADMIN)
    create_user(app, email="dashboard-player@example.com")
    login(client, email=admin.email)

    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tổng quan vận hành" in page
    assert "Quản lý tài khoản" in page
    assert "Giám sát dữ liệu" not in page
    assert "/admin/accounts" in page
    assert "/admin/monitoring" in page


def test_admin_can_filter_accounts_without_exposing_password_hash(app, client):
    admin = create_user(app, email="accounts-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="unique-player@example.com")
    login(client, email=admin.email)

    response = client.get("/admin/accounts?q=unique-player&role=USER&status=ACTIVE")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert target.email in page
    assert admin.email not in page
    assert "Chọn nhóm tài khoản" in page
    assert "Người chơi" in page
    assert "Đang hoạt động" in page
    assert "password_hash" not in page
    assert PASSWORD not in page


def test_admin_locks_and_unlocks_account_without_deleting_history(app, client):
    admin = create_user(app, email="status-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="status-player@example.com")
    login(client, email=admin.email)

    locked = client.post(
        f"/admin/accounts/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert locked.status_code == 302

    with app.app_context():
        account = db.session.get(User, target.id)
        assert account is not None
        assert account.status == UserStatus.LOCKED.value

    client.post("/auth/logout")
    rejected_login = login(client, email=target.email)
    assert rejected_login.status_code == 200
    assert "hiện không thể đăng nhập" in rejected_login.get_data(as_text=True)

    login(client, email=admin.email)
    unlocked = client.post(
        f"/admin/accounts/{target.id}/status",
        data={"status": UserStatus.ACTIVE.value},
    )
    assert unlocked.status_code == 302
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_admin_cannot_lock_current_account_or_submit_invalid_status(app, client):
    admin = create_user(app, email="self-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="invalid-status-player@example.com")
    login(client, email=admin.email)

    self_lock = client.post(
        f"/admin/accounts/{admin.id}/status",
        data={"status": UserStatus.LOCKED.value},
        follow_redirects=True,
    )
    assert "không thể tự khóa" in self_lock.get_data(as_text=True)

    invalid = client.post(
        f"/admin/accounts/{target.id}/status",
        data={"status": UserStatus.INACTIVE.value},
        follow_redirects=True,
    )
    assert "không hợp lệ" in invalid.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(User, admin.id).status == UserStatus.ACTIVE.value
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_admin_monitoring_lists_all_mvp_records(app, client):
    admin = create_user(app, email="monitor-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="monitor-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="monitor-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    expected = {
        "bookings": booking_code,
        "matches": "Kèo Admin Test",
        "catalog": "Sân bóng đá 5 người",
    }
    for section, marker in expected.items():
        response = client.get(f"/admin/monitoring?section={section}")
        assert response.status_code == 200
        assert marker in response.get_data(as_text=True)


def test_admin_monitoring_explains_data_and_opens_booking_detail(app, client):
    admin = create_user(app, email="monitor-ui-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="monitor-ui-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="monitor-ui-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    monitoring = client.get("/admin/monitoring?section=bookings")
    monitoring_page = monitoring.get_data(as_text=True)

    assert monitoring.status_code == 200
    assert "Tình trạng cần kiểm tra" not in monitoring_page
    assert "Đặt sân &amp; dòng tiền" in monitoring_page
    assert "Chọn cơ sở" in monitoring_page
    assert "Cơ sở Admin Test" in monitoring_page
    assert "Sân kiểm thử" in monitoring_page
    assert "Tiến độ tiền cọc" in monitoring_page
    assert "Xem dòng tiền" in monitoring_page
    assert "PAY-ADMIN-MONITOR" in monitoring_page
    assert "REFUND-ADMIN-MONITOR" in monitoring_page
    assert "Xem hồ sơ đầy đủ" in monitoring_page
    assert f"/admin/monitoring/bookings/{booking_code}" in monitoring_page

    detail = client.get(f"/admin/monitoring/bookings/{booking_code}")
    detail_page = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert booking_code in detail_page
    assert "Lịch đặt sân đang ở bước nào?" in detail_page
    assert "Các khoản tiền cọc" in detail_page
    assert "Lịch sử thanh toán" in detail_page
    assert "PAY-ADMIN-MONITOR" in detail_page
    assert "Kèo Admin Test" in detail_page


def test_admin_booking_detail_redirects_when_booking_does_not_exist(app, client):
    admin = create_user(app, email="missing-booking-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get(
        "/admin/monitoring/bookings/DOES-NOT-EXIST",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Không tìm thấy lịch đặt sân cần theo dõi" in response.get_data(as_text=True)


def test_admin_monitoring_filters_by_venue_and_field_with_friendly_labels(
    app,
    client,
):
    admin = create_user(app, email="location-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="location-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="location-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        venue_id = booking.field.venue_id
        field_id = booking.field_id
    login(client, email=admin.email)

    for section in ("bookings", "matches"):
        response = client.get(
            f"/admin/monitoring?section={section}&venue={venue_id}&field={field_id}"
        )
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Cơ sở Admin Test" in page
        assert "Sân kiểm thử" in page

    payments_page = client.get(
        f"/admin/monitoring?section=bookings&venue={venue_id}&field={field_id}"
    ).get_data(as_text=True)
    assert "Thanh toán thử nghiệm" in payments_page
    assert ">MOCK<" not in payments_page

    invalid_field = client.get(
        f"/admin/monitoring?section=bookings&venue={venue_id}&field=999999",
        follow_redirects=True,
    )
    assert "Không tìm thấy sân đã chọn" in invalid_field.get_data(as_text=True)


def test_admin_monitoring_searches_regions_and_paginates_many_venues(app, client):
    admin = create_user(app, email="many-venues-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="many-venues-owner@example.com", role=UserRole.OWNER)
    with app.app_context():
        venue_ids = []
        field_type = db.session.scalar(
            db.select(FieldType).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        for index in range(1, 51):
            venue = Venue(
                owner_id=owner.id,
                name=f"Cơ sở mở rộng {index:02d}",
                address=f"{index} Đường mở rộng {index:02d}",
                district="Quận 7" if index % 2 == 0 else "Quận 9",
                city="TP. Hồ Chí Minh",
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            )
            db.session.add(venue)
            db.session.flush()
            venue_ids.append(venue.id)
        for index in range(1, 31):
            db.session.add(
                Field(
                    venue_id=venue_ids[-1],
                    name=f"Sân mở rộng {index:02d}",
                    field_type_id=field_type.id,
                    capacity=10,
                    status=FieldStatus.ACTIVE.value,
                )
            )
        db.session.commit()
    login(client, email=admin.email)

    first_page = client.get(
        "/admin/monitoring",
        query_string={"section": "bookings", "venue_q": "Cơ sở mở rộng"},
    ).get_data(as_text=True)
    assert "50 cơ sở phù hợp" in first_page
    assert "Cơ sở mở rộng 01" in first_page
    assert "Cơ sở mở rộng 10" in first_page
    assert "Cơ sở mở rộng 11" not in first_page
    assert "Trang 1/5" in first_page

    second_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue_q": "Cơ sở mở rộng",
            "venue_page": 5,
        },
    ).get_data(as_text=True)
    assert "Cơ sở mở rộng 41" in second_page
    assert "Cơ sở mở rộng 50" in second_page
    assert "Cơ sở mở rộng 01" not in second_page
    assert "Trang 5/5" in second_page

    district_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue_q": "Cơ sở mở rộng",
            "venue_city": "TP. Hồ Chí Minh",
            "venue_district": "Quận 7",
        },
    ).get_data(as_text=True)
    assert "25 cơ sở phù hợp" in district_page
    assert "Cơ sở mở rộng 02" in district_page
    assert "Cơ sở mở rộng 01" not in district_page

    selected_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue": venue_ids[-1],
            "venue_q": "Cơ sở mở rộng",
            "venue_page": 5,
        },
    ).get_data(as_text=True)
    assert "Cơ sở mở rộng 50" in selected_page
    assert "30 sân" in selected_page
    assert "data-admin-field-search" in selected_page
    assert "Xem thêm 22 sân" in selected_page
    assert 'data-field-search-value="Sân mở rộng 30' in selected_page
    assert "hidden data-admin-field-extra" in selected_page


def test_admin_monitoring_validates_filters(app, client):
    admin = create_user(app, email="filter-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    invalid_section = client.get(
        "/admin/monitoring?section=secrets",
        follow_redirects=True,
    )
    assert "không hợp lệ" in invalid_section.get_data(as_text=True)

    invalid_status = client.get(
        "/admin/monitoring?section=bookings&status=UNKNOWN",
        follow_redirects=True,
    )
    assert "Trạng thái lịch đặt sân không hợp lệ" in invalid_status.get_data(
        as_text=True
    )

    invalid_date = client.get(
        "/admin/monitoring?section=bookings&date=not-a-date",
        follow_redirects=True,
    )
    assert "Ngày lọc phải có định dạng hợp lệ" in invalid_date.get_data(
        as_text=True
    )


def test_admin_monitoring_loads_partial_navigation_assets(app, client):
    admin = create_user(app, email="smooth-monitoring-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get("/admin/monitoring?section=bookings")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-admin-monitoring-root" in page
    assert "data-admin-monitoring-status" in page
    assert "/static/js/admin-monitoring.js" in page


def test_admin_monitoring_redirects_legacy_finance_sections(app, client):
    admin = create_user(app, email="legacy-monitor-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    expected_focus = {
        "contributions": "incomplete_deposit",
        "payments": "payment_issue",
        "refunds": "refund_pending",
    }
    for legacy_section, focus in expected_focus.items():
        response = client.get(
            "/admin/monitoring",
            query_string={"section": legacy_section, "venue": 7},
        )
        assert response.status_code == 302
        assert f"section=bookings" in response.location
        assert f"focus={focus}" in response.location
        assert "venue=7" in response.location


def test_admin_monitoring_shows_only_joined_match_recipients(app, client):
    admin = create_user(app, email="match-recipient-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="match-recipient-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="match-recipient-creator@example.com")
    joined_user = create_user(app, email="match-recipient-joined@example.com")
    withdrawn_user = create_user(app, email="match-recipient-withdrawn@example.com")
    booking_code = seed_monitoring_data(app, user_id=creator.id, owner_id=owner.id)

    with app.app_context():
        db.session.get(User, joined_user.id).full_name = "Người đã nhận kèo"
        db.session.get(User, withdrawn_user.id).full_name = "Người đã rút kèo"
        match = db.session.scalar(
            db.select(Match).join(Booking).where(Booking.booking_code == booking_code)
        )
        db.session.add(
            MatchParticipant(
                match_id=match.id,
                user_id=joined_user.id,
                participant_type=MatchParticipantType.PLAYER.value,
                status=MatchParticipantStatus.JOINED.value,
            )
        )
        for _ in range(4):
            db.session.add(
                MatchParticipant(
                    match_id=match.id,
                    user_id=withdrawn_user.id,
                    participant_type=MatchParticipantType.PLAYER.value,
                    status=MatchParticipantStatus.WITHDRAWN.value,
                )
            )
        db.session.commit()

    login(client, email=admin.email)
    response = client.get("/admin/monitoring?section=matches")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Người đã nhận kèo" in page
    assert "Người đã rút kèo" not in page
    assert "1 người" in page
    assert "4 yêu cầu đã kết thúc hoặc rút khỏi kèo" in page
    assert "5 người/yêu cầu" not in page
    assert f"/admin/monitoring/bookings/{booking_code}" in page
