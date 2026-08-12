from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from math import ceil

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

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
from app.models.user import utc_now
from app.services.auth import normalize_full_name, normalize_phone


class VenueError(ValueError):
    """Base error for venue business rules."""


class VenueNotFoundError(VenueError):
    """Raised when a venue id does not exist or is not publicly visible."""


class VenuePermissionError(VenueError):
    """Raised when an owner tries to manage another owner's venue."""


class InvalidVenueStateError(VenueError):
    """Raised when a moderation transition would not change the venue."""


@dataclass(frozen=True)
class PublicVenueSearchResult:
    venue: Venue
    starting_price: Decimal | None
    field_types: tuple[str, ...]


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
    field_type: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    page: int = 1,
    per_page: int = 9,
) -> PublicVenueSearchPage:
    """Return bookable public venues matching the validated search filters."""
    normalized_query = " ".join((query or "").split())
    normalized_field_type = (field_type or "").strip() or None
    valid_field_types = {item.value for item in FieldType}

    if normalized_field_type not in valid_field_types | {None}:
        raise VenueError("Loại sân cần lọc không hợp lệ.")
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
    if normalized_field_type:
        active_field_conditions.append(
            Field.field_type == normalized_field_type
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

    ordered_statement = statement.order_by(Venue.name.asc())
    total = db.session.scalar(
        db.select(db.func.count()).select_from(statement.subquery())
    ) or 0
    total_pages = ceil(total / per_page) if total else 0
    if total_pages and page > total_pages:
        page = total_pages

    rows = db.session.execute(
        ordered_statement.limit(per_page).offset((page - 1) * per_page)
    ).all()
    if not rows:
        return PublicVenueSearchPage(
            items=(),
            page=page,
            per_page=per_page,
            total=total,
        )

    venue_ids = [venue.id for venue, _ in rows]
    field_type_rows = db.session.execute(
        db.select(Field.venue_id, Field.field_type)
        .where(
            Field.venue_id.in_(venue_ids),
            Field.status == FieldStatus.ACTIVE.value,
        )
        .distinct()
    ).all()
    types_by_venue: dict[int, list[str]] = {}
    for venue_id, active_field_type in field_type_rows:
        types_by_venue.setdefault(venue_id, []).append(active_field_type)

    field_type_order = {
        FieldType.FIVE_A_SIDE.value: 0,
        FieldType.SEVEN_A_SIDE.value: 1,
        FieldType.ELEVEN_A_SIDE.value: 2,
    }
    return PublicVenueSearchPage(
        items=tuple(
            PublicVenueSearchResult(
                venue=venue,
                starting_price=price,
                field_types=tuple(
                    sorted(
                        types_by_venue.get(venue.id, []),
                        key=field_type_order.get,
                    )
                ),
            )
            for venue, price in rows
        ),
        page=page,
        per_page=per_page,
        total=total,
    )


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
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được tạo cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)

    venue = Venue(
        owner_id=owner.id,
        name=_normalize_required_text(name),
        address=_normalize_required_text(address),
        district=_normalize_optional_text(district),
        city=_normalize_required_text(city),
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
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được sửa cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)

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
