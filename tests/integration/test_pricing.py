from dataclasses import dataclass
from datetime import time
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Field,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    PriceSlotStatus,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import (
    MissingActivePriceSlotError,
    MissingPriceCoverageError,
    OverlappingPriceSlotError,
    PricingError,
    calculate_price_quote,
    create_field,
    create_price_slot,
    create_venue,
    register_user,
    set_field_activation,
    set_price_slot_status,
    update_price_slot,
)


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(app, *, email: str, role: UserRole = UserRole.USER) -> CreatedUser:
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


def create_venue_and_field(
    app,
    *,
    owner_id: int,
    venue_status: VenueStatus = VenueStatus.PENDING,
    field_name: str = "Sân số 1",
) -> tuple[int, int]:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name="Cơ sở Minh Anh",
            address="123 Nguyễn Hữu Thọ",
            district="Quận 7",
            city="TP. Hồ Chí Minh",
            phone="0909876543",
            description=None,
            opening_time=time(6, 0),
            closing_time=time(23, 0),
        )
        venue.status = venue_status.value
        db.session.commit()
        field = create_field(
            owner=owner,
            venue_id=venue.id,
            name=field_name,
            field_type=FieldType.SEVEN_A_SIDE.value,
            surface_type="Cỏ nhân tạo",
            capacity=14,
        )
        return venue.id, field.id


def create_slot(
    app,
    *,
    owner_id: int,
    field_id: int,
    day_of_week: int = 0,
    start_time: time = time(17, 0),
    end_time: time = time(19, 0),
    hourly_price: Decimal = Decimal("200000"),
) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        slot = create_price_slot(
            owner=owner,
            field_id=field_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            hourly_price=hourly_price,
        )
        return slot.id


def price_form_data(**overrides):
    data = {
        "day_of_week": "0",
        "start_hour": "17",
        "start_minute": "00",
        "end_hour": "19",
        "end_minute": "00",
        "hourly_price": "200000",
    }
    data.update(overrides)
    return data


def test_only_owner_can_open_pricing_pages(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)

    pricing_url = f"/owner/venues/{venue_id}/fields/{field_id}/prices"
    assert client.get(pricing_url).status_code == 302

    player = create_user(app, email="player@example.com")
    login(client, email=player.email)
    assert client.get(pricing_url).status_code == 403


def test_owner_creates_active_price_slot_while_field_stays_inactive(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/prices/new",
        data=price_form_data(),
    )

    assert response.status_code == 302
    with app.app_context():
        slot = db.session.scalar(db.select(FieldPriceSlot))
        field = db.session.get(Field, field_id)
        assert slot.day_of_week == 0
        assert slot.start_time == time(17, 0)
        assert slot.end_time == time(19, 0)
        assert slot.hourly_price == Decimal("200000.00")
        assert slot.status == PriceSlotStatus.ACTIVE.value
        assert field.status == FieldStatus.INACTIVE.value


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"start_hour": "19", "end_hour": "18"},
            "Giờ kết thúc phải sau giờ bắt đầu",
        ),
        ({"hourly_price": "0"}, "Giá theo giờ phải lớn hơn 0"),
    ],
)
def test_invalid_price_slot_values_are_rejected(
    app,
    client,
    overrides,
    expected_message,
):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/fields/{field_id}/prices/new",
        data=price_form_data(**overrides),
    )

    assert response.status_code == 200
    assert expected_message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(FieldPriceSlot.id))) == 0


def test_owner_cannot_manage_another_owners_pricing(app, client):
    owner_a = create_user(app, email="owner-a@example.com", role=UserRole.OWNER)
    owner_b = create_user(app, email="owner-b@example.com", role=UserRole.OWNER)
    venue_b_id, field_b_id = create_venue_and_field(app, owner_id=owner_b.id)
    login(client, email=owner_a.email)

    pricing_url = f"/owner/venues/{venue_b_id}/fields/{field_b_id}/prices"
    assert client.get(pricing_url).status_code == 403
    assert (
        client.post(f"{pricing_url}/new", data=price_form_data()).status_code
        == 403
    )


def test_overlap_is_blocked_but_adjacent_or_other_day_is_allowed(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_slot(app, owner_id=owner.id, field_id=field_id)
    login(client, email=owner.email)
    create_url = f"/owner/venues/{venue_id}/fields/{field_id}/prices/new"

    overlap_response = client.post(
        create_url,
        data=price_form_data(start_hour="18", end_hour="21"),
    )
    adjacent_response = client.post(
        create_url,
        data=price_form_data(start_hour="19", end_hour="21"),
    )
    other_day_response = client.post(
        create_url,
        data=price_form_data(day_of_week="1"),
    )

    assert overlap_response.status_code == 200
    assert "bị chồng" in overlap_response.get_data(as_text=True)
    assert adjacent_response.status_code == 302
    assert other_day_response.status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(FieldPriceSlot.id))) == 3


def test_inactive_overlapping_slot_cannot_be_reactivated(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_slot(app, owner_id=owner.id, field_id=field_id)
    second_slot_id = create_slot(
        app,
        owner_id=owner.id,
        field_id=field_id,
        start_time=time(19, 0),
        end_time=time(21, 0),
    )

    with app.app_context():
        owner_model = db.session.get(User, owner.id)
        set_price_slot_status(
            slot_id=second_slot_id,
            owner=owner_model,
            status=PriceSlotStatus.INACTIVE.value,
        )
        update_price_slot(
            slot_id=second_slot_id,
            owner=owner_model,
            day_of_week=0,
            start_time=time(18, 0),
            end_time=time(21, 0),
            hourly_price=Decimal("250000"),
        )
        with pytest.raises(OverlappingPriceSlotError):
            set_price_slot_status(
                slot_id=second_slot_id,
                owner=owner_model,
                status=PriceSlotStatus.ACTIVE.value,
            )


def test_field_requires_active_price_and_stops_with_last_slot(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)

    with app.app_context():
        owner_model = db.session.get(User, owner.id)
        with pytest.raises(MissingActivePriceSlotError):
            set_field_activation(
                field_id=field_id,
                owner=owner_model,
                status=FieldStatus.ACTIVE.value,
            )

    slot_id = create_slot(app, owner_id=owner.id, field_id=field_id)
    with app.app_context():
        owner_model = db.session.get(User, owner.id)
        set_field_activation(
            field_id=field_id,
            owner=owner_model,
            status=FieldStatus.ACTIVE.value,
        )
        assert db.session.get(Field, field_id).status == FieldStatus.ACTIVE.value

        set_price_slot_status(
            slot_id=slot_id,
            owner=owner_model,
            status=PriceSlotStatus.INACTIVE.value,
        )
        assert db.session.get(Field, field_id).status == FieldStatus.INACTIVE.value


def test_public_detail_shows_only_active_field_with_active_prices(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    venue_id, field_id = create_venue_and_field(
        app,
        owner_id=owner.id,
        venue_status=VenueStatus.ACTIVE,
        field_name="Sân công khai",
    )
    create_slot(app, owner_id=owner.id, field_id=field_id)
    with app.app_context():
        owner_model = db.session.get(User, owner.id)
        set_field_activation(
            field_id=field_id,
            owner=owner_model,
            status=FieldStatus.ACTIVE.value,
        )

    response = client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "Sân công khai" in content
    assert "Thứ Hai" in content
    assert "200.000 đ/giờ" in content


def test_price_quote_splits_multiple_slots_and_calculates_total(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_slot(
        app,
        owner_id=owner.id,
        field_id=field_id,
        start_time=time(17, 0),
        end_time=time(18, 0),
        hourly_price=Decimal("200000"),
    )
    create_slot(
        app,
        owner_id=owner.id,
        field_id=field_id,
        start_time=time(18, 0),
        end_time=time(21, 0),
        hourly_price=Decimal("300000"),
    )

    with app.app_context():
        quote = calculate_price_quote(
            field_id=field_id,
            day_of_week=0,
            start_time=time(17, 30),
            end_time=time(19, 0),
        )

        assert len(quote.segments) == 2
        assert quote.segments[0].duration_minutes == 30
        assert quote.segments[0].subtotal == Decimal("100000.00")
        assert quote.segments[1].duration_minutes == 60
        assert quote.segments[1].subtotal == Decimal("300000.00")
        assert quote.total == Decimal("400000.00")


def test_price_quote_reports_missing_coverage(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    _, field_id = create_venue_and_field(app, owner_id=owner.id)
    create_slot(
        app,
        owner_id=owner.id,
        field_id=field_id,
        start_time=time(17, 0),
        end_time=time(18, 0),
    )

    with app.app_context(), pytest.raises(MissingPriceCoverageError) as exc_info:
        calculate_price_quote(
            field_id=field_id,
            day_of_week=0,
            start_time=time(16, 0),
            end_time=time(18, 0),
        )

    assert exc_info.value.start_time == time(16, 0)
    assert exc_info.value.end_time == time(17, 0)


def test_create_price_slot_rolls_back_when_commit_fails(app, monkeypatch):
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

        with pytest.raises(PricingError):
            create_price_slot(
                owner=owner_model,
                field_id=field_id,
                day_of_week=0,
                start_time=time(17, 0),
                end_time=time(19, 0),
                hourly_price=Decimal("200000"),
            )

        assert rollback_called is True
        assert db.session.scalar(db.select(db.func.count(FieldPriceSlot.id))) == 0
