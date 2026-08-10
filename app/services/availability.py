from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

from sqlalchemy import and_, or_

from app.extensions import db
from app.models import (
    Booking,
    BookingStatus,
    Field,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldPriceSlot,
    PriceSlotStatus,
)


VIETNAM_TIMEZONE = timezone(timedelta(hours=7))
AVAILABILITY_STEP_MINUTES = 30
MINIMUM_BOOKING_MINUTES = 60


class AvailabilitySlotStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    MAINTENANCE = "MAINTENANCE"
    NO_PRICE = "NO_PRICE"
    PAST = "PAST"


@dataclass(frozen=True)
class AvailabilitySlot:
    start_time: time
    end_time: time
    status: AvailabilitySlotStatus


@dataclass(frozen=True)
class FieldAvailability:
    booking_date: date
    opening_time: time
    closing_time: time
    slots: tuple[AvailabilitySlot, ...]


def build_field_availability(
    *,
    field: Field,
    booking_date: date,
    now: datetime | None = None,
) -> FieldAvailability:
    """Return selectable 30-minute intervals for one field and local date."""
    current_local = _normalize_local_datetime(now)
    current_utc = current_local.astimezone(timezone.utc).replace(tzinfo=None)
    opening_minutes = _time_to_minutes(field.venue.opening_time)
    if field.venue.opening_time.second or field.venue.opening_time.microsecond:
        opening_minutes += 1
    opening_minutes = _ceil_to_step(opening_minutes)
    closing_minutes = _floor_to_step(_time_to_minutes(field.venue.closing_time))

    price_slots = list(
        db.session.scalars(
            db.select(FieldPriceSlot)
            .where(
                FieldPriceSlot.field_id == field.id,
                FieldPriceSlot.day_of_week == booking_date.weekday(),
                FieldPriceSlot.status == PriceSlotStatus.ACTIVE.value,
            )
            .order_by(FieldPriceSlot.start_time.asc())
        )
    )
    maintenances = list(
        db.session.scalars(
            db.select(FieldMaintenance).where(
                FieldMaintenance.field_id == field.id,
                FieldMaintenance.maintenance_date == booking_date,
                FieldMaintenance.status == FieldMaintenanceStatus.ACTIVE.value,
            )
        )
    )
    bookings = list(
        db.session.scalars(
            db.select(Booking).where(
                Booking.field_id == field.id,
                Booking.booking_date == booking_date,
                or_(
                    Booking.status.in_(
                        (
                            BookingStatus.PARTIALLY_PAID.value,
                            BookingStatus.PAID.value,
                            BookingStatus.REFUND_PENDING.value,
                        )
                    ),
                    and_(
                        Booking.status == BookingStatus.CONFIRMED.value,
                        or_(
                            Booking.initial_payment_due_at.is_(None),
                            Booking.initial_payment_due_at > current_utc,
                        ),
                    ),
                ),
            )
        )
    )

    slots: list[AvailabilitySlot] = []
    cursor = opening_minutes
    while cursor + AVAILABILITY_STEP_MINUTES <= closing_minutes:
        slot_start = _minutes_to_time(cursor)
        slot_end = _minutes_to_time(cursor + AVAILABILITY_STEP_MINUTES)
        start_at = datetime.combine(booking_date, slot_start)

        if start_at <= current_local:
            status = AvailabilitySlotStatus.PAST
        elif _overlaps(bookings, slot_start, slot_end):
            status = AvailabilitySlotStatus.BOOKED
        elif _overlaps(maintenances, slot_start, slot_end):
            status = AvailabilitySlotStatus.MAINTENANCE
        elif not _has_price_coverage(price_slots, slot_start, slot_end):
            status = AvailabilitySlotStatus.NO_PRICE
        else:
            status = AvailabilitySlotStatus.AVAILABLE

        slots.append(
            AvailabilitySlot(
                start_time=slot_start,
                end_time=slot_end,
                status=status,
            )
        )
        cursor += AVAILABILITY_STEP_MINUTES

    return FieldAvailability(
        booking_date=booking_date,
        opening_time=field.venue.opening_time,
        closing_time=field.venue.closing_time,
        slots=tuple(slots),
    )


def _normalize_local_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(VIETNAM_TIMEZONE).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)
    return value


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _ceil_to_step(minutes: int) -> int:
    step = AVAILABILITY_STEP_MINUTES
    return ((minutes + step - 1) // step) * step


def _floor_to_step(minutes: int) -> int:
    step = AVAILABILITY_STEP_MINUTES
    return (minutes // step) * step


def _minutes_to_time(minutes: int) -> time:
    return time(hour=minutes // 60, minute=minutes % 60)


def _overlaps(records, start_time: time, end_time: time) -> bool:
    return any(
        record.start_time < end_time and record.end_time > start_time
        for record in records
    )


def _has_price_coverage(
    price_slots: list[FieldPriceSlot],
    start_time: time,
    end_time: time,
) -> bool:
    cursor = start_time
    for price_slot in price_slots:
        if price_slot.end_time <= cursor:
            continue
        if price_slot.start_time > cursor:
            return False
        cursor = min(price_slot.end_time, end_time)
        if cursor >= end_time:
            return True
    return False
