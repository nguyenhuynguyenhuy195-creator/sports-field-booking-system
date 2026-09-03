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
    Province,
    Refund,
    RefundStatus,
    User,
    UserRole,
    UserStatus,
    Venue,
    VenueStatus,
    Ward,
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


def seed_booking_operations_data(app, *, user_id: int, owner_id: int) -> dict:
    """Create financially consistent records dedicated to the Phase 2.1 list."""
    with app.app_context():
        provinces = tuple(
            db.session.scalars(db.select(Province).order_by(Province.code).limit(2))
        )
        first_ward = db.session.scalar(
            db.select(Ward)
            .where(Ward.province_code == provinces[0].code)
            .order_by(Ward.code)
        )
        second_ward = db.session.scalar(
            db.select(Ward)
            .where(Ward.province_code == provinces[1].code)
            .order_by(Ward.code)
        )
        all_field_types = tuple(
            db.session.scalars(db.select(FieldType).order_by(FieldType.id))
        )
        field_types = (
            all_field_types[0],
            next(
                field_type
                for field_type in all_field_types[1:]
                if field_type.sport_id != all_field_types[0].sport_id
            ),
        )
        venues = (
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops A",
                address="1 Đường Vận Hành",
                province_code=provinces[0].code,
                province_name=provinces[0].name,
                ward_code=first_ward.code,
                ward_name=first_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops B",
                address="2 Đường Vận Hành",
                province_code=provinces[1].code,
                province_name=provinces[1].name,
                ward_code=second_ward.code,
                ward_name=second_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops Legacy",
                address="3 Đường Vận Hành",
                province_name=provinces[0].name,
                ward_name=first_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
        )
        db.session.add_all(venues)
        db.session.flush()
        fields = (
            Field(
                venue_id=venues[0].id,
                name="Sân Booking Ops A",
                field_type_id=field_types[0].id,
                capacity=10,
                status=FieldStatus.ACTIVE.value,
            ),
            Field(
                venue_id=venues[1].id,
                name="Sân Booking Ops B",
                field_type_id=field_types[1].id,
                capacity=4,
                status=FieldStatus.ACTIVE.value,
            ),
            Field(
                venue_id=venues[2].id,
                name="Sân Booking Ops Legacy",
                field_type_id=field_types[0].id,
                capacity=10,
                status=FieldStatus.ACTIVE.value,
            ),
        )
        db.session.add_all(fields)
        db.session.flush()

        scheduled_date = date.today() + timedelta(days=7)

        def add_booking(
            code,
            *,
            field=fields[0],
            mode=BookingMode.DIRECT_BOOKING.value,
            policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total=Decimal("180000"),
            deposit=Decimal("54000"),
            paid=Decimal("0"),
            status=BookingStatus.CONFIRMED.value,
        ):
            booking = Booking(
                booking_code=code,
                user_id=user_id,
                field_id=field.id,
                booking_date=scheduled_date,
                start_time=time(18, 0),
                end_time=time(19, 0),
                booking_mode=mode,
                payment_policy=policy,
                total_amount=total,
                deposit_rate=(
                    Decimal("1.0000")
                    if policy == BookingPaymentPolicy.LEGACY_FULL_ONLINE.value
                    else Decimal("0.3000")
                ),
                deposit_amount=deposit,
                paid_amount=paid,
                cancellation_fee_amount=Decimal("0"),
                status=status,
            )
            db.session.add(booking)
            db.session.flush()
            return booking

        def add_payment(booking, status, suffix, *, amount=None):
            contribution = BookingContribution(
                booking_id=booking.id,
                user_id=user_id,
                contribution_type=ContributionType.CREATOR.value,
                amount_due=booking.deposit_amount,
                amount_paid=booking.paid_amount,
                status=(
                    ContributionStatus.PAID.value
                    if booking.paid_amount >= booking.deposit_amount
                    else ContributionStatus.PENDING.value
                ),
            )
            db.session.add(contribution)
            db.session.flush()
            payment = Payment(
                booking_id=booking.id,
                contribution_id=contribution.id,
                payer_id=user_id,
                provider=PaymentProvider.MOCK.value,
                payment_method=PaymentMethod.SIMULATED.value,
                amount=amount or booking.deposit_amount,
                order_id=f"PAY-OPS-{suffix}",
                request_id=f"REQ-OPS-{suffix}",
                status=status,
                paid_at=utc_now() if status == PaymentStatus.SUCCESS.value else None,
            )
            db.session.add(payment)
            db.session.flush()
            return payment

        main = add_booking(
            "BK-OPS-MAIN",
            paid=Decimal("40000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        main_payment = add_payment(
            main,
            PaymentStatus.SUCCESS.value,
            "SEARCH-TARGET",
            amount=Decimal("54000"),
        )
        db.session.add(
            Refund(
                booking_id=main.id,
                payment_id=main_payment.id,
                recipient_id=user_id,
                amount=Decimal("14000"),
                reason="Hoàn một phần hợp lệ",
                order_id="REFUND-OPS-SEARCH-TARGET",
                request_id="REFUND-REQ-OPS-SEARCH-TARGET",
                status=RefundStatus.SUCCESS.value,
                refunded_at=utc_now(),
            )
        )

        opponent = add_booking(
            "BK-OPS-OPPONENT",
            mode=BookingMode.FIND_OPPONENT.value,
            total=Decimal("300000"),
            deposit=Decimal("90000"),
            paid=Decimal("45000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        add_payment(
            opponent,
            PaymentStatus.SUCCESS.value,
            "OPPONENT",
            amount=Decimal("45000"),
        )

        legacy = add_booking(
            "BK-OPS-LEGACY",
            field=fields[1],
            policy=BookingPaymentPolicy.LEGACY_FULL_ONLINE.value,
            total=Decimal("200000"),
            deposit=Decimal("200000"),
            paid=Decimal("200000"),
            status=BookingStatus.PAID.value,
        )
        add_payment(legacy, PaymentStatus.SUCCESS.value, "LEGACY")

        legacy_location = add_booking("BK-OPS-LEGACY-LOCATION", field=fields[2])

        payment_attention_codes = {}
        for payment_status in (
            PaymentStatus.PENDING.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.CANCELLED.value,
            PaymentStatus.EXPIRED.value,
        ):
            booking = add_booking(f"BK-OPS-PAY-{payment_status}")
            add_payment(booking, payment_status, payment_status)
            payment_attention_codes[payment_status] = booking.booking_code

        refund_attention_codes = {}
        for refund_status in (
            RefundStatus.PENDING.value,
            RefundStatus.PROCESSING.value,
            RefundStatus.FAILED.value,
        ):
            booking = add_booking(
                f"BK-OPS-REF-{refund_status}",
                paid=Decimal("54000"),
                status=BookingStatus.PAID.value,
            )
            payment = add_payment(
                booking,
                PaymentStatus.SUCCESS.value,
                f"REF-{refund_status}",
            )
            db.session.add(
                Refund(
                    booking_id=booking.id,
                    payment_id=payment.id,
                    recipient_id=user_id,
                    amount=Decimal("10000"),
                    reason="Theo dõi hoàn tiền",
                    order_id=f"REFUND-OPS-{refund_status}",
                    request_id=f"REFUND-REQ-OPS-{refund_status}",
                    status=refund_status,
                )
            )
            refund_attention_codes[refund_status] = booking.booking_code

        combined = add_booking(
            "BK-OPS-COMBINED",
            paid=Decimal("54000"),
            status=BookingStatus.REFUND_PENDING.value,
        )
        combined_payment = add_payment(
            combined,
            PaymentStatus.SUCCESS.value,
            "COMBINED-SUCCESS",
        )
        add_payment(combined, PaymentStatus.FAILED.value, "COMBINED-FAILED")
        db.session.add(
            Refund(
                booking_id=combined.id,
                payment_id=combined_payment.id,
                recipient_id=user_id,
                amount=Decimal("10000"),
                reason="Theo dõi kết hợp",
                order_id="REFUND-OPS-COMBINED",
                request_id="REFUND-REQ-OPS-COMBINED",
                status=RefundStatus.PENDING.value,
            )
        )

        db.session.commit()
        return {
            "main": main.booking_code,
            "opponent": opponent.booking_code,
            "legacy": legacy.booking_code,
            "legacy_location": legacy_location.booking_code,
            "scheduled_date": scheduled_date.isoformat(),
            "province_code": provinces[0].code,
            "province_name": provinces[0].name,
            "ward_code": first_ward.code,
            "ward_name": first_ward.full_name,
            "other_province_code": provinces[1].code,
            "venue_id": venues[0].id,
            "field_id": fields[0].id,
            "sport_code": field_types[0].sport.code,
            "other_sport_code": field_types[1].sport.code,
            "other_venue_id": venues[1].id,
            "other_field_id": fields[1].id,
            "customer_email": db.session.get(User, user_id).email,
            "customer_name": db.session.get(User, user_id).full_name,
            "payment_attention_codes": payment_attention_codes,
            "refund_attention_codes": refund_attention_codes,
            "combined": combined.booking_code,
        }


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
        "/admin/bookings",
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
    assert 'href="/admin/bookings" title="Lịch đặt sân"' in page


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
        "/admin/bookings",
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


def test_admin_booking_operations_is_dedicated_compact_read_only_list(app, client):
    admin = create_user(app, email="booking-ops-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-ops-owner@example.com", role=UserRole.OWNER)
    player = create_user(
        app,
        email="booking-ops-player@example.com",
        full_name="Nguyễn Khách Vận Hành",
    )
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    response = client.get("/admin/bookings", query_string={"q": data["opponent"]})
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-admin-bookings-root" in page
    assert "data-admin-booking-filters" in page
    assert data["opponent"] in page
    assert "300.000 đ" in page
    assert "45.000 đ" in page
    assert "255.000 đ" in page
    assert "Online đã ghi nhận" in page
    assert "Tại sân" in page
    assert "Lịch sử thanh toán" not in page
    assert "Lịch sử hoàn tiền" not in page
    assert "PAY-OPS-OPPONENT" not in page
    assert f"/admin/monitoring/bookings/{data['opponent']}" in page
    assert "/static/js/administrative-unit-picker.js" in page
    assert "/static/js/admin-bookings.js" in page
    assert 'href="/admin/bookings">Xóa lọc</a>' in page
    assert "admin-booking-code" in page


def test_admin_booking_operations_searches_all_accepted_sources(app, client):
    admin = create_user(app, email="booking-search-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-search-owner@example.com", role=UserRole.OWNER)
    player = create_user(
        app,
        email="booking-search-player@example.com",
        full_name="Trần Minh Booking Ops",
    )
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    for query in (
        data["main"],
        data["customer_name"],
        data["customer_email"],
        "PAY-OPS-SEARCH-TARGET",
        "REFUND-OPS-SEARCH-TARGET",
    ):
        response = client.get("/admin/bookings", query_string={"q": query})
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        if query in {data["customer_name"], data["customer_email"]}:
            assert data["customer_email"] in page
        else:
            assert data["main"] in page, query
            assert data["opponent"] not in page


def test_admin_booking_operations_filters_status_sport_date_and_location(app, client):
    admin = create_user(app, email="booking-filter-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-filter-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-filter-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    filters = {
        "status": BookingStatus.PARTIALLY_PAID.value,
        "sport": data["sport_code"],
        "date": data["scheduled_date"],
        "province_code": data["province_code"],
        "ward_code": data["ward_code"],
        "venue": data["venue_id"],
        "field": data["field_id"],
    }
    response = client.get("/admin/bookings", query_string=filters)
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert data["main"] in page
    assert data["opponent"] in page
    assert data["legacy"] not in page
    assert f'value="{data["province_code"]}"' in page
    assert data["ward_name"] in page
    assert "Cơ sở Booking Ops A" in page
    assert "Sân Booking Ops A" in page

    status_page = client.get(
        "/admin/bookings",
        query_string={"status": BookingStatus.PAID.value, "q": data["legacy"]},
    ).get_data(as_text=True)
    assert data["legacy"] in status_page
    assert data["main"] not in status_page

    sport_page = client.get(
        "/admin/bookings",
        query_string={"sport": data["other_sport_code"]},
    ).get_data(as_text=True)
    assert data["legacy"] in sport_page
    assert data["main"] not in sport_page

    wrong_date_page = client.get(
        "/admin/bookings",
        query_string={"date": (date.today() + timedelta(days=30)).isoformat()},
    ).get_data(as_text=True)
    assert "Không tìm thấy lịch đặt" in wrong_date_page

    other_location_page = client.get(
        "/admin/bookings",
        query_string={
            "province_code": data["other_province_code"],
            "venue": data["other_venue_id"],
            "field": data["other_field_id"],
        },
    ).get_data(as_text=True)
    assert data["legacy"] in other_location_page
    assert data["main"] not in other_location_page

    legacy_fallback = client.get(
        "/admin/bookings",
        query_string={
            "q": data["legacy_location"],
            "province_code": data["province_code"],
            "ward_code": data["ward_code"],
        },
    ).get_data(as_text=True)
    assert data["legacy_location"] in legacy_fallback

    invalid_ward = client.get(
        "/admin/bookings",
        query_string={"ward_code": data["ward_code"]},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "chọn tỉnh hoặc thành phố trước" in invalid_ward

    invalid_chain = client.get(
        "/admin/bookings",
        query_string={
            "province_code": data["other_province_code"],
            "venue": data["venue_id"],
        },
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Cơ sở không thuộc khu vực đã chọn" in invalid_chain


def test_admin_booking_operations_paginates_six_and_preserves_filters(app, client):
    admin = create_user(app, email="booking-page-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-page-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-page-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    response = client.get(
        "/admin/bookings",
        query_string={
            "q": "BK-OPS",
            "date": data["scheduled_date"],
            "province_code": data["province_code"],
            "page": 1,
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert page.count('class="admin-booking-code"') == 6
    assert "Trang <strong>1</strong> / 2" in page
    assert "q=BK-OPS" in page
    assert f"date={data['scheduled_date']}" in page
    assert f"province_code={data['province_code']}" in page

    second_page = client.get(
        "/admin/bookings",
        query_string={
            "q": "BK-OPS",
            "date": data["scheduled_date"],
            "province_code": data["province_code"],
            "page": 2,
        },
    ).get_data(as_text=True)
    assert "Trang <strong>2</strong> / 2" in second_page


def test_admin_booking_operations_distinguishes_legacy_policy_and_attention(app, client):
    admin = create_user(app, email="booking-attention-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-attention-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-attention-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    legacy = client.get(
        "/admin/bookings", query_string={"q": "PAY-OPS-LEGACY"}
    ).get_data(as_text=True)
    assert "Online toàn phần (lịch sử)" in legacy
    assert "Cọc online theo chính sách" not in legacy

    pending = client.get(
        "/admin/bookings",
        query_string={"q": data["payment_attention_codes"][PaymentStatus.PENDING.value]},
    ).get_data(as_text=True)
    assert "Thanh toán chờ xác nhận" in pending
    assert "Thanh toán cần kiểm tra" not in pending

    for payment_status in (
        PaymentStatus.FAILED.value,
        PaymentStatus.CANCELLED.value,
        PaymentStatus.EXPIRED.value,
    ):
        page = client.get(
            "/admin/bookings",
            query_string={"q": data["payment_attention_codes"][payment_status]},
        ).get_data(as_text=True)
        assert "Thanh toán cần kiểm tra" in page

    for refund_status in (
        RefundStatus.PENDING.value,
        RefundStatus.PROCESSING.value,
        RefundStatus.FAILED.value,
    ):
        page = client.get(
            "/admin/bookings",
            query_string={"q": data["refund_attention_codes"][refund_status]},
        ).get_data(as_text=True)
        assert "Hoàn tiền cần theo dõi" in page

    combined = client.get(
        "/admin/bookings", query_string={"q": data["combined"]}
    ).get_data(as_text=True)
    assert "Thanh toán và hoàn tiền cần theo dõi" in combined

    success_only = client.get(
        "/admin/bookings", query_string={"q": data["main"]}
    ).get_data(as_text=True)
    assert "Hoàn tiền cần theo dõi" not in success_only
    assert "Thanh toán và hoàn tiền cần theo dõi" not in success_only
    assert "Thanh toán cần kiểm tra" not in success_only
    assert "Thanh toán chờ xác nhận" not in success_only


def test_admin_booking_operations_get_does_not_mutate_financial_data(app, client):
    admin = create_user(app, email="booking-read-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-read-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-read-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["main"])
        )
        before = (booking.status, booking.paid_amount)
        payment_count = db.session.scalar(db.select(db.func.count()).select_from(Payment))
        refund_count = db.session.scalar(db.select(db.func.count()).select_from(Refund))
        contribution_count = db.session.scalar(
            db.select(db.func.count()).select_from(BookingContribution)
        )

    login(client, email=admin.email)
    assert client.get("/admin/bookings").status_code == 200

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["main"])
        )
        assert (booking.status, booking.paid_amount) == before
        assert db.session.scalar(db.select(db.func.count()).select_from(Payment)) == payment_count
        assert db.session.scalar(db.select(db.func.count()).select_from(Refund)) == refund_count
        assert (
            db.session.scalar(
                db.select(db.func.count()).select_from(BookingContribution)
            )
            == contribution_count
        )


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
