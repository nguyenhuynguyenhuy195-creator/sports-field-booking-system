from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from math import asin, ceil, cos, radians, sin, sqrt
from urllib.parse import urlencode

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Field,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    CatalogStatus,
    PriceSlotStatus,
    Sport,
    User,
    UserRole,
    Venue,
    VenueStatus,
)
from app.models.user import utc_now
from app.services.auth import normalize_full_name, normalize_phone
from app.services.sport_catalog import (
    SportCatalogError,
    get_active_field_type,
    get_active_sport,
)


class VenueError(ValueError):
    """Base error for venue business rules."""


class VenueNotFoundError(VenueError):
    """Raised when a venue id does not exist or is not publicly visible."""


class VenuePermissionError(VenueError):
    """Raised when an owner tries to manage another owner's venue."""


class InvalidVenueStateError(VenueError):
    """Raised when a moderation transition would not change the venue."""


@dataclass(frozen=True)
class PublicFieldTypeSummary:
    code: str
    name: str
    sport_code: str
    sport_name: str


@dataclass(frozen=True)
class PublicVenueSearchResult:
    venue: Venue
    starting_price: Decimal | None
    field_types: tuple[PublicFieldTypeSummary, ...]
    distance_km: float | None
    directions_url: str


@dataclass(frozen=True)
class PublicVenueSearchPage:
    items: tuple[PublicVenueSearchResult, ...]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return ceil(self.total / self.per_page) if self.total else 0

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def _normalize_required_text(value: str) -> str:
    return normalize_full_name(value)


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    return normalized or None


def _validate_operating_hours(opening_time: time, closing_time: time) -> None:
    if opening_time >= closing_time:
        raise VenueError("Giờ đóng cửa phải sau giờ mở cửa.")


def list_public_venues() -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.status == VenueStatus.ACTIVE.value)
            .order_by(Venue.name.asc())
        )
    )


def search_public_venues(
    *,
    query: str | None = None,
    sport: str | None = None,
    field_type: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    radius_km: int | None = None,
    page: int = 1,
    per_page: int = 9,
) -> PublicVenueSearchPage:
    """Return bookable public venues matching the validated search filters."""
    normalized_query = " ".join((query or "").split())
    normalized_sport = (sport or "").strip().upper() or None
    normalized_field_type = (field_type or "").strip() or None
    try:
        selected_sport = (
            get_active_sport(normalized_sport) if normalized_sport else None
        )
        selected_field_type = (
            get_active_field_type(normalized_field_type)
            if normalized_field_type
            else None
        )
    except SportCatalogError as exc:
        raise VenueError(str(exc)) from exc
    if (
        selected_sport is not None
        and selected_field_type is not None
        and selected_field_type.sport_id != selected_sport.id
    ):
        raise VenueError("Loại sân không thuộc bộ môn đã chọn.")
    if min_price is not None and min_price < 0:
        raise VenueError("Giá tối thiểu không được là số âm.")
    if max_price is not None and max_price < 0:
        raise VenueError("Giá tối đa không được là số âm.")
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise VenueError("Giá tối thiểu không được lớn hơn giá tối đa.")
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 50:
        raise VenueError("Số kết quả mỗi trang không hợp lệ.")
    coordinates = _validate_coordinates(latitude, longitude)
    if coordinates is None and radius_km is not None:
        raise VenueError("Cần có vị trí hiện tại để tìm sân theo bán kính.")
    if coordinates is not None and radius_km not in {3, 5, 10}:
        raise VenueError("Bán kính tìm kiếm chỉ nhận 3 km, 5 km hoặc 10 km.")

    active_field_conditions = [
        Field.venue_id == Venue.id,
        Field.status == FieldStatus.ACTIVE.value,
    ]
    if selected_field_type is not None:
        active_field_conditions.append(
            Field.field_type_id == selected_field_type.id
        )
    elif selected_sport is not None:
        active_field_conditions.append(
            Field.field_type_id.in_(
                db.select(FieldType.id).where(
                    FieldType.sport_id == selected_sport.id,
                    FieldType.status == CatalogStatus.ACTIVE.value,
                )
            )
        )

    eligible_field_exists = (
        db.select(Field.id).where(*active_field_conditions).exists()
    )
    starting_price = (
        db.select(db.func.min(FieldPriceSlot.hourly_price))
        .select_from(FieldPriceSlot)
        .join(Field, Field.id == FieldPriceSlot.field_id)
        .where(
            *active_field_conditions,
            FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value,
        )
        .correlate(Venue)
        .scalar_subquery()
    )

    statement = db.select(
        Venue,
        starting_price.label("starting_price"),
    ).where(
        Venue.status == VenueStatus.ACTIVE.value,
        eligible_field_exists,
    )

    if normalized_query:
        pattern = f"%{_escape_like_value(normalized_query.lower())}%"
        statement = statement.where(
            or_(
                db.func.lower(Venue.name).like(pattern, escape="\\"),
                db.func.lower(Venue.address).like(pattern, escape="\\"),
                db.func.lower(Venue.city).like(pattern, escape="\\"),
                and_(
                    Venue.district.is_not(None),
                    db.func.lower(Venue.district).like(
                        pattern,
                        escape="\\",
                    ),
                ),
            )
        )
    if min_price is not None:
        statement = statement.where(starting_price >= min_price)
    if max_price is not None:
        statement = statement.where(starting_price <= max_price)
    if coordinates is not None:
        statement = statement.where(
            Venue.latitude.is_not(None),
            Venue.longitude.is_not(None),
        )

    rows = db.session.execute(statement.order_by(Venue.name.asc())).all()
    rows_with_distance: list[tuple[Venue, Decimal | None, float | None]] = []
    for venue, price in rows:
        distance = None
        if coordinates is not None:
            distance = _haversine_km(
                coordinates[0],
                coordinates[1],
                Decimal(venue.latitude),
                Decimal(venue.longitude),
            )
            if distance > radius_km:
                continue
        rows_with_distance.append((venue, price, distance))

    if coordinates is not None:
        rows_with_distance.sort(key=lambda row: (row[2], row[0].name.lower()))
    total = len(rows_with_distance)
    total_pages = ceil(total / per_page) if total else 0
    if total_pages and page > total_pages:
        page = total_pages

    page_rows = rows_with_distance[(page - 1) * per_page : page * per_page]
    if not page_rows:
        return PublicVenueSearchPage(
            items=(),
            page=page,
            per_page=per_page,
            total=total,
        )

    venue_ids = [venue.id for venue, _, _ in page_rows]
    field_type_rows = db.session.execute(
        db.select(
            Field.venue_id,
            FieldType.code,
            FieldType.name,
            Sport.code,
            Sport.name,
        )
        .join(FieldType, FieldType.id == Field.field_type_id)
        .join(Sport, Sport.id == FieldType.sport_id)
        .where(
            Field.venue_id.in_(venue_ids),
            Field.status == FieldStatus.ACTIVE.value,
            FieldType.status == CatalogStatus.ACTIVE.value,
            Sport.status == CatalogStatus.ACTIVE.value,
        )
        .distinct()
    ).all()
    types_by_venue: dict[int, list[PublicFieldTypeSummary]] = {}
    for venue_id, type_code, type_name, sport_code, sport_name in field_type_rows:
        types_by_venue.setdefault(venue_id, []).append(
            PublicFieldTypeSummary(
                code=type_code,
                name=type_name,
                sport_code=sport_code,
                sport_name=sport_name,
            )
        )

    return PublicVenueSearchPage(
        items=tuple(
            PublicVenueSearchResult(
                venue=venue,
                starting_price=price,
                field_types=tuple(
                    sorted(
                        types_by_venue.get(venue.id, []),
                        key=lambda item: (item.sport_name, item.name),
                    )
                ),
                distance_km=distance,
                directions_url=build_google_maps_directions_url(venue),
            )
            for venue, price, distance in page_rows
        ),
        page=page,
        per_page=per_page,
        total=total,
    )


def _validate_coordinates(
    latitude: Decimal | None,
    longitude: Decimal | None,
) -> tuple[Decimal, Decimal] | None:
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise VenueError("Vĩ độ và kinh độ phải được cung cấp cùng nhau.")
    if latitude < Decimal("-90") or latitude > Decimal("90"):
        raise VenueError("Vĩ độ không hợp lệ.")
    if longitude < Decimal("-180") or longitude > Decimal("180"):
        raise VenueError("Kinh độ không hợp lệ.")
    return latitude, longitude


def _haversine_km(
    origin_latitude: Decimal,
    origin_longitude: Decimal,
    venue_latitude: Decimal,
    venue_longitude: Decimal,
) -> float:
    origin_lat = radians(float(origin_latitude))
    venue_lat = radians(float(venue_latitude))
    delta_lat = venue_lat - origin_lat
    delta_lng = radians(float(venue_longitude - origin_longitude))
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(origin_lat) * cos(venue_lat) * sin(delta_lng / 2) ** 2
    )
    return 6371.0088 * 2 * asin(sqrt(haversine))


def build_google_maps_directions_url(venue: Venue) -> str:
    if venue.has_coordinates:
        destination = f"{venue.latitude},{venue.longitude}"
    else:
        destination = ", ".join(
            item
            for item in (venue.address, venue.district, venue.city)
            if item
        )
    parameters = {"api": "1", "destination": destination}
    if venue.google_place_id:
        parameters["destination_place_id"] = venue.google_place_id
    return "https://www.google.com/maps/dir/?" + urlencode(parameters)


def _escape_like_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def get_public_venue(venue_id: int) -> Venue:
    venue = db.session.scalar(
        db.select(Venue)
        .options(joinedload(Venue.owner))
        .where(
            Venue.id == venue_id,
            Venue.status == VenueStatus.ACTIVE.value,
        )
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở đang hoạt động.")
    return venue


def list_owner_venues(owner_id: int) -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.created_at.desc())
        )
    )


def get_owner_venue(*, venue_id: int, owner_id: int) -> Venue:
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")
    return venue


def list_admin_venues() -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .options(joinedload(Venue.owner), joinedload(Venue.reviewer))
            .order_by(Venue.created_at.desc())
        )
    )


def create_venue(
    *,
    owner: User,
    name: str,
    address: str,
    district: str | None,
    city: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
    google_place_id: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được tạo cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)
    normalized_location = _normalize_venue_location(
        google_place_id=google_place_id,
        latitude=latitude,
        longitude=longitude,
    )

    venue = Venue(
        owner_id=owner.id,
        name=_normalize_required_text(name),
        address=_normalize_required_text(address),
        district=_normalize_optional_text(district),
        city=_normalize_required_text(city),
        google_place_id=normalized_location[0],
        latitude=normalized_location[1],
        longitude=normalized_location[2],
        phone=normalize_phone(phone),
        description=(description or "").strip() or None,
        opening_time=opening_time,
        closing_time=closing_time,
        status=VenueStatus.PENDING.value,
    )
    db.session.add(venue)
    _commit_or_raise("Không thể tạo cơ sở lúc này. Vui lòng thử lại.")
    return venue


def update_venue(
    *,
    venue_id: int,
    owner: User,
    name: str,
    address: str,
    district: str | None,
    city: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
    google_place_id: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được sửa cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)
    normalized_location = _normalize_venue_location(
        google_place_id=google_place_id,
        latitude=latitude,
        longitude=longitude,
    )

    venue = db.session.scalar(
        db.select(Venue).where(Venue.id == venue_id).with_for_update()
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner.id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")

    venue.name = _normalize_required_text(name)
    venue.address = _normalize_required_text(address)
    venue.district = _normalize_optional_text(district)
    venue.city = _normalize_required_text(city)
    venue.google_place_id = normalized_location[0]
    venue.latitude = normalized_location[1]
    venue.longitude = normalized_location[2]
    venue.phone = normalize_phone(phone)
    venue.description = (description or "").strip() or None
    venue.opening_time = opening_time
    venue.closing_time = closing_time

    _commit_or_raise("Không thể cập nhật cơ sở lúc này. Vui lòng thử lại.")
    return venue


def moderate_venue(
    *,
    venue_id: int,
    reviewer: User,
    decision: str,
    moderation_note: str | None,
) -> Venue:
    if reviewer.role != UserRole.ADMIN.value:
        raise VenuePermissionError("Chỉ quản trị viên được kiểm duyệt cơ sở.")
    if decision not in {VenueStatus.ACTIVE.value, VenueStatus.HIDDEN.value}:
        raise VenueError("Trạng thái kiểm duyệt không hợp lệ.")

    venue = db.session.scalar(
        db.select(Venue).where(Venue.id == venue_id).with_for_update()
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.status == decision:
        raise InvalidVenueStateError(
            "Cơ sở đã ở trạng thái này nên không có thay đổi nào được lưu."
        )
    if decision == VenueStatus.ACTIVE.value and (
        not venue.google_place_id or not venue.has_coordinates
    ):
        raise InvalidVenueStateError(
            "Cơ sở cần chọn vị trí Google đầy đủ trước khi được công khai."
        )

    venue.status = decision
    venue.reviewed_by = reviewer.id
    venue.reviewed_at = utc_now()
    venue.moderation_note = (moderation_note or "").strip() or None

    _commit_or_raise(
        "Không thể lưu kết quả kiểm duyệt lúc này. Vui lòng thử lại."
    )
    return venue


def _normalize_venue_location(
    *,
    google_place_id: str | None,
    latitude: Decimal | None,
    longitude: Decimal | None,
) -> tuple[str | None, Decimal | None, Decimal | None]:
    normalized_place_id = (google_place_id or "").strip() or None
    coordinates = _validate_coordinates(latitude, longitude)
    if normalized_place_id is None and coordinates is None:
        return None, None, None
    if normalized_place_id is None or coordinates is None:
        raise VenueError(
            "Vị trí Google chưa đầy đủ. Hãy chọn lại một gợi ý địa chỉ."
        )
    if len(normalized_place_id) > 255:
        raise VenueError("Google Place ID không hợp lệ.")
    return normalized_place_id, coordinates[0], coordinates[1]


def _commit_or_raise(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise VenueError(message) from exc
