import html
import json
import re
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
    FieldTypeCode,
    PriceSlotStatus,
    User,
    UserRole,
    Venue,
    VenueStatus,
    Ward,
)
from app.services import (
    GeocodingProviderError,
    GeocodingResult,
    VenueError,
    build_google_maps_directions_url,
    create_venue,
    list_provinces,
    list_wards,
    moderate_venue,
    register_user,
)


PASSWORD = "MatKhauAnToan123"
HCMC_PROVINCE_CODE = "79"
HCMC_WARD_CODE = "27475"


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
        "province_code": HCMC_PROVINCE_CODE,
        "ward_code": HCMC_WARD_CODE,
        "phone": " 0909876543 ",
        "description": "  Có bãi giữ xe và phòng thay đồ.  ",
        "opening_hour": "06",
        "opening_minute": "00",
        "closing_hour": "23",
        "closing_minute": "00",
        "owner_id": "999999",
        "status": VenueStatus.ACTIVE.value,
        "latitude": "10.776900",
        "longitude": "106.700900",
        "location_confirmed": "1",
    }
    data.update(overrides)
    return data


def create_venue_for_owner(app, owner_id: int, **overrides) -> int:
    with app.app_context():
        owner = db.session.get(User, owner_id)
        values = {
            "name": "Sân bóng Minh Anh",
            "address": "123 Nguyễn Hữu Thọ",
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
            "phone": "0909876543",
            "description": "Có bãi giữ xe.",
            "opening_time": time(6, 0),
            "closing_time": time(23, 0),
            "latitude": Decimal("10.776900"),
            "longitude": Decimal("106.700900"),
            "coordinates_confirmed": True,
        }
        values.update(overrides)
        venue = create_venue(owner=owner, **values)
        return venue.id


def create_searchable_venue(
    app,
    *,
    owner_id: int,
    name: str,
    address: str,
    district: str | None,
    city: str | None,
    field_name: str,
    field_type: FieldTypeCode,
    hourly_price: Decimal,
    province_code: str | None = None,
    province_name: str | None = None,
    ward_code: str | None = None,
    ward_name: str | None = None,
    venue_status: VenueStatus = VenueStatus.ACTIVE,
    field_status: FieldStatus = FieldStatus.ACTIVE,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> int:
    with app.app_context():
        venue = Venue(
            owner_id=owner_id,
            name=name,
            address=address,
            district=district,
            city=city,
            province_code=province_code,
            province_name=province_name,
            ward_code=ward_code,
            ward_name=ward_name,
            latitude=latitude,
            longitude=longitude,
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
                db.select(FieldType.id).where(FieldType.code == field_type.value)
            ),
            capacity=10,
            status=field_status.value,
        )
        db.session.add(field)
        db.session.flush()
        db.session.add(
            FieldPriceSlot(
                field_id=field.id,
                day_of_week=0,
                start_time=time(6, 0),
                end_time=time(23, 0),
                hourly_price=hourly_price,
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()
        return venue.id


def search_map_markers(page: str) -> list[dict[str, str]]:
    match = re.search(r"data-venues='([^']*)'", page)
    assert match is not None
    return json.loads(html.unescape(match.group(1)))


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


def test_administrative_catalog_loads_all_provinces_and_wards(app):
    with app.app_context():
        provinces = list_provinces()
        hcmc_wards = list_wards(province_code=HCMC_PROVINCE_CODE)

        assert len(provinces) == 34
        assert db.session.scalar(db.select(db.func.count(Ward.code))) == 3321
        assert any(
            province.code == HCMC_PROVINCE_CODE
            and province.name == "Thành phố Hồ Chí Minh"
            for province in provinces
        )
        assert any(
            ward.code == HCMC_WARD_CODE
            and ward.full_name == "Phường Tân Hưng"
            for ward in hcmc_wards
        )


def test_ward_api_filters_by_province_and_validates_code(app, client):
    response = client.get(
        "/api/administrative-units/wards",
        query_string={"province_code": HCMC_PROVINCE_CODE},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert any(item["code"] == HCMC_WARD_CODE for item in payload["wards"])
    assert not any(item["code"] == "20209" for item in payload["wards"])
    assert client.get("/api/administrative-units/wards").status_code == 400
    assert (
        client.get(
            "/api/administrative-units/wards",
            query_string={"province_code": "00"},
        ).status_code
        == 400
    )


def test_owner_form_rejects_ward_outside_selected_province(app, client):
    owner = create_user(
        app,
        email="mismatch-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    response = client.post(
        "/owner/venues/new",
        data=venue_form_data(ward_code="20209"),
    )

    assert response.status_code == 200
    assert (
        "Phường, xã hoặc đặc khu không thuộc tỉnh/thành phố đã chọn."
        in response.get_data(as_text=True)
    )
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0


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
        assert venue.province_code == HCMC_PROVINCE_CODE
        assert venue.province_name == "Thành phố Hồ Chí Minh"
        assert venue.ward_code == HCMC_WARD_CODE
        assert venue.ward_name == "Phường Tân Hưng"
        assert venue.district is None
        assert venue.city is None
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


def test_public_venue_search_matches_name_and_area(app, client):
    owner = create_user(
        app,
        email="search-owner@example.com",
        role=UserRole.OWNER,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Sân bóng Hòa Bình",
        address="25 Nguyễn Tất Thành",
        district="Quận Thanh Khê",
        city="Đà Nẵng",
        field_name="Sân 5A",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("220000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Sân bóng Phú Mỹ",
        address="12 Nguyễn Lương Bằng",
        district="Quận Liên Chiểu",
        city="Đà Nẵng",
        field_name="Sân 7A",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("350000"),
    )

    by_name = client.get("/venues", query_string={"q": "hòa bình"})
    by_area = client.get("/venues", query_string={"q": "thanh khê"})

    assert by_name.status_code == 200
    by_name_page = by_name.get_data(as_text=True)
    assert "Sân bóng Hòa Bình" in by_name_page
    assert "Sân bóng Phú Mỹ" not in by_name_page
    assert by_name_page.count("25 Nguyễn Tất Thành, Quận Thanh Khê, Đà Nẵng") == 1
    assert "Quận Thanh Khê · Đà Nẵng" not in by_name_page
    assert "Giờ hoạt động" not in by_name_page
    assert "Google Maps" in by_name_page
    assert by_area.status_code == 200
    assert "Sân bóng Hòa Bình" in by_area.get_data(as_text=True)
    assert "Sân bóng Phú Mỹ" not in by_area.get_data(as_text=True)


@pytest.mark.parametrize(
    ("query", "email_key"),
    [("hồ chí minh", "province"), ("tân hưng", "ward")],
)
def test_public_venue_search_matches_structured_province_and_ward(
    app,
    client,
    query,
    email_key,
):
    owner = create_user(
        app,
        email=f"structured-{email_key}@example.com",
        role=UserRole.OWNER,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cơ sở địa chỉ chuẩn hóa",
        address="123 Nguyễn Hữu Thọ",
        district=None,
        city=None,
        province_code=HCMC_PROVINCE_CODE,
        province_name="Thành phố Hồ Chí Minh",
        ward_code=HCMC_WARD_CODE,
        ward_name="Phường Tân Hưng",
        field_name="Sân chuẩn hóa",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("250000"),
    )

    response = client.get("/venues", query_string={"q": query})

    assert response.status_code == 200
    assert "Cơ sở địa chỉ chuẩn hóa" in response.get_data(as_text=True)


def test_public_venue_search_filters_exact_structured_province_and_ward(
    app,
    client,
):
    owner = create_user(
        app,
        email="exact-structured-owner@example.com",
        role=UserRole.OWNER,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cơ sở đúng phường",
        address="123 Nguyễn Hữu Thọ",
        district=None,
        city=None,
        province_code=HCMC_PROVINCE_CODE,
        province_name="Thành phố Hồ Chí Minh",
        ward_code=HCMC_WARD_CODE,
        ward_name="Phường Tân Hưng",
        field_name="Sân đúng khu vực",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("250000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cơ sở dữ liệu cũ cùng thành phố",
        address="456 Đường Legacy",
        district="Quận 7",
        city="Thành phố Hồ Chí Minh",
            field_name="Sân dữ liệu cũ",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("200000"),
    )

    province_response = client.get(
        "/venues", query_string={"province_code": HCMC_PROVINCE_CODE}
    )
    ward_response = client.get(
        "/venues",
        query_string={
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    )

    for response in (province_response, ward_response):
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Cơ sở đúng phường" in page
        assert "Cơ sở dữ liệu cũ cùng thành phố" not in page
        assert "Thành phố Hồ Chí Minh" in page
        assert f'venue-type-chip">{HCMC_WARD_CODE}</span>' not in page
    assert "Phường Tân Hưng" in ward_response.get_data(as_text=True)


def test_public_venue_search_rejects_ward_without_matching_province(
    app,
    client,
):
    missing_province = client.get(
        "/venues", query_string={"ward_code": HCMC_WARD_CODE}
    )
    mismatched = client.get(
        "/venues",
        query_string={
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": "00004",
        },
    )

    assert missing_province.status_code == 200
    assert "Hãy chọn tỉnh hoặc thành phố trước" in missing_province.get_data(
        as_text=True
    )
    assert mismatched.status_code == 200
    assert "không thuộc tỉnh/thành phố đã chọn" in mismatched.get_data(
        as_text=True
    )


def test_structured_filters_are_preserved_in_venue_pagination(app, client):
    owner = create_user(
        app,
        email="structured-pagination-owner@example.com",
        role=UserRole.OWNER,
    )
    for number in range(1, 12):
        create_searchable_venue(
            app,
            owner_id=owner.id,
            name=f"Cơ sở cấu trúc {number:02d}",
            address=f"{number} Nguyễn Hữu Thọ",
            district=None,
            city=None,
            province_code=HCMC_PROVINCE_CODE,
            province_name="Thành phố Hồ Chí Minh",
            ward_code=HCMC_WARD_CODE,
            ward_name="Phường Tân Hưng",
            field_name=f"Sân cấu trúc {number:02d}",
            field_type=FieldTypeCode.FOOTBALL_5,
            hourly_price=Decimal("250000"),
        )

    response = client.get(
        "/venues",
        query_string={
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "11 cơ sở phù hợp" in page
    assert f"province_code={HCMC_PROVINCE_CODE}" in page
    assert f"ward_code={HCMC_WARD_CODE}" in page


def test_owner_admin_user_share_one_structured_venue_field_and_price(
    app,
    client,
):
    owner = create_user(
        app,
        email="consistent-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="consistent-admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(
        app,
        owner.id,
        name="Cơ sở xuyên suốt",
        address="88 Nguyễn Hữu Thọ",
    )
    with app.app_context():
        field = Field(
            venue_id=venue_id,
            name="Sân xuyên suốt",
            field_type_id=db.session.scalar(
                db.select(FieldType.id).where(
                    FieldType.code == FieldTypeCode.FOOTBALL_5.value
                )
            ),
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.flush()
        field_id = field.id
        db.session.add(
            FieldPriceSlot(
                field_id=field.id,
                day_of_week=0,
                start_time=time(6, 0),
                end_time=time(22, 0),
                hourly_price=Decimal("275000"),
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()
        reviewer = db.session.get(User, admin.id)
        moderate_venue(
            venue_id=venue_id,
            reviewer=reviewer,
            decision=VenueStatus.ACTIVE.value,
            moderation_note="Đã đối chiếu dữ liệu xuyên suốt.",
        )

    results = client.get(
        "/venues",
        query_string={
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    ).get_data(as_text=True)
    detail = client.get(f"/venues/{venue_id}").get_data(as_text=True)

    assert "Cơ sở xuyên suốt" in results
    assert "275.000 đ/giờ" in results
    assert "Sân xuyên suốt" in detail
    assert "275.000 đ/giờ" in detail
    assert 'class="nav-link active" href="/venues" aria-current="page"' in detail
    assert f'href="/venues/{venue_id}/fields/{field_id}/bookings/new"' in detail


def test_public_venue_detail_renders_leaflet_map_for_confirmed_coordinates(
    app,
    client,
):
    owner = create_user(
        app,
        email="public-map-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id, name="Cơ sở có bản đồ")
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        db.session.commit()

    response = client.get(f"/venues/{venue_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="venue-public-map"' in page
    assert 'data-latitude="10.776900"' in page
    assert 'data-longitude="106.700900"' in page
    assert "Vị trí đã xác nhận" in page
    assert "leaflet@1.9.4" in page
    assert "venue-detail-map.js" in page
    assert "/owner/venues/geocode" not in page
    assert "Mở chỉ đường trên Google Maps" in page


def test_public_venue_detail_without_coordinates_uses_address_fallback(
    app,
    client,
):
    owner = create_user(
        app,
        email="public-map-fallback-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(
        app,
        owner.id,
        name="Cơ sở chưa có tọa độ",
        latitude=None,
        longitude=None,
        coordinates_confirmed=False,
    )
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        db.session.commit()

    response = client.get(f"/venues/{venue_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Chưa có vị trí trên bản đồ" in page
    assert "123 Nguyễn Hữu Thọ" in page
    assert 'id="venue-public-map"' not in page
    assert "leaflet@1.9.4" not in page
    assert "venue-detail-map.js" not in page
    assert "Mở chỉ đường trên Google Maps" in page


def test_find_venue_map_marks_only_coordinate_results_in_current_set(
    app,
    client,
):
    owner = create_user(
        app,
        email="find-map-owner@example.com",
        role=UserRole.OWNER,
    )
    first_id = create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Ban do A",
        address="1 Duong A",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San A",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("200000"),
        latitude=Decimal("10.776900"),
        longitude=Decimal("106.700900"),
    )
    second_id = create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Ban do B",
        address="2 Duong B",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San B",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("250000"),
        latitude=Decimal("10.780000"),
        longitude=Decimal("106.710000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Ban do chua ghim",
        address="3 Duong C",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San C",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("220000"),
    )

    response = client.get("/venues", query_string={"q": "Ban do"})
    page = response.get_data(as_text=True)
    markers = search_map_markers(page)

    assert response.status_code == 200
    assert 'id="venue-search-map"' in page
    assert "2/3 cơ sở có vị trí" in page
    assert "Ban do chua ghim" in page
    assert {marker["name"] for marker in markers} == {"Ban do A", "Ban do B"}
    assert {marker["detail_url"] for marker in markers} == {
        f"/venues/{first_id}",
        f"/venues/{second_id}",
    }
    assert all(
        marker["latitude"] != "0.000000"
        and marker["longitude"] != "0.000000"
        for marker in markers
    )
    assert "/owner/venues/geocode" not in page
    assert "radius_km=" not in page


def test_find_venue_map_tracks_the_existing_sport_filter(app, client):
    owner = create_user(
        app,
        email="find-map-filter-owner@example.com",
        role=UserRole.OWNER,
    )
    football_id = create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Loc bong da",
        address="4 Duong D",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San D",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("200000"),
        latitude=Decimal("10.781000"),
        longitude=Decimal("106.711000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Loc cau long",
        address="5 Duong E",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San E",
        field_type=FieldTypeCode.BADMINTON_STANDARD,
        hourly_price=Decimal("180000"),
        latitude=Decimal("10.782000"),
        longitude=Decimal("106.712000"),
    )

    response = client.get("/venues", query_string={"sport": "FOOTBALL"})
    page = response.get_data(as_text=True)
    markers = search_map_markers(page)

    assert response.status_code == 200
    assert "1 cơ sở phù hợp" in page
    assert "1/1 cơ sở có vị trí" in page
    assert markers == [
        {
            "address": "4 Duong D, Phuong Tan Hung, TP. Ho Chi Minh",
            "detail_url": f"/venues/{football_id}",
            "latitude": "10.781000",
            "longitude": "106.711000",
            "name": "Loc bong da",
        }
    ]


def test_find_venue_map_uses_empty_state_when_results_have_no_coordinates(
    app,
    client,
):
    owner = create_user(
        app,
        email="find-map-empty-owner@example.com",
        role=UserRole.OWNER,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Khong co toa do",
        address="6 Duong F",
        district="Phuong Tan Hung",
        city="TP. Ho Chi Minh",
        field_name="San F",
        field_type=FieldTypeCode.TENNIS_STANDARD,
        hourly_price=Decimal("300000"),
    )

    response = client.get("/venues", query_string={"q": "Khong co toa do"})
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Chưa có vị trí hiển thị trên bản đồ" in page
    assert "Khong co toa do" in page
    assert 'id="venue-search-map"' not in page
    assert "leaflet@1.9.4" not in page
    assert "venue-search-map.js" not in page


def test_public_venue_filters_combine_field_type_and_matching_type_price(
    app,
    client,
):
    owner = create_user(
        app,
        email="filter-owner@example.com",
        role=UserRole.OWNER,
    )
    target_id = create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cụm sân Thành Công",
        address="10 Đường A",
        district="Quận 7",
        city="TP. Hồ Chí Minh",
        field_name="Sân 7 tiêu chuẩn",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("350000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cụm sân Giá Cao",
        address="20 Đường B",
        district="Quận 7",
        city="TP. Hồ Chí Minh",
        field_name="Sân 7 cao cấp",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("500000"),
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cụm sân Chưa Mở",
        address="30 Đường C",
        district="Quận 7",
        city="TP. Hồ Chí Minh",
        field_name="Sân 7 chưa mở",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("320000"),
        field_status=FieldStatus.INACTIVE,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cụm sân Bị Ẩn",
        address="40 Đường D",
        district="Quận 7",
        city="TP. Hồ Chí Minh",
        field_name="Sân 7 bị ẩn",
        field_type=FieldTypeCode.FOOTBALL_7,
        hourly_price=Decimal("330000"),
        venue_status=VenueStatus.HIDDEN,
    )

    response = client.get(
        "/venues",
        query_string={
            "field_type": FieldTypeCode.FOOTBALL_7.value,
            "min_price": "300000",
            "max_price": "400000",
        },
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Cụm sân Thành Công" in page
    assert "Cụm sân Giá Cao" not in page
    assert "Cụm sân Chưa Mở" not in page
    assert "Cụm sân Bị Ẩn" not in page
    assert f'/venues/{target_id}' in page
    assert "350.000 đ/giờ" in page
    assert "Bóng đá · Sân 7 người" in page
    assert "Xóa tất cả" in page
    assert "Xóa bộ lọc" not in page


def test_price_filter_uses_selected_field_type_price(app, client):
    owner = create_user(
        app,
        email="mixed-price-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Cụm sân Nhiều Loại",
        address="50 Đường E",
        district="Quận 3",
        city="TP. Hồ Chí Minh",
        field_name="Sân 5 giá tốt",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("150000"),
    )
    with app.app_context():
        field = Field(
            venue_id=venue_id,
            name="Sân 7 buổi tối",
            field_type_id=db.session.scalar(
                db.select(FieldType.id).where(
                    FieldType.code == FieldTypeCode.FOOTBALL_7.value
                )
            ),
            capacity=14,
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
                hourly_price=Decimal("450000"),
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()

    response = client.get(
        "/venues",
        query_string={
            "field_type": FieldTypeCode.FOOTBALL_7.value,
            "max_price": "200000",
        },
    )

    assert response.status_code == 200
    assert "Cụm sân Nhiều Loại" not in response.get_data(as_text=True)


def test_invalid_venue_price_range_keeps_values_and_shows_error(app, client):
    response = client.get(
        "/venues",
        query_string={"min_price": "500000", "max_price": "200000"},
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Giá tối thiểu không được lớn hơn giá tối đa." in page
    assert 'name="min_price"' in page
    assert 'value="500000"' in page
    assert 'name="max_price"' in page
    assert 'value="200000"' in page
    assert 'collapse venue-filter-collapse show' in page


def test_search_treats_sql_wildcards_as_literal_text(app, client):
    owner = create_user(
        app,
        email="wildcard-owner@example.com",
        role=UserRole.OWNER,
    )
    create_searchable_venue(
        app,
        owner_id=owner.id,
        name="Sân không có ký hiệu đặc biệt",
        address="60 Đường F",
        district="Quận 1",
        city="TP. Hồ Chí Minh",
        field_name="Sân 5 thường",
        field_type=FieldTypeCode.FOOTBALL_5,
        hourly_price=Decimal("200000"),
    )

    response = client.get("/venues", query_string={"q": "%"})

    assert response.status_code == 200
    assert "Sân không có ký hiệu đặc biệt" not in response.get_data(as_text=True)


def test_venue_search_paginates_and_keeps_filters(app, client):
    owner = create_user(
        app,
        email="pagination-owner@example.com",
        role=UserRole.OWNER,
    )
    for number in range(1, 12):
        create_searchable_venue(
            app,
            owner_id=owner.id,
            name=f"Sân Phân Trang {number:02d}",
            address=f"{number} Đường Kiểm Thử",
            district="Quận Hải Châu",
            city="Đà Nẵng",
            field_name=f"Sân 5 số {number:02d}",
            field_type=FieldTypeCode.FOOTBALL_5,
            hourly_price=Decimal("200000"),
        )

    query = {
        "q": "Phân Trang",
        "field_type": FieldTypeCode.FOOTBALL_5.value,
        "min_price": "100000",
        "max_price": "300000",
        "page": "2",
    }
    response = client.get("/venues", query_string=query)
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "11 cơ sở phù hợp" in page
    assert "Trang 2/2" in page
    assert "Sân Phân Trang 11" in page
    assert "Sân Phân Trang 01" not in page
    assert 'value="Phân Trang"' in page
    assert f'selected value="{FieldTypeCode.FOOTBALL_5.value}"' in page
    assert 'value="100000"' in page
    assert 'value="300000"' in page


def test_owner_critical_update_returns_active_venue_to_pending_review(app, client):
    owner = create_user(
        app,
        email="owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="reviewer@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        venue.reviewed_by = admin.id
        venue.reviewed_at = venue.created_at
        venue.moderation_note = "Đã duyệt trước đó."
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
        assert venue.status == VenueStatus.PENDING.value
        assert venue.latitude == Decimal("10.776900")
        assert venue.longitude == Decimal("106.700900")
        assert venue.reviewed_by is None
        assert venue.reviewed_at is None
        assert venue.moderation_note is None


def test_owner_create_requires_explicit_marker_confirmation(app, client):
    owner = create_user(app, email="unconfirmed-marker@example.com", role=UserRole.OWNER)
    login(client, email=owner.email)

    response = client.post(
        "/owner/venues/new",
        data=venue_form_data(location_confirmed="0"),
    )

    assert response.status_code == 200
    assert "Vui lòng xác nhận ghim vị trí" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0


def test_owner_noncritical_update_keeps_active_venue_approval(app, client):
    owner = create_user(
        app,
        email="noncritical-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="noncritical-reviewer@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        venue.reviewed_by = admin.id
        venue.reviewed_at = venue.created_at
        venue.moderation_note = "Duy trì công khai."
        db.session.commit()
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(description="Bổ sung bãi gửi xe có mái che."),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.description == "Bổ sung bãi gửi xe có mái che."
        assert venue.status == VenueStatus.ACTIVE.value
        assert venue.reviewed_by == admin.id
        assert venue.reviewed_at is not None
        assert venue.moderation_note == "Duy trì công khai."
        assert venue.latitude == Decimal("10.776900")
        assert venue.longitude == Decimal("106.700900")


def test_owner_form_has_leaflet_location_picker_without_public_maps_api(
    app,
    client,
):
    owner = create_user(
        app,
        email="location-consistency-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    response = client.get("/owner/venues/new")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Địa chỉ này được dùng để tìm vị trí trên bản đồ và mở chỉ đường." in page
    assert "venue-location-picker.js" in page
    assert "leaflet@1.9.4" in page
    assert "Xác nhận ghim" in page
    assert "Chưa xác nhận vị trí" in page
    assert "tile.openstreetmap.org" in page
    assert "maps.googleapis.com" not in page
    assert "google_place_id" not in page


def test_owner_venue_list_does_not_show_legacy_google_location_warning(
    app,
    client,
):
    owner = create_user(
        app,
        email="owner-list-without-maps@example.com",
        role=UserRole.OWNER,
    )
    create_venue_for_owner(app, owner.id)
    login(client, email=owner.email)

    response = client.get("/owner/venues")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Cơ sở chưa có vị trí Google" not in page
    assert "tìm kiếm gần tôi" not in page


def test_owner_venue_workspace_handles_empty_state(app, client):
    owner = create_user(
        app,
        email="empty-venue-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    response = client.get("/owner/venues")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Owner Console" in page
    assert "Bạn chưa có cơ sở nào" in page
    assert "Tạo cơ sở đầu tiên" in page
    assert "Chưa có ảnh cơ sở" not in page


@pytest.mark.parametrize(
    ("venue_count", "grid_modifier"),
    [(1, "owner-venue-grid--single"), (2, "owner-venue-grid--pair")],
)
def test_owner_venue_workspace_marks_compact_grids_by_venue_count(
    app,
    client,
    venue_count,
    grid_modifier,
):
    owner = create_user(
        app,
        email=f"venue-grid-{venue_count}@example.com",
        role=UserRole.OWNER,
    )
    for number in range(venue_count):
        create_venue_for_owner(app, owner.id, name=f"Cơ sở lưới {number}")
    login(client, email=owner.email)

    response = client.get("/owner/venues")

    assert response.status_code == 200
    assert grid_modifier in response.get_data(as_text=True)


def test_owner_venue_workspace_scopes_statuses_and_counts_fields(app, client):
    owner = create_user(
        app,
        email="venue-workspace-owner@example.com",
        role=UserRole.OWNER,
    )
    other_owner = create_user(
        app,
        email="venue-workspace-other@example.com",
        role=UserRole.OWNER,
    )
    status_venue_ids = []
    for status in VenueStatus:
        venue_id = create_venue_for_owner(
            app,
            owner.id,
            name=f"Cơ sở {status.value}",
        )
        status_venue_ids.append((venue_id, status))
    create_venue_for_owner(app, other_owner.id, name="Cơ sở không thuộc chủ sân")
    with app.app_context():
        for venue_id, status in status_venue_ids:
            db.session.get(Venue, venue_id).status = status.value
        field_type_id = db.session.scalar(
            db.select(FieldType.id).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        db.session.add_all(
            [
                Field(
                    venue_id=status_venue_ids[0][0],
                    name=f"Sân đếm {number}",
                    field_type_id=field_type_id,
                    capacity=10,
                    status=FieldStatus.ACTIVE.value,
                )
                for number in range(1, 3)
            ]
        )
        db.session.commit()
    login(client, email=owner.email)

    response = client.get("/owner/venues")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Cơ sở không thuộc chủ sân" not in page
    assert "2</strong> sân thuộc cơ sở" in page
    assert "Xem sân" in page
    for label in (
        "Đang chờ duyệt",
        "Đang hoạt động",
        "Đã bị ẩn",
        "Ngừng hoạt động",
    ):
        assert label in page


def test_owner_venue_form_uses_console_shell_and_rejects_short_address(
    app,
    client,
):
    owner = create_user(
        app,
        email="venue-form-shell-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)

    get_response = client.get("/owner/venues/new")
    invalid_response = client.post(
        "/owner/venues/new",
        data=venue_form_data(address="12"),
    )

    assert get_response.status_code == 200
    assert "owner-venue-form-card" in get_response.get_data(as_text=True)
    assert invalid_response.status_code == 200
    assert "Địa chỉ phải từ 5 đến 255 ký tự." in invalid_response.get_data(
        as_text=True
    )
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0


def test_owner_address_change_requires_location_reconfirmation(
    app,
    client,
):
    owner = create_user(
        app,
        email="clear-location-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.google_place_id = "legacy-place-id"
        venue.latitude = Decimal("10.776900")
        venue.longitude = Decimal("106.700900")
        db.session.commit()
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(
            address="456 Nguyễn Hữu Thọ",
            location_confirmed="0",
        ),
    )

    assert response.status_code == 200
    assert "Vui lòng xác nhận lại ghim" in response.get_data(as_text=True)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.address == "123 Nguyễn Hữu Thọ"
        assert venue.google_place_id == "legacy-place-id"
        assert venue.latitude == Decimal("10.776900")
        assert venue.longitude == Decimal("106.700900")


def test_active_venue_coordinate_only_change_returns_to_pending(app, client):
    owner = create_user(app, email="coordinate-owner@example.com", role=UserRole.OWNER)
    admin = create_user(app, email="coordinate-admin@example.com", role=UserRole.ADMIN)
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.status = VenueStatus.ACTIVE.value
        venue.reviewed_by = admin.id
        venue.moderation_note = "Đã kiểm tra."
        db.session.commit()
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(latitude="10.777100", longitude="106.701200"),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.latitude == Decimal("10.777100")
        assert venue.longitude == Decimal("106.701200")
        assert venue.status == VenueStatus.PENDING.value
        assert venue.reviewed_by is None
        assert venue.moderation_note is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"latitude": "91"}, "Vĩ độ phải là số từ -90 đến 90."),
        ({"longitude": "not-a-number"}, "Kinh độ phải là số từ -180 đến 180."),
        ({"longitude": ""}, "Vĩ độ và kinh độ phải được gửi cùng nhau."),
    ],
)
def test_owner_create_rejects_invalid_coordinate_input(app, client, overrides, message):
    owner = create_user(app, email=f"invalid-{len(message)}@example.com", role=UserRole.OWNER)
    login(client, email=owner.email)

    response = client.post("/owner/venues/new", data=venue_form_data(**overrides))

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0


def test_existing_venue_without_coordinates_remains_editable(app, client):
    owner = create_user(app, email="legacy-no-coordinates@example.com", role=UserRole.OWNER)
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        venue.latitude = None
        venue.longitude = None
        db.session.commit()
    login(client, email=owner.email)

    response = client.post(
        f"/owner/venues/{venue_id}/edit",
        data=venue_form_data(
            description="Cập nhật mô tả, không đổi vị trí.",
            latitude="",
            longitude="",
            location_confirmed="0",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.latitude is None
        assert venue.longitude is None
        assert venue.description == "Cập nhật mô tả, không đổi vị trí."


def test_owner_geocode_endpoint_returns_mocked_suggestion(app, client, monkeypatch):
    owner = create_user(app, email="geocode-owner@example.com", role=UserRole.OWNER)
    login(client, email=owner.email)
    monkeypatch.setattr(
        "app.routes.venues.geocode_venue_address",
        lambda **kwargs: GeocodingResult(
            latitude=Decimal("10.776900"),
            longitude=Decimal("106.700900"),
            display_name="Vị trí gợi ý",
            query="query",
        ),
    )

    response = client.post(
        "/owner/venues/geocode",
        data={
            "address": "123 Nguyễn Hữu Thọ",
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "latitude": "10.776900",
        "longitude": "106.700900",
        "display_name": "Vị trí gợi ý",
    }


def test_owner_geocode_endpoint_handles_provider_failure(app, client, monkeypatch):
    owner = create_user(app, email="geocode-failure@example.com", role=UserRole.OWNER)
    login(client, email=owner.email)

    def fail_geocoding(**kwargs):
        raise GeocodingProviderError(
            "Không thể kết nối dịch vụ tìm vị trí. Bạn vẫn có thể đặt ghim thủ công trên bản đồ."
        )

    monkeypatch.setattr("app.routes.venues.geocode_venue_address", fail_geocoding)
    response = client.post(
        "/owner/venues/geocode",
        data={
            "address": "123 Nguyễn Hữu Thọ",
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    )

    assert response.status_code == 503
    assert "đặt ghim thủ công" in response.get_json()["error"]


def test_non_owner_cannot_use_geocode_endpoint(app, client):
    player = create_user(app, email="geocode-player@example.com", role=UserRole.USER)
    login(client, email=player.email)

    response = client.post(
        "/owner/venues/geocode",
        data={
            "address": "123 Nguyễn Hữu Thọ",
            "province_code": HCMC_PROVINCE_CODE,
            "ward_code": HCMC_WARD_CODE,
        },
    )

    assert response.status_code == 403


def test_owner_edit_form_keeps_structured_province_and_ward_selection(app, client):
    owner = create_user(
        app,
        email="edit-address-owner@example.com",
        role=UserRole.OWNER,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=owner.email)

    response = client.get(f"/owner/venues/{venue_id}/edit")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f'selected value="{HCMC_PROVINCE_CODE}"' in page
    assert f'selected value="{HCMC_WARD_CODE}"' in page
    assert "Phường Tân Hưng" in page


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

    assert client.get(f"/owner/venues/{venue_id}/edit").status_code == 403
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
    assert "Chờ duyệt" in page
    assert "Duyệt và công khai" in page
    assert "Kiểm tra đường đi" in page
    assert "Mở chỉ đường trên Google Maps" in page
    assert "Dữ liệu Google Maps" not in page
    assert "admin-venue-workspace" in page


def test_admin_venue_status_filter_shows_only_selected_status(app, client):
    owner = create_user(
        app,
        email="filter-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="filter-admin@example.com",
        role=UserRole.ADMIN,
    )
    pending_id = create_venue_for_owner(
        app,
        owner.id,
        name="Cơ sở chờ duyệt",
    )
    active_id = create_venue_for_owner(
        app,
        owner.id,
        name="Cơ sở đang hoạt động",
    )
    hidden_id = create_venue_for_owner(
        app,
        owner.id,
        name="Cơ sở đã ẩn",
    )
    with app.app_context():
        db.session.get(Venue, active_id).status = VenueStatus.ACTIVE.value
        db.session.get(Venue, hidden_id).status = VenueStatus.HIDDEN.value
        db.session.commit()
    login(client, email=admin.email)

    response = client.get("/admin/venues?status=ACTIVE")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Cơ sở đang hoạt động" in page
    assert "Cơ sở chờ duyệt" not in page
    assert "Cơ sở đã ẩn" not in page
    assert f"admin-venue-panel-{active_id}" in page
    assert f"admin-venue-panel-{pending_id}" not in page


def test_admin_can_activate_pending_venue_without_maps_data(
    app,
    client,
):
    owner = create_user(
        app,
        email="missing-location-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="missing-location-admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    login(client, email=admin.email)

    response = client.post(
        f"/admin/venues/{venue_id}/moderate",
        data=moderate_form_data(venue_id, VenueStatus.ACTIVE),
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Venue, venue_id).status == VenueStatus.ACTIVE.value


def test_admin_reactivates_hidden_venue_without_maps_data(app, client):
    owner = create_user(
        app,
        email="hidden-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="hidden-admin@example.com",
        role=UserRole.ADMIN,
    )
    venue_id = create_venue_for_owner(app, owner.id)
    with app.app_context():
        db.session.get(Venue, venue_id).status = VenueStatus.HIDDEN.value
        db.session.commit()
    login(client, email=admin.email)

    response = client.post(
        f"/admin/venues/{venue_id}/moderate",
        data=moderate_form_data(
            venue_id,
            VenueStatus.ACTIVE,
            "Đã đối chiếu lại vị trí.",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        venue = db.session.get(Venue, venue_id)
        assert venue.status == VenueStatus.ACTIVE.value
        assert venue.reviewed_by == admin.id
        assert venue.reviewed_at is not None
        assert venue.moderation_note == "Đã đối chiếu lại vị trí."


def test_admin_venue_workspace_has_directions_without_embedded_map(app, client):
    owner = create_user(
        app,
        email="map-component-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="map-component-admin@example.com",
        role=UserRole.ADMIN,
    )
    create_venue_for_owner(app, owner.id, name="Cơ sở 1")
    create_venue_for_owner(app, owner.id, name="Cơ sở 2")
    login(client, email=admin.email)

    response = client.get("/admin/venues?status=PENDING")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.count("Mở chỉ đường trên Google Maps") == 2
    assert 'id="admin-venue-selected-map"' not in page
    assert "data-admin-venue-map-slot" not in page
    assert "/static/js/admin-venue-map.js" not in page
    assert "maps.googleapis.com" not in page


def test_admin_venue_workspace_handles_legacy_address_without_maps_data(
    app,
    client,
):
    owner = create_user(
        app,
        email="legacy-venue-owner@example.com",
        role=UserRole.OWNER,
    )
    admin = create_user(
        app,
        email="legacy-venue-admin@example.com",
        role=UserRole.ADMIN,
    )
    with app.app_context():
        venue = Venue(
            owner_id=owner.id,
            name="Cơ sở dữ liệu cũ",
            address="10 Đường Legacy",
            district="Quận 7",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(22, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.commit()
    login(client, email=admin.email)

    response = client.get("/admin/venues?status=ACTIVE")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Cơ sở dữ liệu cũ" in page
    assert "10 Đường Legacy, Quận 7, TP. Hồ Chí Minh" in page
    assert "Mở chỉ đường trên Google Maps" in page
    assert "Dữ liệu Google Maps" not in page


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
                province_code=HCMC_PROVINCE_CODE,
                ward_code=HCMC_WARD_CODE,
                phone=None,
                description=None,
                opening_time=time(6, 0),
                closing_time=time(22, 0),
            )

        assert rollback_called is True
        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 0
