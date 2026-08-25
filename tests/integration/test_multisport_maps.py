from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    Field,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    PriceSlotStatus,
    Sport,
    SportCode,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services import (
    ImmutableFieldTypeError,
    InvalidVenueStateError,
    VenueError,
    create_field,
    create_venue,
    moderate_venue,
    register_user,
    search_public_venues,
    update_field,
)


PASSWORD = "MatKhauAnToan123"


def create_user(app, *, email: str, role: UserRole) -> int:
    with app.app_context():
        user = register_user(
            full_name="Nguyễn Văn A",
            email=email,
            phone="0901234567",
            password=PASSWORD,
        )
        user.role = role.value
        db.session.commit()
        return user.id


def create_public_venue_with_field(
    app,
    *,
    owner_id: int,
    name: str,
    latitude: Decimal | None,
    longitude: Decimal | None,
    field_type_code: str,
) -> int:
    with app.app_context():
        field_type_id = db.session.scalar(
            db.select(FieldType.id).where(FieldType.code == field_type_code)
        )
        venue = Venue(
            owner_id=owner_id,
            name=name,
            address="1 Đường Thể Thao",
            city="TP. Hồ Chí Minh",
            google_place_id=f"place-{name}" if latitude is not None else None,
            latitude=latitude,
            longitude=longitude,
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name=f"Sân {name}",
            field_type_id=field_type_id,
            capacity=4,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.flush()
        db.session.add(
            FieldPriceSlot(
                field_id=field.id,
                day_of_week=0,
                start_time=time(6, 0),
                end_time=time(23, 0),
                hourly_price=Decimal("200000"),
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()
        return venue.id


def test_default_catalog_has_four_sports_and_six_field_types(app):
    with app.app_context():
        sports = list(db.session.scalars(db.select(Sport).order_by(Sport.id)))
        field_types = list(
            db.session.scalars(db.select(FieldType).order_by(FieldType.id))
        )

        assert [item.code for item in sports] == [
            SportCode.FOOTBALL.value,
            SportCode.BADMINTON.value,
            SportCode.PICKLEBALL.value,
            SportCode.TENNIS.value,
        ]
        assert {item.code for item in field_types} == {
            item.value for item in FieldTypeCode
        }


def test_public_filter_options_include_their_parent_sport(app, client):
    response = client.get("/venues")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="field-type-filter-options"' in page
    assert (
        'data-sport="BADMINTON" value="BADMINTON_STANDARD"'
        in page
    )
    assert 'data-sport="FOOTBALL" value="FOOTBALL_5"' in page
    assert 'data-sport="FOOTBALL" value="FOOTBALL_7"' in page
    assert 'data-sport="FOOTBALL" value="FOOTBALL_11"' in page
    assert 'data-sport="PICKLEBALL" value="PICKLEBALL_STANDARD"' in page
    assert 'data-sport="TENNIS" value="TENNIS_STANDARD"' in page


def test_public_search_rejects_mismatched_sport_and_field_type(app, client):
    response = client.get(
        "/venues",
        query_string={
            "sport": SportCode.FOOTBALL.value,
            "field_type": FieldTypeCode.TENNIS_STANDARD.value,
        },
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Loại sân không thuộc bộ môn đã chọn." in page
    assert "Bộ lọc chưa hợp lệ" in page


def test_sport_filter_only_summarizes_matching_field_types(app):
    owner_id = create_user(
        app,
        email="mixed-sport-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Cơ sở đa môn",
        latitude=None,
        longitude=None,
        field_type_code=FieldTypeCode.BADMINTON_STANDARD.value,
    )

    with app.app_context():
        football_type_id = db.session.scalar(
            db.select(FieldType.id).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        football_field = Field(
            venue_id=venue_id,
            name="Sân bóng đá 5 người",
            field_type_id=football_type_id,
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(football_field)
        db.session.flush()
        db.session.add(
            FieldPriceSlot(
                field_id=football_field.id,
                day_of_week=0,
                start_time=time(6, 0),
                end_time=time(23, 0),
                hourly_price=Decimal("300000"),
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()

        result = search_public_venues(sport=SportCode.BADMINTON.value)

        assert result.total == 1
        assert [item.code for item in result.items[0].field_types] == [
            FieldTypeCode.BADMINTON_STANDARD.value
        ]


def test_owner_can_create_tennis_field_from_catalog(app):
    owner_id = create_user(
        app,
        email="tennis-owner@example.com",
        role=UserRole.OWNER,
    )
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name="Trung tâm tennis",
            address="12 Đường A",
            province_code="79",
            ward_code="27475",
            phone=None,
            description=None,
            opening_time=time(6, 0),
            closing_time=time(22, 0),
        )
        field = create_field(
            owner=owner,
            venue_id=venue.id,
            name="Sân tennis 1",
            field_type=FieldTypeCode.TENNIS_STANDARD.value,
            surface_type=None,
            capacity=4,
        )

        assert field.field_type.code == FieldTypeCode.TENNIS_STANDARD.value
        assert field.field_type.sport.code == SportCode.TENNIS.value


def test_field_type_cannot_change_after_booking_history_exists(app):
    owner_id = create_user(
        app,
        email="history-owner@example.com",
        role=UserRole.OWNER,
    )
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name="Cơ sở có lịch sử",
            address="15 Đường B",
            province_code="48",
            ward_code="20209",
            phone=None,
            description=None,
            opening_time=time(6, 0),
            closing_time=time(22, 0),
        )
        field = create_field(
            owner=owner,
            venue_id=venue.id,
            name="Sân cũ",
            field_type=FieldTypeCode.FOOTBALL_5.value,
            surface_type=None,
            capacity=10,
        )
        db.session.add(
            Booking(
                booking_code="BK-MULTISPORT-HISTORY",
                user_id=owner.id,
                field_id=field.id,
                booking_date=date.today() + timedelta(days=2),
                start_time=time(18, 0),
                end_time=time(19, 0),
                booking_mode=BookingMode.DIRECT_BOOKING.value,
                play_format=None,
                requested_players=None,
                payment_policy=BookingPaymentPolicy.LEGACY_FULL_ONLINE.value,
                total_amount=Decimal("200000"),
                deposit_rate=Decimal("1"),
                deposit_amount=Decimal("200000"),
                paid_amount=Decimal("0"),
                cancellation_fee_amount=Decimal("0"),
                status=BookingStatus.CONFIRMED.value,
            )
        )
        db.session.commit()

        with pytest.raises(ImmutableFieldTypeError):
            update_field(
                field_id=field.id,
                owner=owner,
                name=field.name,
                field_type=FieldTypeCode.TENNIS_STANDARD.value,
                surface_type=None,
                capacity=4,
            )


def test_venue_location_requires_complete_place_and_coordinate_pair(app):
    owner_id = create_user(
        app,
        email="location-owner@example.com",
        role=UserRole.OWNER,
    )
    with app.app_context():
        owner = db.session.get(User, owner_id)
        with pytest.raises(VenueError):
            create_venue(
                owner=owner,
                name="Cơ sở sai vị trí",
                address="20 Đường C",
                province_code="92",
                ward_code="31135",
                phone=None,
                description=None,
                opening_time=time(6, 0),
                closing_time=time(22, 0),
                google_place_id="place-only",
                latitude=Decimal("10.000000"),
                longitude=None,
            )


def test_admin_cannot_activate_new_venue_without_google_location(app):
    owner_id = create_user(
        app,
        email="pending-owner@example.com",
        role=UserRole.OWNER,
    )
    admin_id = create_user(
        app,
        email="maps-admin@example.com",
        role=UserRole.ADMIN,
    )
    with app.app_context():
        owner = db.session.get(User, owner_id)
        admin = db.session.get(User, admin_id)
        venue = create_venue(
            owner=owner,
            name="Cơ sở chưa ghim",
            address="25 Đường D",
            province_code="46",
            ward_code="19777",
            phone=None,
            description=None,
            opening_time=time(6, 0),
            closing_time=time(22, 0),
        )

        with pytest.raises(InvalidVenueStateError):
            moderate_venue(
                venue_id=venue.id,
                reviewer=admin,
                decision=VenueStatus.ACTIVE.value,
                moderation_note=None,
            )


def test_radius_search_filters_internal_venues_and_sorts_by_distance(app):
    owner_id = create_user(
        app,
        email="radius-owner@example.com",
        role=UserRole.OWNER,
    )
    near_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân gần",
        latitude=Decimal("10.777500"),
        longitude=Decimal("106.701500"),
        field_type_code=FieldTypeCode.BADMINTON_STANDARD.value,
    )
    create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân xa",
        latitude=Decimal("10.850000"),
        longitude=Decimal("106.780000"),
        field_type_code=FieldTypeCode.BADMINTON_STANDARD.value,
    )
    create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân chưa tọa độ",
        latitude=None,
        longitude=None,
        field_type_code=FieldTypeCode.BADMINTON_STANDARD.value,
    )

    with app.app_context():
        result = search_public_venues(
            sport=SportCode.BADMINTON.value,
            latitude=Decimal("10.776900"),
            longitude=Decimal("106.700900"),
            radius_km=3,
        )

        assert result.total == 1
        assert result.items[0].venue.id == near_id
        assert result.items[0].distance_km is not None
        assert result.items[0].distance_km < 1
        assert "destination_place_id=" in result.items[0].directions_url


def test_text_search_still_includes_legacy_venue_without_coordinates(app):
    owner_id = create_user(
        app,
        email="legacy-map-owner@example.com",
        role=UserRole.OWNER,
    )
    legacy_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Cơ sở Legacy",
        latitude=None,
        longitude=None,
        field_type_code=FieldTypeCode.FOOTBALL_7.value,
    )

    with app.app_context():
        result = search_public_venues(query="Legacy")

        assert result.total == 1
        assert result.items[0].venue.id == legacy_id
        assert result.items[0].distance_km is None
