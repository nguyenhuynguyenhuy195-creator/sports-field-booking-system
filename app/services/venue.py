from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal, InvalidOperation
from math import asin, ceil, cos, radians, sin, sqrt
from urllib.parse import urlencode

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

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
from app.services.administrative_unit import (
    AdministrativeUnitError,
    resolve_administrative_address,
    resolve_province,
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
    directions_url: str
    distance_km: float | None = None


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


@dataclass(frozen=True)
class OwnerVenueSummary:
    venue: Venue
    field_count: int


def _normalize_required_text(value: str) -> str:
    return normalize_full_name(value)


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
    province_code: str | None = None,
    ward_code: str | None = None,
    sport: str | None = None,
    field_type: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    latitude: str | Decimal | None = None,
    longitude: str | Decimal | None = None,
    sort: str | None = None,
    page: int = 1,
    per_page: int = 10,
) -> PublicVenueSearchPage:
    """Return bookable public venues matching the validated search filters."""
    normalized_query = " ".join((query or "").split())
    normalized_province_code = (province_code or "").strip() or None
    normalized_ward_code = (ward_code or "").strip() or None
    normalized_sport = (sport or "").strip().upper() or None
    normalized_field_type = (field_type or "").strip() or None
    nearby_origin = _normalize_search_coordinates(latitude, longitude)
    normalized_sort = (sort or "").strip().lower()
    if nearby_origin is not None and not normalized_sort:
        normalized_sort = "nearest"
    if normalized_sort not in ("", "nearest"):
        raise VenueError("Cách sắp xếp không hợp lệ.")
    if normalized_sort == "nearest" and nearby_origin is None:
        raise VenueError(
            "Hãy cung cấp vị trí hiện tại trước khi sắp xếp gần nhất."
        )
    if normalized_ward_code and not normalized_province_code:
        raise VenueError(
            "Hãy chọn tỉnh hoặc thành phố trước khi chọn phường, xã."
        )
    selected_province = None
    selected_ward = None
    try:
        if normalized_province_code:
            selected_province = resolve_province(
                province_code=normalized_province_code
            )
        if normalized_ward_code:
            administrative_address = resolve_administrative_address(
                province_code=normalized_province_code,
                ward_code=normalized_ward_code,
            )
            selected_ward = administrative_address.ward
    except AdministrativeUnitError as exc:
        raise VenueError(str(exc)) from exc
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
    ).options(selectinload(Venue.media_images)).where(
        Venue.status == VenueStatus.ACTIVE.value,
        eligible_field_exists,
    )

    if normalized_query:
        pattern = f"%{_escape_like_value(normalized_query.lower())}%"
        statement = statement.where(
            or_(
                db.func.lower(Venue.name).like(pattern, escape="\\"),
                db.func.lower(Venue.address).like(pattern, escape="\\"),
                db.func.lower(
                    db.func.coalesce(Venue.province_name, Venue.city, "")
                ).like(pattern, escape="\\"),
                db.func.lower(
                    db.func.coalesce(Venue.ward_name, Venue.district, "")
                ).like(pattern, escape="\\"),
            )
        )
    if selected_province is not None:
        statement = statement.where(
            Venue.province_code == selected_province.code
        )
    if selected_ward is not None:
        statement = statement.where(Venue.ward_code == selected_ward.code)
    if min_price is not None:
        statement = statement.where(starting_price >= min_price)
    if max_price is not None:
        statement = statement.where(starting_price <= max_price)
    rows = db.session.execute(statement.order_by(Venue.name.asc())).all()
    filtered_rows: list[tuple[Venue, Decimal | None, float | None]] = []
    for venue, price in rows:
        distance_km = None
        if nearby_origin is not None:
            venue_coordinates = valid_venue_coordinates(venue)
            if venue_coordinates is None:
                continue
            distance_km = haversine_distance_km(
                nearby_origin[0],
                nearby_origin[1],
                venue_coordinates[0],
                venue_coordinates[1],
            )
        filtered_rows.append((venue, price, distance_km))

    if normalized_sort == "nearest":
        filtered_rows.sort(
            key=lambda row: (
                row[2] if row[2] is not None else float("inf"),
                row[0].name.casefold(),
                row[0].id,
            )
        )

    total = len(filtered_rows)
    total_pages = ceil(total / per_page) if total else 0
    if total_pages and page > total_pages:
        page = total_pages

    page_rows = filtered_rows[(page - 1) * per_page : page * per_page]
    if not page_rows:
        return PublicVenueSearchPage(
            items=(),
            page=page,
            per_page=per_page,
            total=total,
        )

    venue_ids = [venue.id for venue, _, _ in page_rows]
    visible_field_type_conditions = [
        Field.venue_id.in_(venue_ids),
        Field.status == FieldStatus.ACTIVE.value,
        FieldType.status == CatalogStatus.ACTIVE.value,
        Sport.status == CatalogStatus.ACTIVE.value,
    ]
    if selected_field_type is not None:
        visible_field_type_conditions.append(
            Field.field_type_id == selected_field_type.id
        )
    elif selected_sport is not None:
        visible_field_type_conditions.append(
            FieldType.sport_id == selected_sport.id
        )

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
        .where(*visible_field_type_conditions)
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
                directions_url=build_google_maps_directions_url(venue),
                distance_km=distance_km,
            )
            for venue, price, distance_km in page_rows
        ),
        page=page,
        per_page=per_page,
        total=total,
    )


def build_google_maps_directions_url(venue: Venue) -> str:
    parameters = {"api": "1", "destination": venue.full_address}
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
        .options(
            joinedload(Venue.owner),
            selectinload(Venue.media_images),
        )
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
    venue = db.session.scalar(
        db.select(Venue)
        .options(selectinload(Venue.media_images))
        .where(Venue.id == venue_id)
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")
    return venue


def _normalize_search_coordinates(
    latitude: str | Decimal | None,
    longitude: str | Decimal | None,
) -> tuple[float, float] | None:
    raw_latitude = str(latitude).strip() if latitude is not None else ""
    raw_longitude = str(longitude).strip() if longitude is not None else ""
    if bool(raw_latitude) != bool(raw_longitude):
        raise VenueError(
            "Thông tin vị trí hiện tại chưa đầy đủ. Vui lòng thử lại."
        )
    if not raw_latitude:
        return None

    try:
        normalized_latitude = Decimal(raw_latitude)
        normalized_longitude = Decimal(raw_longitude)
    except InvalidOperation as exc:
        raise VenueError(
            "Thông tin vị trí hiện tại không hợp lệ. Vui lòng thử lại."
        ) from exc
    if (
        not normalized_latitude.is_finite()
        or not normalized_longitude.is_finite()
        or not Decimal("-90") <= normalized_latitude <= Decimal("90")
        or not Decimal("-180") <= normalized_longitude <= Decimal("180")
    ):
        raise VenueError(
            "Thông tin vị trí hiện tại không hợp lệ. Vui lòng thử lại."
        )
    return float(normalized_latitude), float(normalized_longitude)


def valid_venue_coordinates(venue: Venue) -> tuple[float, float] | None:
    """Return a trusted coordinate pair suitable for public location features."""
    if not venue.has_coordinates:
        return None
    latitude = float(venue.latitude)
    longitude = float(venue.longitude)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if latitude == 0 and longitude == 0:
        return None
    return latitude, longitude


def haversine_distance_km(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    """Calculate great-circle distance using mean Earth radius 6,371.0088 km."""
    latitude_delta = radians(destination_latitude - origin_latitude)
    longitude_delta = radians(destination_longitude - origin_longitude)
    origin_radians = radians(origin_latitude)
    destination_radians = radians(destination_latitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(origin_radians)
        * cos(destination_radians)
        * sin(longitude_delta / 2) ** 2
    )
    angular_distance = 2 * asin(sqrt(min(1.0, max(0.0, haversine))))
    return 6371.0088 * angular_distance


def list_owner_venue_summaries(owner_id: int) -> list[OwnerVenueSummary]:
    """Return owner-scoped venues with their current field count."""
    field_count = (
        db.select(db.func.count(Field.id))
        .where(Field.venue_id == Venue.id)
        .correlate(Venue)
        .scalar_subquery()
    )
    rows = db.session.execute(
        db.select(Venue, field_count.label("field_count"))
        .options(selectinload(Venue.media_images))
        .where(Venue.owner_id == owner_id)
        .order_by(Venue.created_at.desc(), Venue.id.desc())
    ).all()
    return [
        OwnerVenueSummary(venue=venue, field_count=int(count or 0))
        for venue, count in rows
    ]


def list_admin_venues(*, status: str | None = None) -> list[Venue]:
    statement = db.select(Venue).options(
        joinedload(Venue.owner), joinedload(Venue.reviewer)
    )
    if status is not None:
        statement = statement.where(Venue.status == status)
    return list(
        db.session.scalars(statement.order_by(Venue.created_at.desc()))
    )


def create_venue(
    *,
    owner: User,
    name: str,
    address: str,
    province_code: str,
    ward_code: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
    latitude: str | Decimal | None = None,
    longitude: str | Decimal | None = None,
    coordinates_confirmed: bool = False,
    require_coordinates: bool = False,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được tạo cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)
    try:
        administrative_address = resolve_administrative_address(
            province_code=province_code,
            ward_code=ward_code,
        )
    except AdministrativeUnitError as exc:
        raise VenueError(str(exc)) from exc
    normalized_coordinates = _normalize_coordinates(latitude, longitude)
    if require_coordinates and normalized_coordinates is None:
        raise VenueError(
            "Vui lòng đặt và xác nhận ghim vị trí trước khi tạo cơ sở."
        )
    if normalized_coordinates is not None and not coordinates_confirmed:
        raise VenueError(
            "Vui lòng xác nhận ghim vị trí trước khi lưu cơ sở."
        )
    venue = Venue(
        owner_id=owner.id,
        name=_normalize_required_text(name),
        address=_normalize_required_text(address),
        province_code=administrative_address.province.code,
        province_name=administrative_address.province.name,
        ward_code=administrative_address.ward.code,
        ward_name=administrative_address.ward.full_name,
        phone=normalize_phone(phone),
        description=(description or "").strip() or None,
        opening_time=opening_time,
        closing_time=closing_time,
        latitude=(normalized_coordinates or (None, None))[0],
        longitude=(normalized_coordinates or (None, None))[1],
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
    province_code: str,
    ward_code: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
    latitude: str | Decimal | None = None,
    longitude: str | Decimal | None = None,
    coordinates_confirmed: bool = False,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được sửa cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)
    try:
        administrative_address = resolve_administrative_address(
            province_code=province_code,
            ward_code=ward_code,
        )
    except AdministrativeUnitError as exc:
        raise VenueError(str(exc)) from exc
    venue = db.session.scalar(
        db.select(Venue).where(Venue.id == venue_id).with_for_update()
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner.id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")

    normalized_name = _normalize_required_text(name)
    normalized_address = _normalize_required_text(address)
    address_changed = any(
        (
            venue.address != normalized_address,
            venue.province_code != administrative_address.province.code,
            venue.ward_code != administrative_address.ward.code,
        )
    )
    submitted_coordinates = _normalize_coordinates(latitude, longitude)
    current_coordinates = (
        (venue.latitude, venue.longitude) if venue.has_coordinates else None
    )
    if submitted_coordinates is None:
        if address_changed:
            raise VenueError(
                "Địa chỉ đã thay đổi. Vui lòng đặt và xác nhận lại ghim vị trí."
            )
        submitted_coordinates = current_coordinates
    coordinates_changed = submitted_coordinates != current_coordinates
    if (address_changed or coordinates_changed) and not coordinates_confirmed:
        raise VenueError(
            "Thông tin vị trí đã thay đổi. Vui lòng xác nhận lại ghim trước khi lưu."
        )
    location_changed = address_changed or coordinates_changed
    critical_change = any(
        (
            venue.name != normalized_name,
            location_changed,
        )
    )

    venue.name = normalized_name
    venue.address = normalized_address
    venue.province_code = administrative_address.province.code
    venue.province_name = administrative_address.province.name
    venue.ward_code = administrative_address.ward.code
    venue.ward_name = administrative_address.ward.full_name
    venue.phone = normalize_phone(phone)
    venue.description = (description or "").strip() or None
    venue.opening_time = opening_time
    venue.closing_time = closing_time
    if submitted_coordinates is not None:
        venue.latitude, venue.longitude = submitted_coordinates
    if location_changed:
        venue.google_place_id = None

    if venue.status == VenueStatus.ACTIVE.value and critical_change:
        # The current approval only applies to the location and identity that
        # were reviewed. Clear the single-record audit fields so the pending
        # venue cannot be mistaken for already reviewed content.
        venue.status = VenueStatus.PENDING.value
        venue.reviewed_by = None
        venue.reviewed_at = None
        venue.moderation_note = None

    _commit_or_raise("Không thể cập nhật cơ sở lúc này. Vui lòng thử lại.")
    return venue


def _normalize_coordinates(
    latitude: str | Decimal | None,
    longitude: str | Decimal | None,
) -> tuple[Decimal, Decimal] | None:
    raw_latitude = str(latitude).strip() if latitude is not None else ""
    raw_longitude = str(longitude).strip() if longitude is not None else ""
    if bool(raw_latitude) != bool(raw_longitude):
        raise VenueError(
            "Thông tin vị trí chưa đầy đủ. Vui lòng đặt và xác nhận lại ghim."
        )
    if not raw_latitude:
        return None
    try:
        normalized_latitude = Decimal(raw_latitude)
        normalized_longitude = Decimal(raw_longitude)
        if (
            not normalized_latitude.is_finite()
            or not normalized_longitude.is_finite()
            or not Decimal("-90") <= normalized_latitude <= Decimal("90")
            or not Decimal("-180") <= normalized_longitude <= Decimal("180")
        ):
            raise VenueError(
                "Vị trí đã chọn không hợp lệ. Vui lòng đặt lại ghim trên bản đồ."
            )
        return (
            normalized_latitude.quantize(Decimal("0.000001")),
            normalized_longitude.quantize(Decimal("0.000001")),
        )
    except (InvalidOperation, ValueError) as exc:
        raise VenueError(
            "Vị trí đã chọn không hợp lệ. Vui lòng đặt lại ghim trên bản đồ."
        ) from exc


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
    allowed_transitions = {
        VenueStatus.PENDING.value: {
            VenueStatus.ACTIVE.value,
            VenueStatus.HIDDEN.value,
        },
        VenueStatus.ACTIVE.value: {VenueStatus.HIDDEN.value},
        VenueStatus.HIDDEN.value: {VenueStatus.ACTIVE.value},
    }
    if decision not in allowed_transitions.get(venue.status, set()):
        raise InvalidVenueStateError(
            "Không thể thực hiện chuyển trạng thái kiểm duyệt này."
        )
    venue.status = decision
    venue.reviewed_by = reviewer.id
    venue.reviewed_at = utc_now()
    venue.moderation_note = (moderation_note or "").strip() or None

    _commit_or_raise(
        "Không thể lưu kết quả kiểm duyệt lúc này. Vui lòng thử lại."
    )
    return venue


def _commit_or_raise(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise VenueError(message) from exc
