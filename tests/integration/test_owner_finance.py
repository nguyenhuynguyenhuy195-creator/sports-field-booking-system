from dataclasses import dataclass
from datetime import datetime, time
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
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import get_owner_finance_summary


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class Account:
    id: int
    email: str


def create_user(app, *, email: str, role: UserRole, name: str | None = None) -> Account:
    with app.app_context():
        user = User(
            full_name=name or f"Tài khoản {role.value}",
            email=email,
            role=role.value,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return Account(id=user.id, email=user.email)


def login(client, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 302


def create_venue_field(
    app, *, owner_id: int, venue_name: str, field_name: str
) -> tuple[int, int]:
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name=venue_name,
            address="1 Đường Tài Chính",
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
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.commit()
        return venue.id, field.id


def create_booking(
    app,
    *,
    code: str,
    customer_id: int,
    field_id: int,
    status: BookingStatus,
    total_amount: Decimal = Decimal("1000000.00"),
    deposit_amount: Decimal = Decimal("300000.00"),
    paid_amount: Decimal = Decimal("0.00"),
    payment_policy: BookingPaymentPolicy = BookingPaymentPolicy.DEPOSIT_30,
) -> int:
    with app.app_context():
        booking = Booking(
            booking_code=code,
            user_id=customer_id,
            field_id=field_id,
            booking_date=datetime(2030, 1, 15).date(),
            start_time=time(18, 0),
            end_time=time(19, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
            payment_policy=payment_policy.value,
            total_amount=total_amount,
            deposit_rate=Decimal("0.3000"),
            deposit_amount=deposit_amount,
            paid_amount=paid_amount,
            status=status.value,
        )
        db.session.add(booking)
        db.session.commit()
        return booking.id


def create_payment(
    app,
    *,
    booking_id: int,
    payer_id: int,
    amount: Decimal,
    status: PaymentStatus,
    token: str,
    occurred_at: datetime,
    provider: PaymentProvider = PaymentProvider.MOCK,
) -> int:
    with app.app_context():
        contribution = BookingContribution(
            booking_id=booking_id,
            user_id=payer_id,
            contribution_type=ContributionType.CREATOR.value,
            amount_due=amount,
            amount_paid=amount if status == PaymentStatus.SUCCESS else Decimal("0"),
            status=(
                ContributionStatus.PAID.value
                if status == PaymentStatus.SUCCESS
                else ContributionStatus.PENDING.value
            ),
        )
        db.session.add(contribution)
        db.session.flush()
        payment = Payment(
            booking_id=booking_id,
            contribution_id=contribution.id,
            payer_id=payer_id,
            provider=provider.value,
            payment_method=(
                PaymentMethod.SIMULATED.value
                if provider == PaymentProvider.MOCK
                else PaymentMethod.MOMO_WALLET.value
            ),
            amount=amount,
            order_id=f"ORDER-{token}",
            request_id=f"REQUEST-{token}",
            provider_trans_id=(
                f"TRANS-{token}" if status == PaymentStatus.SUCCESS else None
            ),
            status=status.value,
            result_code="0" if status == PaymentStatus.SUCCESS else "99",
            paid_at=occurred_at if status == PaymentStatus.SUCCESS else None,
            created_at=occurred_at,
        )
        db.session.add(payment)
        db.session.commit()
        return payment.id


def create_refund(
    app,
    *,
    booking_id: int,
    payment_id: int,
    recipient_id: int,
    amount: Decimal,
    status: RefundStatus,
    token: str,
    occurred_at: datetime,
) -> int:
    with app.app_context():
        refund = Refund(
            booking_id=booking_id,
            payment_id=payment_id,
            recipient_id=recipient_id,
            amount=amount,
            reason="Hoàn tiền kiểm thử",
            order_id=f"REFUND-{token}",
            request_id=f"REFUND-REQUEST-{token}",
            provider_refund_trans_id=(
                f"REFUND-TRANS-{token}" if status == RefundStatus.SUCCESS else None
            ),
            status=status.value,
            result_code="0" if status == RefundStatus.SUCCESS else None,
            refunded_at=occurred_at if status == RefundStatus.SUCCESS else None,
            created_at=occurred_at,
        )
        db.session.add(refund)
        db.session.commit()
        return refund.id


def test_owner_finance_permissions_empty_state_and_active_navigation(app, client):
    owner = create_user(app, email="finance-owner@example.com", role=UserRole.OWNER)
    user = create_user(app, email="finance-user@example.com", role=UserRole.USER)
    admin = create_user(app, email="finance-admin@example.com", role=UserRole.ADMIN)

    anonymous = client.get("/owner/finance")
    assert anonymous.status_code == 302
    assert "/auth/login" in anonymous.headers["Location"]

    for account in (user, admin):
        login(client, email=account.email)
        assert client.get("/owner/finance").status_code == 403
        assert client.post("/auth/logout").status_code == 302

    login(client, email=owner.email)
    response = client.get("/owner/finance")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/owner/finance" aria-current="page"' in html
    assert "Chưa có hoạt động phù hợp" in html
    assert "0 đ" in html
    assert "Đối soát &amp; chi trả" in html
    assert "Chưa có dữ liệu đối soát" in html
    assert "Đối soát và chi trả chưa được triển khai" in html
    assert "Tài khoản nhận tiền" not in html
    assert client.post("/owner/finance").status_code == 405
    assert "Đã đối soát" not in html


def test_finance_metrics_use_payment_refund_source_and_do_not_double_count(app):
    owner = create_user(app, email="metric-owner@example.com", role=UserRole.OWNER)
    other_owner = create_user(
        app, email="metric-other@example.com", role=UserRole.OWNER
    )
    customer = create_user(
        app,
        email="metric-customer@example.com",
        role=UserRole.USER,
        name="Khách có tên rất dài để kiểm tra hiển thị tài chính",
    )
    _, field_id = create_venue_field(
        app, owner_id=owner.id, venue_name="Cơ sở Chính", field_name="Sân Một"
    )
    _, other_field_id = create_venue_field(
        app,
        owner_id=other_owner.id,
        venue_name="Cơ sở Không Thuộc Quyền",
        field_name="Sân Khác",
    )
    booking_id = create_booking(
        app,
        code="FINANCE-PAID",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.PAID,
        paid_amount=Decimal("220000.00"),
    )
    paid_one = create_payment(
        app,
        booking_id=booking_id,
        payer_id=customer.id,
        amount=Decimal("200000.00"),
        status=PaymentStatus.SUCCESS,
        token="PAID-ONE",
        occurred_at=datetime(2026, 9, 1, 2, 0),
    )
    paid_two = create_payment(
        app,
        booking_id=booking_id,
        payer_id=customer.id,
        amount=Decimal("100000.00"),
        status=PaymentStatus.SUCCESS,
        token="PAID-TWO",
        occurred_at=datetime(2026, 9, 1, 3, 0),
        provider=PaymentProvider.MOMO,
    )
    for index, payment_status in enumerate(
        (PaymentStatus.FAILED, PaymentStatus.CANCELLED, PaymentStatus.EXPIRED),
        start=1,
    ):
        create_payment(
            app,
            booking_id=booking_id,
            payer_id=customer.id,
            amount=Decimal(index * 10000),
            status=payment_status,
            token=f"EXCLUDED-{payment_status.value}",
            occurred_at=datetime(2026, 9, 1, 4 + index, 0),
        )
    create_refund(
        app,
        booking_id=booking_id,
        payment_id=paid_one,
        recipient_id=customer.id,
        amount=Decimal("80000.00"),
        status=RefundStatus.SUCCESS,
        token="SUCCESS",
        occurred_at=datetime(2026, 9, 1, 9, 0),
    )
    create_refund(
        app,
        booking_id=booking_id,
        payment_id=paid_two,
        recipient_id=customer.id,
        amount=Decimal("40000.00"),
        status=RefundStatus.PENDING,
        token="PENDING",
        occurred_at=datetime(2026, 9, 1, 10, 0),
    )

    cancelled_id = create_booking(
        app,
        code="OWNER-CANCELLED-REFUND",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.CANCELLED,
        total_amount=Decimal("300000.00"),
        deposit_amount=Decimal("90000.00"),
        paid_amount=Decimal("0.00"),
    )
    cancelled_payment = create_payment(
        app,
        booking_id=cancelled_id,
        payer_id=customer.id,
        amount=Decimal("90000.00"),
        status=PaymentStatus.SUCCESS,
        token="OWNER-CANCELLED",
        occurred_at=datetime(2026, 9, 1, 11, 0),
    )
    create_refund(
        app,
        booking_id=cancelled_id,
        payment_id=cancelled_payment,
        recipient_id=customer.id,
        amount=Decimal("90000.00"),
        status=RefundStatus.SUCCESS,
        token="OWNER-CANCELLED",
        occurred_at=datetime(2026, 9, 1, 11, 5),
    )

    completed_id = create_booking(
        app,
        code="COMPLETED-NO-OFFLINE-TRACKING",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.COMPLETED,
        total_amount=Decimal("500000.00"),
        deposit_amount=Decimal("150000.00"),
        paid_amount=Decimal("150000.00"),
    )
    create_payment(
        app,
        booking_id=completed_id,
        payer_id=customer.id,
        amount=Decimal("150000.00"),
        status=PaymentStatus.SUCCESS,
        token="COMPLETED",
        occurred_at=datetime(2026, 9, 1, 11, 10),
    )
    partially_paid_id = create_booking(
        app,
        code="PARTIAL-VALID-BOOKING",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.PARTIALLY_PAID,
        total_amount=Decimal("400000.00"),
        deposit_amount=Decimal("120000.00"),
        paid_amount=Decimal("60000.00"),
    )
    create_payment(
        app,
        booking_id=partially_paid_id,
        payer_id=customer.id,
        amount=Decimal("60000.00"),
        status=PaymentStatus.SUCCESS,
        token="PARTIAL",
        occurred_at=datetime(2026, 9, 1, 11, 15),
    )

    other_booking_id = create_booking(
        app,
        code="OTHER-OWNER-HIDDEN",
        customer_id=customer.id,
        field_id=other_field_id,
        status=BookingStatus.PAID,
        paid_amount=Decimal("300000.00"),
    )
    create_payment(
        app,
        booking_id=other_booking_id,
        payer_id=customer.id,
        amount=Decimal("300000.00"),
        status=PaymentStatus.SUCCESS,
        token="OTHER-OWNER",
        occurred_at=datetime(2026, 9, 1, 12, 0),
    )

    with app.app_context():
        summary = get_owner_finance_summary(owner.id)

    assert summary.booking_value == Decimal("1500000.00")
    assert summary.funded_booking_count == 2
    assert summary.collected_online == Decimal("600000.00")
    assert summary.successful_payment_count == 5
    assert summary.refunded_completed == Decimal("170000.00")
    assert summary.successful_refund_count == 2
    assert summary.recorded_online_balance == Decimal("430000.00")
    assert summary.expected_at_venue == Decimal("1120000.00")
    assert summary.pending_refund_amount == Decimal("40000.00")
    assert summary.pending_refund_count == 1
    assert "OTHER-OWNER-HIDDEN" not in {
        item.booking.booking_code for item in summary.activities
    }

    client = app.test_client()
    login(client, email=owner.email)
    html = client.get("/owner/finance").get_data(as_text=True)
    assert "FINANCE-PAID" in html
    assert "OWNER-CANCELLED-REFUND" in html
    assert "COMPLETED-NO-OFFLINE-TRACKING" in html
    assert "PARTIAL-VALID-BOOKING" in html
    assert "OTHER-OWNER-HIDDEN" not in html
    assert "/owner/bookings/FINANCE-PAID" in html
    assert "/owner/bookings/OWNER-CANCELLED-REFUND" in html
    assert "MoMo Sandbox" in html
    assert "Giá trị booking đã giữ sân" in html
    assert (
        "Tổng giá trị các booking đã hoàn tất bước giữ sân hoặc đã hoàn thành."
        in html
    )
    assert "Tổng thanh toán trực tuyến thành công, trước hoàn tiền." in html
    assert "Tổng số tiền đã hoàn thành công cho người thanh toán." in html
    assert (
        "Phần tiền dự kiến thanh toán trực tiếp tại sân của các booking đang còn hiệu lực."
        in html
    )
    assert (
        "Số tiền trực tuyến còn được hệ thống ghi nhận sau các khoản hoàn thành công."
        in html
    )
    for implementation_detail in (
        "PAID/COMPLETED",
        "Payment SUCCESS",
        "Refund SUCCESS",
        "DEPOSIT_30",
        "Total trừ paid_amount",
    ):
        assert implementation_detail not in html
    assert "Đang chờ xử lý" in html


def test_expected_at_venue_uses_deposit_policy_and_excludes_completed(app):
    owner = create_user(
        app, email="venue-metric-owner@example.com", role=UserRole.OWNER
    )
    customer = create_user(
        app, email="venue-metric-user@example.com", role=UserRole.USER
    )
    _, field_id = create_venue_field(
        app,
        owner_id=owner.id,
        venue_name="Cơ sở metric tại sân",
        field_name="Sân metric",
    )
    create_booking(
        app,
        code="EXPECTED-PARTIAL",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.PARTIALLY_PAID,
        total_amount=Decimal("400000.00"),
        deposit_amount=Decimal("120000.00"),
        paid_amount=Decimal("60000.00"),
    )
    create_booking(
        app,
        code="EXPECTED-PAID",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.PAID,
        total_amount=Decimal("300000.00"),
        deposit_amount=Decimal("90000.00"),
        paid_amount=Decimal("90000.00"),
    )
    create_booking(
        app,
        code="COMPLETED-OFFLINE-UNKNOWN",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.COMPLETED,
        total_amount=Decimal("500000.00"),
        deposit_amount=Decimal("150000.00"),
        paid_amount=Decimal("150000.00"),
    )
    create_booking(
        app,
        code="LEGACY-FULL-ONLINE",
        customer_id=customer.id,
        field_id=field_id,
        status=BookingStatus.PARTIALLY_PAID,
        total_amount=Decimal("400000.00"),
        deposit_amount=Decimal("400000.00"),
        paid_amount=Decimal("200000.00"),
        payment_policy=BookingPaymentPolicy.LEGACY_FULL_ONLINE,
    )

    with app.app_context():
        summary = get_owner_finance_summary(owner.id)

    assert summary.expected_at_venue == Decimal("550000.00")


def test_finance_history_filters_keep_metrics_and_filter_activity(app, client):
    owner = create_user(app, email="filter-owner@example.com", role=UserRole.OWNER)
    customer = create_user(app, email="filter-user@example.com", role=UserRole.USER)
    venue_one, field_one = create_venue_field(
        app, owner_id=owner.id, venue_name="Cơ sở Một", field_name="Sân Một"
    )
    venue_two, field_two = create_venue_field(
        app, owner_id=owner.id, venue_name="Cơ sở Hai", field_name="Sân Hai"
    )
    booking_one = create_booking(
        app,
        code="FILTER-ONE",
        customer_id=customer.id,
        field_id=field_one,
        status=BookingStatus.PAID,
        paid_amount=Decimal("300000.00"),
    )
    booking_two = create_booking(
        app,
        code="FILTER-TWO",
        customer_id=customer.id,
        field_id=field_two,
        status=BookingStatus.PAID,
        paid_amount=Decimal("300000.00"),
    )
    payment_one = create_payment(
        app,
        booking_id=booking_one,
        payer_id=customer.id,
        amount=Decimal("300000.00"),
        status=PaymentStatus.SUCCESS,
        token="FILTER-ONE",
        occurred_at=datetime(2026, 9, 1, 16, 30),
    )
    create_payment(
        app,
        booking_id=booking_two,
        payer_id=customer.id,
        amount=Decimal("300000.00"),
        status=PaymentStatus.SUCCESS,
        token="FILTER-TWO",
        occurred_at=datetime(2026, 9, 1, 17, 30),
    )
    create_refund(
        app,
        booking_id=booking_one,
        payment_id=payment_one,
        recipient_id=customer.id,
        amount=Decimal("50000.00"),
        status=RefundStatus.PENDING,
        token="FILTER-PENDING",
        occurred_at=datetime(2026, 9, 1, 16, 45),
    )

    login(client, email=owner.email)
    response = client.get(
        "/owner/finance",
        query_string={
            "venue_id": venue_one,
            "field_id": field_one,
            "activity_type": "REFUND",
            "status": "PENDING",
            "date_from": "2026-09-01",
            "date_to": "2026-09-01",
        },
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "FILTER-ONE" in html
    assert "FILTER-TWO" not in html
    assert "REFUND-FILTER-PENDING" in html
    assert "ORDER-FILTER-ONE" not in html
    assert "300.000 đ" in html
    assert f'value="{venue_one}" selected' in html
    assert f'value="{field_one}" selected' in html
    assert 'value="REFUND" selected' in html
    assert 'value="PENDING" selected' in html

    next_day = client.get(
        "/owner/finance",
        query_string={"date_from": "2026-09-02", "date_to": "2026-09-02"},
    ).get_data(as_text=True)
    assert "FILTER-ONE" not in next_day
    assert "FILTER-TWO" in next_day
    assert venue_two


def test_foreign_and_mismatched_finance_filters_do_not_leak(app, client):
    owner = create_user(app, email="scope-owner@example.com", role=UserRole.OWNER)
    other = create_user(app, email="scope-other@example.com", role=UserRole.OWNER)
    own_venue_one, own_field_one = create_venue_field(
        app, owner_id=owner.id, venue_name="Own One", field_name="Own Field One"
    )
    own_venue_two, _ = create_venue_field(
        app, owner_id=owner.id, venue_name="Own Two", field_name="Own Field Two"
    )
    foreign_venue, foreign_field = create_venue_field(
        app, owner_id=other.id, venue_name="Foreign", field_name="Foreign Field"
    )
    login(client, email=owner.email)

    assert client.get(f"/owner/finance?venue_id={foreign_venue}").status_code == 403
    assert client.get(f"/owner/finance?field_id={foreign_field}").status_code == 403
    assert (
        client.get(
            f"/owner/finance?venue_id={own_venue_two}&field_id={own_field_one}"
        ).status_code
        == 404
    )
    assert client.get("/owner/finance?venue_id=999999").status_code == 404
    assert client.get("/owner/finance?field_id=999999").status_code == 404
    assert client.get("/owner/finance?activity_type=LEDGER").status_code == 400
    assert client.get("/owner/finance?date_from=2026-09-03&date_to=2026-09-01").status_code == 400
    assert own_venue_one
