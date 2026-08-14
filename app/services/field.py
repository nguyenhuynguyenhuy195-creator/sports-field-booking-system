from __future__ import annotations

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Booking,
    Field,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    PriceSlotStatus,
    User,
    UserRole,
    Venue,
)
from app.services.auth import normalize_full_name
from app.services.sport_catalog import SportCatalogError, get_active_field_type


class FieldError(ValueError):
    """Base error for field business rules."""


class FieldNotFoundError(FieldError):
    """Raised when a field or its parent venue does not exist."""


class FieldPermissionError(FieldError):
    """Raised when an owner manages a field outside their venues."""


class DuplicateFieldNameError(FieldError):
    """Raised when a venue already has a field with the same name."""


class ImmutableFieldTypeError(FieldError):
    """Raised when changing the catalog type would corrupt booking history."""


def list_owner_fields(*, venue_id: int, owner_id: int) -> tuple[Venue, list[Field]]:
    venue = _get_owned_venue(venue_id=venue_id, owner_id=owner_id)
    fields = list(
        db.session.scalars(
            db.select(Field)
            .options(joinedload(Field.field_type).joinedload(FieldType.sport))
            .where(Field.venue_id == venue_id)
            .order_by(Field.created_at.desc())
        )
    )
    return venue, fields


def list_public_fields(venue_id: int) -> list[Field]:
    return list(
        db.session.scalars(
            db.select(Field)
            .options(
                joinedload(Field.field_type).joinedload(FieldType.sport),
                selectinload(
                    Field.price_slots.and_(
                        FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value
                    )
                )
            )
            .where(
                Field.venue_id == venue_id,
                Field.status == FieldStatus.ACTIVE.value,
            )
            .order_by(Field.name.asc())
        )
    )


def get_owner_field(*, field_id: int, owner_id: int) -> Field:
    field = db.session.scalar(
        db.select(Field)
        .options(
            joinedload(Field.venue),
            joinedload(Field.field_type).joinedload(FieldType.sport),
        )
        .where(Field.id == field_id)
    )
    if field is None:
        raise FieldNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner_id:
        raise FieldPermissionError("Bạn không có quyền quản lý sân này.")
    return field


def create_field(
    *,
    owner: User,
    venue_id: int,
    name: str,
    field_type: str,
    surface_type: str | None,
    capacity: int,
) -> Field:
    _validate_owner(owner)
    normalized_name = normalize_full_name(name)
    normalized_surface = _normalize_optional_text(surface_type)
    _validate_field_data(name=normalized_name, capacity=capacity)
    try:
        catalog_type = get_active_field_type(field_type)
    except SportCatalogError as exc:
        raise FieldError(str(exc)) from exc

    venue = _get_owned_venue(
        venue_id=venue_id,
        owner_id=owner.id,
        lock=True,
    )
    if _field_name_exists(venue_id=venue.id, name=normalized_name):
        raise DuplicateFieldNameError(
            "Cơ sở này đã có một sân cùng tên."
        )

    field = Field(
        venue_id=venue.id,
        name=normalized_name,
        field_type_id=catalog_type.id,
        surface_type=normalized_surface,
        capacity=capacity,
        status=FieldStatus.INACTIVE.value,
    )
    db.session.add(field)
    _commit_field("Không thể tạo sân lúc này. Vui lòng thử lại.")
    return field


def update_field(
    *,
    field_id: int,
    owner: User,
    name: str,
    field_type: str,
    surface_type: str | None,
    capacity: int,
) -> Field:
    _validate_owner(owner)
    normalized_name = normalize_full_name(name)
    normalized_surface = _normalize_optional_text(surface_type)
    _validate_field_data(name=normalized_name, capacity=capacity)
    try:
        catalog_type = get_active_field_type(field_type)
    except SportCatalogError as exc:
        raise FieldError(str(exc)) from exc

    field = db.session.scalar(
        db.select(Field)
        .options(
            joinedload(Field.venue),
            joinedload(Field.field_type).joinedload(FieldType.sport),
        )
        .where(Field.id == field_id)
        .with_for_update()
    )
    if field is None:
        raise FieldNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner.id:
        raise FieldPermissionError("Bạn không có quyền quản lý sân này.")
    if _field_name_exists(
        venue_id=field.venue_id,
        name=normalized_name,
        exclude_field_id=field.id,
    ):
        raise DuplicateFieldNameError(
            "Cơ sở này đã có một sân cùng tên."
        )

    if field.field_type_id != catalog_type.id:
        has_booking_history = db.session.scalar(
            db.select(Booking.id).where(Booking.field_id == field.id).limit(1)
        )
        if has_booking_history is not None:
            raise ImmutableFieldTypeError(
                "Không thể đổi loại sân vì sân đã có lịch sử đặt. "
                "Hãy ngừng sân cũ và tạo một sân mới."
            )

    field.name = normalized_name
    field.field_type_id = catalog_type.id
    field.surface_type = normalized_surface
    field.capacity = capacity
    _commit_field("Không thể cập nhật sân lúc này. Vui lòng thử lại.")
    return field


def _get_owned_venue(
    *,
    venue_id: int,
    owner_id: int,
    lock: bool = False,
) -> Venue:
    statement = db.select(Venue).where(Venue.id == venue_id)
    if lock:
        statement = statement.with_for_update()
    venue = db.session.scalar(statement)
    if venue is None:
        raise FieldNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise FieldPermissionError("Bạn không có quyền quản lý cơ sở này.")
    return venue


def _field_name_exists(
    *,
    venue_id: int,
    name: str,
    exclude_field_id: int | None = None,
) -> bool:
    statement = db.select(Field.id).where(
        Field.venue_id == venue_id,
        db.func.lower(Field.name) == name.lower(),
    )
    if exclude_field_id is not None:
        statement = statement.where(Field.id != exclude_field_id)
    return db.session.scalar(statement) is not None


def _validate_owner(owner: User) -> None:
    if owner.role != UserRole.OWNER.value:
        raise FieldPermissionError("Chỉ chủ sân được quản lý sân con.")


def _validate_field_data(*, name: str, capacity: int) -> None:
    if not name:
        raise FieldError("Vui lòng nhập tên sân.")
    if capacity < 1:
        raise FieldError("Sức chứa phải lớn hơn 0.")


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    return normalized or None


def _commit_field(message: str) -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateFieldNameError(
            "Cơ sở này đã có một sân cùng tên."
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise FieldError(message) from exc
