from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Field,
    FieldPriceSlot,
    FieldStatus,
    PriceSlotStatus,
    User,
    UserRole,
)


class PricingError(ValueError):
    """Base error for price-slot business rules."""


class PricingNotFoundError(PricingError):
    """Raised when a field or price slot does not exist."""


class PricingPermissionError(PricingError):
    """Raised when an owner manages pricing outside their venues."""


class OverlappingPriceSlotError(PricingError):
    """Raised when active price slots overlap for the same field and day."""


class MissingActivePriceSlotError(PricingError):
    """Raised when a field is activated without an active price slot."""


class MissingPriceCoverageError(PricingError):
    """Raised when a requested interval is not fully covered by prices."""

    def __init__(self, start_time: time, end_time: time) -> None:
        self.start_time = start_time
        self.end_time = end_time
        super().__init__(
            "Chưa có khung giá cho khoảng "
            f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}."
        )


@dataclass(frozen=True)
class PriceSegment:
    price_slot_id: int
    start_time: time
    end_time: time
    duration_minutes: int
    hourly_price: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class PriceQuote:
    segments: tuple[PriceSegment, ...]
    total: Decimal


MONEY_QUANTUM = Decimal("0.01")


def list_owner_price_slots(
    *,
    field_id: int,
    owner_id: int,
) -> tuple[Field, list[FieldPriceSlot]]:
    field = _get_owned_field(field_id=field_id, owner_id=owner_id)
    slots = list(
        db.session.scalars(
            db.select(FieldPriceSlot)
            .where(FieldPriceSlot.field_id == field_id)
            .order_by(
                FieldPriceSlot.day_of_week.asc(),
                FieldPriceSlot.start_time.asc(),
            )
        )
    )
    return field, slots


def get_owner_price_slot(*, slot_id: int, owner_id: int) -> FieldPriceSlot:
    slot = db.session.scalar(
        db.select(FieldPriceSlot)
        .options(joinedload(FieldPriceSlot.field).joinedload(Field.venue))
        .where(FieldPriceSlot.id == slot_id)
    )
    if slot is None:
        raise PricingNotFoundError("Không tìm thấy khung giá.")
    if slot.field.venue.owner_id != owner_id:
        raise PricingPermissionError(
            "Bạn không có quyền quản lý khung giá của sân này."
        )
    return slot


def create_price_slot(
    *,
    owner: User,
    field_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    hourly_price: Decimal,
) -> FieldPriceSlot:
    _validate_owner(owner)
    normalized_price = _validate_price_slot_data(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        hourly_price=hourly_price,
    )
    field = _get_owned_field(
        field_id=field_id,
        owner_id=owner.id,
        lock=True,
    )
    _validate_within_operating_hours(
        field=field,
        start_time=start_time,
        end_time=end_time,
    )
    if _active_overlap_exists(
        field_id=field.id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    ):
        raise OverlappingPriceSlotError(
            "Khung giờ này bị chồng với một khung giá đang hoạt động."
        )

    slot = FieldPriceSlot(
        field_id=field.id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        hourly_price=normalized_price,
        status=PriceSlotStatus.ACTIVE.value,
    )
    db.session.add(slot)
    _commit_pricing("Không thể tạo khung giá lúc này. Vui lòng thử lại.")
    return slot


def update_price_slot(
    *,
    slot_id: int,
    owner: User,
    day_of_week: int,
    start_time: time,
    end_time: time,
    hourly_price: Decimal,
) -> FieldPriceSlot:
    _validate_owner(owner)
    normalized_price = _validate_price_slot_data(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        hourly_price=hourly_price,
    )
    slot = db.session.get(FieldPriceSlot, slot_id)
    if slot is None:
        raise PricingNotFoundError("Không tìm thấy khung giá.")
    field = _get_owned_field(
        field_id=slot.field_id,
        owner_id=owner.id,
        lock=True,
    )
    _validate_within_operating_hours(
        field=field,
        start_time=start_time,
        end_time=end_time,
    )
    slot = db.session.scalar(
        db.select(FieldPriceSlot)
        .where(FieldPriceSlot.id == slot_id)
        .with_for_update()
    )
    if slot is None:
        raise PricingNotFoundError("Không tìm thấy khung giá.")
    if (
        slot.status == PriceSlotStatus.ACTIVE.value
        and _active_overlap_exists(
            field_id=slot.field_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            exclude_slot_id=slot.id,
        )
    ):
        raise OverlappingPriceSlotError(
            "Khung giờ này bị chồng với một khung giá đang hoạt động."
        )

    slot.day_of_week = day_of_week
    slot.start_time = start_time
    slot.end_time = end_time
    slot.hourly_price = normalized_price
    _commit_pricing("Không thể cập nhật khung giá lúc này. Vui lòng thử lại.")
    return slot


def set_price_slot_status(
    *,
    slot_id: int,
    owner: User,
    status: str,
) -> FieldPriceSlot:
    _validate_owner(owner)
    if status not in {item.value for item in PriceSlotStatus}:
        raise PricingError("Trạng thái khung giá không hợp lệ.")

    slot = db.session.get(FieldPriceSlot, slot_id)
    if slot is None:
        raise PricingNotFoundError("Không tìm thấy khung giá.")
    field = _get_owned_field(
        field_id=slot.field_id,
        owner_id=owner.id,
        lock=True,
    )
    slot = db.session.scalar(
        db.select(FieldPriceSlot)
        .where(FieldPriceSlot.id == slot_id)
        .with_for_update()
    )
    if slot is None:
        raise PricingNotFoundError("Không tìm thấy khung giá.")

    if status == PriceSlotStatus.ACTIVE.value and _active_overlap_exists(
        field_id=slot.field_id,
        day_of_week=slot.day_of_week,
        start_time=slot.start_time,
        end_time=slot.end_time,
        exclude_slot_id=slot.id,
    ):
        raise OverlappingPriceSlotError(
            "Không thể bật vì khung giờ này chồng với khung giá đang hoạt động."
        )

    slot.status = status
    if (
        status == PriceSlotStatus.INACTIVE.value
        and field.status == FieldStatus.ACTIVE.value
        and not _has_active_slot(field_id=field.id, exclude_slot_id=slot.id)
    ):
        field.status = FieldStatus.INACTIVE.value

    _commit_pricing("Không thể đổi trạng thái khung giá lúc này.")
    return slot


def set_field_activation(
    *,
    field_id: int,
    owner: User,
    status: str,
) -> Field:
    _validate_owner(owner)
    if status not in {item.value for item in FieldStatus}:
        raise PricingError("Trạng thái sân không hợp lệ.")
    field = _get_owned_field(
        field_id=field_id,
        owner_id=owner.id,
        lock=True,
    )
    if (
        status == FieldStatus.ACTIVE.value
        and not _has_active_slot(field_id=field.id)
    ):
        raise MissingActivePriceSlotError(
            "Hãy tạo ít nhất một khung giá đang hoạt động trước khi bật sân."
        )

    field.status = status
    _commit_pricing("Không thể đổi trạng thái sân lúc này.")
    return field


def calculate_price_quote(
    *,
    field_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
) -> PriceQuote:
    _validate_interval(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    if db.session.get(Field, field_id) is None:
        raise PricingNotFoundError("Không tìm thấy sân.")

    slots = list(
        db.session.scalars(
            db.select(FieldPriceSlot)
            .where(
                FieldPriceSlot.field_id == field_id,
                FieldPriceSlot.day_of_week == day_of_week,
                FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value,
                FieldPriceSlot.start_time < end_time,
                FieldPriceSlot.end_time > start_time,
            )
            .order_by(FieldPriceSlot.start_time.asc())
        )
    )

    cursor = start_time
    segments: list[PriceSegment] = []
    for slot in slots:
        if slot.end_time <= cursor:
            continue
        if slot.start_time > cursor:
            raise MissingPriceCoverageError(cursor, min(slot.start_time, end_time))

        segment_end = min(slot.end_time, end_time)
        duration_minutes = _duration_minutes(cursor, segment_end)
        hourly_price = Decimal(slot.hourly_price).quantize(MONEY_QUANTUM)
        subtotal = (
            hourly_price * Decimal(duration_minutes) / Decimal(60)
        ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        segments.append(
            PriceSegment(
                price_slot_id=slot.id,
                start_time=cursor,
                end_time=segment_end,
                duration_minutes=duration_minutes,
                hourly_price=hourly_price,
                subtotal=subtotal,
            )
        )
        cursor = segment_end
        if cursor >= end_time:
            break

    if cursor < end_time:
        raise MissingPriceCoverageError(cursor, end_time)

    total = sum((segment.subtotal for segment in segments), Decimal("0.00"))
    return PriceQuote(segments=tuple(segments), total=total.quantize(MONEY_QUANTUM))


def _get_owned_field(
    *,
    field_id: int,
    owner_id: int,
    lock: bool = False,
) -> Field:
    statement = (
        db.select(Field)
        .options(joinedload(Field.venue))
        .where(Field.id == field_id)
    )
    if lock:
        statement = statement.with_for_update()
    field = db.session.scalar(statement)
    if field is None:
        raise PricingNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner_id:
        raise PricingPermissionError(
            "Bạn không có quyền quản lý khung giá của sân này."
        )
    return field


def _validate_owner(owner: User) -> None:
    if owner.role != UserRole.OWNER.value:
        raise PricingPermissionError("Chỉ chủ sân được cấu hình khung giá.")


def _validate_price_slot_data(
    *,
    day_of_week: int,
    start_time: time,
    end_time: time,
    hourly_price: Decimal,
) -> Decimal:
    _validate_interval(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    try:
        price = Decimal(str(hourly_price)).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PricingError("Giá theo giờ không hợp lệ.") from exc
    if price <= 0:
        raise PricingError("Giá theo giờ phải lớn hơn 0.")
    if price > Decimal("9999999999.99"):
        raise PricingError("Giá theo giờ vượt quá giới hạn cho phép.")
    return price


def _validate_interval(
    *,
    day_of_week: int,
    start_time: time,
    end_time: time,
) -> None:
    if day_of_week not in range(7):
        raise PricingError("Ngày áp dụng không hợp lệ.")
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise PricingError("Khoảng giờ không hợp lệ.")
    if start_time >= end_time:
        raise PricingError("Giờ kết thúc phải sau giờ bắt đầu.")


def _validate_within_operating_hours(
    *,
    field: Field,
    start_time: time,
    end_time: time,
) -> None:
    if (
        start_time < field.venue.opening_time
        or end_time > field.venue.closing_time
    ):
        raise PricingError(
            "Khung giá phải nằm trong giờ hoạt động của cơ sở "
            f"({field.venue.opening_time.strftime('%H:%M')}–"
            f"{field.venue.closing_time.strftime('%H:%M')})."
        )


def _active_overlap_exists(
    *,
    field_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    exclude_slot_id: int | None = None,
) -> bool:
    statement = db.select(FieldPriceSlot.id).where(
        FieldPriceSlot.field_id == field_id,
        FieldPriceSlot.day_of_week == day_of_week,
        FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value,
        FieldPriceSlot.start_time < end_time,
        FieldPriceSlot.end_time > start_time,
    )
    if exclude_slot_id is not None:
        statement = statement.where(FieldPriceSlot.id != exclude_slot_id)
    return db.session.scalar(statement) is not None


def _has_active_slot(
    *,
    field_id: int,
    exclude_slot_id: int | None = None,
) -> bool:
    statement = db.select(FieldPriceSlot.id).where(
        FieldPriceSlot.field_id == field_id,
        FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value,
    )
    if exclude_slot_id is not None:
        statement = statement.where(FieldPriceSlot.id != exclude_slot_id)
    return db.session.scalar(statement) is not None


def _duration_minutes(start_time: time, end_time: time) -> int:
    start = datetime.combine(date.min, start_time)
    end = datetime.combine(date.min, end_time)
    return int((end - start).total_seconds() // 60)


def _commit_pricing(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise PricingError(message) from exc
