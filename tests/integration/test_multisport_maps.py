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


def test_new_venue_uses_structured_address_without_google_location(app):
    owner_id = create_user(
        app,
        email="location-owner@example.com",
        role=UserRole.OWNER,
    )
    with app.app_context():
        owner = db.session.get(User, owner_id)
        venue = create_venue(
            owner=owner,
            name="Cơ sở không dùng bản đồ nhúng",
            address="20 Đường C",
            province_code="92",
            ward_code="31135",
            phone=None,
            description=None,
            opening_time=time(6, 0),
            closing_time=time(22, 0),
        )

        assert venue.google_place_id is None
        assert venue.latitude is None
        assert venue.longitude is None


def test_admin_can_activate_new_venue_without_google_location(app):
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

        moderate_venue(
            venue_id=venue.id,
            reviewer=admin,
            decision=VenueStatus.ACTIVE.value,
            moderation_note=None,
        )

        assert venue.status == VenueStatus.ACTIVE.value


def test_search_does_not_require_coordinates_or_radius(app):
    owner_id = create_user(
        app,
        email="radius-owner@example.com",
        role=UserRole.OWNER,
    )
    create_public_venue_with_field(
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
        result = search_public_venues(sport=SportCode.BADMINTON.value)

        assert result.total == 3
        assert all(
            not hasattr(item, "distance_km") for item in result.items
        )
        assert all(
            item.directions_url.startswith("https://www.google.com/maps/dir/")
            for item in result.items
        )


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
        assert result.items[0].directions_url.startswith(
            "https://www.google.com/maps/dir/"
        )


def test_public_listing_keeps_directions_without_embedded_maps(app, client):
    owner_id = create_user(
        app,
        email="public-marker-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân marker công khai",
        latitude=Decimal("10.777500"),
        longitude=Decimal("106.701500"),
        field_type_code=FieldTypeCode.BADMINTON_STANDARD.value,
    )
    response = client.get("/venues")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f'href="/venues/{venue_id}"' in page
    assert "https://www.google.com/maps/dir/" in page
    assert "Mở chỉ đường trên Google Maps" in page
    assert "data-markers=" not in page
    assert "maps.googleapis.com" not in page


def test_public_pages_do_not_render_embedded_map_or_fallback(app, client):
    owner_id = create_user(
        app,
        email="public-map-fallback-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân không có API key",
        latitude=Decimal("10.777500"),
        longitude=Decimal("106.701500"),
        field_type_code=FieldTypeCode.FOOTBALL_5.value,
    )
    listing_response = client.get("/venues")
    detail_response = client.get(f"/venues/{venue_id}")
    listing_page = listing_response.get_data(as_text=True)
    detail_page = detail_response.get_data(as_text=True)

    assert listing_response.status_code == 200
    assert detail_response.status_code == 200
    assert "Bản đồ hiện chưa khả dụng" not in listing_page
    assert "Bản đồ hiện chưa khả dụng" not in detail_page
    assert "/static/js/venue-public-map.js" not in listing_page
    assert "/static/js/venue-public-map.js" not in detail_page
    assert "maps.googleapis.com" not in listing_page
    assert "maps.googleapis.com" not in detail_page
    assert "Mở chỉ đường" in listing_page
    assert "Mở chỉ đường trên Google Maps" in detail_page


def test_public_detail_keeps_only_external_google_maps_directions(
    app,
    client,
):
    owner_id = create_user(
        app,
        email="detail-map-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_public_venue_with_field(
        app,
        owner_id=owner_id,
        name="Sân chi tiết bản đồ",
        latitude=Decimal("10.777500"),
        longitude=Decimal("106.701500"),
        field_type_code=FieldTypeCode.TENNIS_STANDARD.value,
    )
    response = client.get(f"/venues/{venue_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "https://www.google.com/maps/dir/" in page
    assert "Mở chỉ đường trên Google Maps" in page
    assert "data-markers=" not in page
    assert "maps.googleapis.com" not in page


def test_text_search_paginates_without_location_filters(app, client):
    owner_id = create_user(
        app,
        email="nearby-pagination-owner@example.com",
        role=UserRole.OWNER,
    )
    for number in range(1, 12):
        create_public_venue_with_field(
            app,
            owner_id=owner_id,
            name=f"Sân gần phân trang {number:02d}",
            latitude=Decimal("10.777000") + Decimal(number) / Decimal("100000"),
            longitude=Decimal("106.701000"),
            field_type_code=FieldTypeCode.PICKLEBALL_STANDARD.value,
        )

    response = client.get(
        "/venues",
        query_string={
            "q": "gần phân trang",
            "page": "2",
        },
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "11 cơ sở phù hợp" in page
    assert "Trang 2/2" in page
    assert "q=g%E1%BA%A7n+ph%C3%A2n+trang" in page
    assert "latitude=" not in page
    assert "longitude=" not in page
    assert "radius_km=" not in page
