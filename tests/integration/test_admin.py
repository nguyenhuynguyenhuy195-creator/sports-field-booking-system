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
    OwnerApplication,
    OwnerApplicationStatus,
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
from app.routes.admin import (
    BOOKING_STATUS_LABELS,
    PAYMENT_STATUS_LABELS,
    REFUND_STATUS_LABELS,
)
from app.services import register_user


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
    full_name: str | None = None,
    phone: str = "0901234567",
    status: UserStatus = UserStatus.ACTIVE,
) -> CreatedUser:
    with app.app_context():
        user = register_user(
            full_name=full_name or f"Tài khoản {role.value}",
            email=email,
            phone=phone,
            password=PASSWORD,
        )
        user.role = role.value
        user.status = status.value
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

    admin_paths = (
        "/admin",
        "/admin/accounts",
        "/admin/users",
        "/admin/users/999",
        "/admin/owner-applications",
        "/admin/venues",
        "/admin/monitoring",
        "/admin/monitoring/bookings/UNKNOWN",
    )
    for path in admin_paths:
        assert client.get(path).status_code == 403

    client.post("/auth/logout")
    owner = create_user(
        app,
        email="owner-admin-denied@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)
    for path in admin_paths:
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
    assert "/static/css/admin.css" in page
    assert "/static/js/admin-navigation.js" in page
    assert "app-footer" not in page
    assert "/admin/users" in page
    assert "/admin/monitoring" in page


def test_admin_dashboard_uses_database_counts_for_phase_one_kpis(app, client):
    admin = create_user(app, email="kpi-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="kpi-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="kpi-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)

    with app.app_context():
        db.session.add(
            OwnerApplication(
                user_id=player.id,
                business_name="Cơ sở KPI",
                contact_phone="0901234567",
                status=OwnerApplicationStatus.PENDING.value,
            )
        )
        pending_venue = Venue(
            owner_id=owner.id,
            name="Cơ sở chờ KPI",
            address="45 Đường KPI",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(22, 0),
            status=VenueStatus.PENDING.value,
        )
        db.session.add(pending_venue)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking.booking_date = date.today()
        db.session.commit()

    login(client, email=admin.email)
    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Yêu cầu chủ sân đang chờ" in page
    assert "Cơ sở đang chờ duyệt" in page
    assert "Lịch đặt sân hôm nay" in page
    assert "Các vấn đề cần xử lý" in page
    assert "Thanh toán cần kiểm tra" in page
    assert "Hoàn tiền chưa hoàn tất" in page
    assert "PENDING" not in page
    assert "PROCESSING" not in page
    assert "FAILED" not in page

    owner_applications_page = client.get(
        "/admin/owner-applications"
    ).get_data(as_text=True)
    assert "tự động cấp quyền chủ sân" in owner_applications_page
    assert "Role chỉ được đổi qua workflow này" not in owner_applications_page
    assert "Chờ duyệt" in owner_applications_page

    venues_page = client.get("/admin/venues").get_data(as_text=True)
    assert "Kiểm tra đường đi" in venues_page
    assert "Mở chỉ đường trên Google Maps" in venues_page


def test_admin_status_labels_use_vietnamese_business_language():
    assert BOOKING_STATUS_LABELS == {
        BookingStatus.PENDING.value: "Chờ xác nhận",
        BookingStatus.CONFIRMED.value: "Đang giữ chỗ",
        BookingStatus.PARTIALLY_PAID.value: "Đã cọc một phần",
        BookingStatus.PAID.value: "Đã thanh toán cọc",
        BookingStatus.REFUND_PENDING.value: "Đang hoàn tiền",
        BookingStatus.COMPLETED.value: "Đã hoàn thành",
        BookingStatus.REJECTED.value: "Đã từ chối",
        BookingStatus.CANCELLED.value: "Đã hủy",
        BookingStatus.EXPIRED.value: "Đã hết hạn",
    }
    assert PAYMENT_STATUS_LABELS == {
        PaymentStatus.PENDING.value: "Đang chờ xác nhận",
        PaymentStatus.SUCCESS.value: "Thanh toán thành công",
        PaymentStatus.FAILED.value: "Thanh toán thất bại",
        PaymentStatus.CANCELLED.value: "Đã hủy",
        PaymentStatus.EXPIRED.value: "Đã hết hạn",
    }
    assert REFUND_STATUS_LABELS == {
        RefundStatus.PENDING.value: "Chờ xử lý",
        RefundStatus.PROCESSING.value: "Đang xử lý",
        RefundStatus.SUCCESS.value: "Đã hoàn tiền",
        RefundStatus.FAILED.value: "Hoàn tiền thất bại",
    }


def test_admin_sidebar_only_uses_registered_phase_one_endpoints(app, client):
    admin = create_user(app, email="sidebar-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    for expected_href in (
        "/admin",
        "/admin/owner-applications",
        "/admin/venues",
        "/admin/monitoring?section=bookings",
        "/admin/monitoring?section=matches",
        "/admin/users",
        "/auth/logout",
    ):
        assert expected_href in page

    payment_page = client.get(
        "/admin/monitoring?section=bookings&focus=payment_issue"
    ).get_data(as_text=True)
    refund_page = client.get(
        "/admin/monitoring?section=bookings&focus=refund_pending"
    ).get_data(as_text=True)
    match_page = client.get(
        "/admin/monitoring?section=matches"
    ).get_data(as_text=True)
    assert 'title="Thanh toán" aria-current="page"' in payment_page
    assert 'title="Hoàn tiền" aria-current="page"' in refund_page
    assert 'title="Kèo chơi" aria-current="page"' in match_page


def test_admin_can_filter_accounts_without_exposing_password_hash(app, client):
    admin = create_user(app, email="accounts-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="unique-player@example.com")
    login(client, email=admin.email)

    response = client.get("/admin/users?q=unique-player&role=USER&status=ACTIVE")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert target.email in page
    assert admin.email not in page
    assert "data-admin-account-root" in page
    assert "data-admin-account-detail-link" in page
    assert "Chọn nhóm tài khoản" in page
    assert "Người dùng" in page
    assert "Đang hoạt động" in page
    assert "password_hash" not in page
    assert PASSWORD not in page


def test_admin_users_searches_name_email_phone_and_handles_empty_result(
    app, client
):
    admin = create_user(app, email="search-admin@example.com", role=UserRole.ADMIN)
    target = create_user(
        app,
        email="minh.anh@example.com",
        full_name="Nguyễn Minh Anh",
        phone="0987654321",
    )
    unrelated = create_user(app, email="unrelated@example.com")
    login(client, email=admin.email)

    for query in ("Minh Anh", "minh.anh@example.com", "0987654321"):
        response = client.get("/admin/users", query_string={"q": query})
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert target.email in page
        assert unrelated.email not in page

    empty = client.get("/admin/users?q=khong-ton-tai")
    empty_page = empty.get_data(as_text=True)
    assert empty.status_code == 200
    assert "Không tìm thấy tài khoản" in empty_page
    assert "khong-ton-tai" in empty_page


def test_admin_users_filters_each_role_and_existing_status(app, client):
    admin = create_user(app, email="filter-admin@example.com", role=UserRole.ADMIN)
    player = create_user(app, email="filter-player@example.com")
    owner = create_user(
        app,
        email="filter-owner@example.com",
        role=UserRole.OWNER,
        status=UserStatus.LOCKED,
    )
    inactive = create_user(
        app,
        email="filter-inactive@example.com",
        status=UserStatus.INACTIVE,
    )
    login(client, email=admin.email)

    expectations = (
        ({"role": "USER", "status": "ACTIVE"}, player.email),
        ({"role": "OWNER", "status": "LOCKED"}, owner.email),
        ({"role": "ADMIN", "status": "ACTIVE"}, admin.email),
        ({"role": "USER", "status": "INACTIVE"}, inactive.email),
    )
    for filters, expected_email in expectations:
        response = client.get("/admin/users", query_string=filters)
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert expected_email in page


def test_admin_users_paginates_at_database_and_keeps_filters(app, client):
    admin = create_user(
        app,
        email="pagination-admin@example.com",
        role=UserRole.ADMIN,
    )
    users = [
        create_user(
            app,
            email=f"locked-{index:02d}@example.com",
            status=UserStatus.LOCKED,
        )
        for index in range(21)
    ]
    login(client, email=admin.email)

    first_page = client.get(
        "/admin/users?role=USER&status=LOCKED&page=1"
    ).get_data(as_text=True)
    second_page = client.get(
        "/admin/users?role=USER&status=LOCKED&page=2"
    ).get_data(as_text=True)

    assert "Trang 1/2" in first_page
    assert "Trang 2/2" in second_page
    assert users[0].email not in first_page
    assert users[0].email in second_page
    assert "role=USER" in first_page
    assert "status=LOCKED" in first_page


def test_admin_user_detail_shows_profile_and_related_data(app, client):
    admin = create_user(app, email="detail-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-player@example.com")
    seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        db.session.add(
            OwnerApplication(
                user_id=owner.id,
                business_name="Hồ sơ chủ sân gần nhất",
                contact_phone="0901234567",
                status=OwnerApplicationStatus.PENDING.value,
            )
        )
        db.session.commit()
    login(client, email=admin.email)

    owner_response = client.get(f"/admin/users/{owner.id}")
    owner_page = owner_response.get_data(as_text=True)
    assert owner_response.status_code == 200
    assert owner.email in owner_page
    assert "Cập nhật gần nhất" in owner_page
    assert "Hồ sơ chủ sân gần nhất" in owner_page
    assert "Số cơ sở sở hữu" in owner_page
    assert "Chờ duyệt" in owner_page

    player_page = client.get(f"/admin/users/{player.id}").get_data(as_text=True)
    assert player.email in player_page
    assert "Số lịch đã đặt" in player_page
    assert "Dữ liệu liên quan" in player_page


def test_admin_locks_and_unlocks_account_without_deleting_history(app, client):
    admin = create_user(app, email="status-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="status-player@example.com")
    login(client, email=admin.email)

    locked = client.post(
        f"/admin/users/{target.id}/status",
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
        f"/admin/users/{target.id}/status",
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
        f"/admin/users/{admin.id}/status",
        data={"status": UserStatus.LOCKED.value},
        follow_redirects=True,
    )
    assert "không thể tự khóa" in self_lock.get_data(as_text=True)

    invalid = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.INACTIVE.value},
        follow_redirects=True,
    )
    assert "không hợp lệ" in invalid.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(User, admin.id).status == UserStatus.ACTIVE.value
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_admin_cannot_change_another_admin_status(app, client):
    admin = create_user(app, email="actor-admin@example.com", role=UserRole.ADMIN)
    other_admin = create_user(
        app,
        email="readonly-admin@example.com",
        role=UserRole.ADMIN,
    )
    login(client, email=admin.email)

    response = client.post(
        f"/admin/users/{other_admin.id}/status",
        data={"status": UserStatus.LOCKED.value},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "chỉ được xem" in page
    with app.app_context():
        account = db.session.get(User, other_admin.id)
        assert account.status == UserStatus.ACTIVE.value
        assert account.role == UserRole.ADMIN.value


def test_non_admin_cannot_change_account_status(app, client):
    target = create_user(app, email="protected-player@example.com")
    user = create_user(app, email="unauthorized-player@example.com")
    login(client, email=user.email)

    response = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert response.status_code == 403

    client.post("/auth/logout")
    owner = create_user(
        app,
        email="unauthorized-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)
    response = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert response.status_code == 403

    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_get_cannot_change_account_status_and_post_requires_csrf(app, client):
    admin = create_user(app, email="method-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="method-player@example.com")
    login(client, email=admin.email)

    get_response = client.get(f"/admin/users/{target.id}/status")
    assert get_response.status_code == 405
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value

    app.config["WTF_CSRF_ENABLED"] = True
    try:
        csrf_response = client.post(
            f"/admin/users/{target.id}/status",
            data={"status": UserStatus.LOCKED.value},
        )
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
    assert csrf_response.status_code == 400
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_account_status_action_keeps_current_filters_and_role(app, client):
    admin = create_user(app, email="return-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="return-player@example.com")
    login(client, email=admin.email)

    response = client.post(
        f"/admin/users/{target.id}/status",
        data={
            "status": UserStatus.LOCKED.value,
            "q": "return-player",
            "role": UserRole.USER.value,
            "filter_status": UserStatus.ACTIVE.value,
            "page": "1",
            "selected_id": str(target.id),
        },
    )

    assert response.status_code == 302
    assert f"/admin/users/{target.id}" in response.headers["Location"]
    assert "q=return-player" in response.headers["Location"]
    assert "role=USER" in response.headers["Location"]
    assert "status=ACTIVE" in response.headers["Location"]
    with app.app_context():
        account = db.session.get(User, target.id)
        assert account.status == UserStatus.LOCKED.value
        assert account.role == UserRole.USER.value


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
    assert "Lịch đặt sân &amp; dòng tiền" in monitoring_page
    assert "Chọn cơ sở" in monitoring_page
    assert "Cơ sở Admin Test" in monitoring_page
    assert "Sân kiểm thử" in monitoring_page
    assert "Tiến độ tiền cọc" in monitoring_page
    assert "Xem thanh toán và hoàn tiền" in monitoring_page
    assert "PAY-ADMIN-MONITOR" in monitoring_page
    assert "REFUND-ADMIN-MONITOR" in monitoring_page
    assert "Xem hồ sơ đầy đủ" in monitoring_page
    assert "data-admin-workspace-detail-link" in monitoring_page
    assert f"/admin/monitoring/bookings/{booking_code}" in monitoring_page

    detail = client.get(f"/admin/monitoring/bookings/{booking_code}")
    detail_page = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert booking_code in detail_page
    assert "Lịch đặt sân đang ở bước nào?" in detail_page
    assert "Các khoản tiền cọc" in detail_page
    assert "Lịch sử thanh toán" in detail_page
    assert "Cổng thanh toán" in detail_page
    assert "Mã giao dịch" in detail_page
    assert "Mã nhà cung cấp" not in detail_page
    assert "PAY-ADMIN-MONITOR" in detail_page
    assert "Kèo Admin Test" in detail_page
    assert 'data-admin-workspace-return="monitoring"' in detail_page


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
