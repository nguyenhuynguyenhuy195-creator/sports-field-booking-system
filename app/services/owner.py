from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Booking,
    BookingStatus,
    Field,
    FieldType,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldStatus,
    Venue,
    VenueStatus,
)

from .booking import get_effective_booking_status
from .maintenance import (
    VIETNAM_TIMEZONE,
    current_vietnam_datetime,
    get_effective_maintenance_status,
)


INACTIVE_DASHBOARD_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    }
)

SCHEDULE_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.CONFIRMED.value,
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
        BookingStatus.REFUND_PENDING.value,
        BookingStatus.COMPLETED.value,
    }
)

SCHEDULE_ALWAYS_OCCUPYING_STATUSES = frozenset(
    {
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
        BookingStatus.REFUND_PENDING.value,
    }
)


class OwnerScheduleError(ValueError):
    """Base error for Owner Schedule read-model validation."""


class OwnerScheduleNotFoundError(OwnerScheduleError):
    """Raised when a requested schedule resource does not exist."""


class OwnerSchedulePermissionError(OwnerScheduleError):
    """Raised when an owner requests another owner's schedule resource."""


@dataclass(frozen=True)
class OwnerDashboardBooking:
    booking: Booking
    effective_status: str
    start_at: datetime


@dataclass(frozen=True)
class OwnerDashboardSummary:
    generated_at: datetime
    today_booking_count: int
    upcoming_booking_count: int
    venue_count: int
    active_field_count: int
    pending_venue_count: int
    inactive_field_count: int
    current_maintenance_count: int
    upcoming_maintenance_count: int
    upcoming_bookings: tuple[OwnerDashboardBooking, ...]


@dataclass(frozen=True)
class OwnerScheduleGuide:
    label: str
    offset_minutes: int


@dataclass(frozen=True)
class OwnerScheduleBlock:
    kind: str
    field: Field
    start_time: time
    end_time: time
    effective_status: str
    is_historical: bool
    is_visible: bool
    offset_minutes: int
    duration_minutes: int
    booking: Booking | None = None
    maintenance: FieldMaintenance | None = None


@dataclass(frozen=True)
class OwnerScheduleColumn:
    field: Field
    blocks: tuple[OwnerScheduleBlock, ...]


@dataclass(frozen=True)
class OwnerScheduleSummary:
    generated_at: datetime
    schedule_date: date
    venues: tuple[Venue, ...]
    selected_venue: Venue | None
    fields: tuple[Field, ...]
    selected_field: Field | None
    field_filter_id: int | None
    columns: tuple[OwnerScheduleColumn, ...]
    list_entries: tuple[OwnerScheduleBlock, ...]
    guides: tuple[OwnerScheduleGuide, ...]
    grid_start: time | None
    grid_end: time | None
    grid_minutes: int


def get_owner_dashboard_summary(
    owner_id: int,
    *,
    now: datetime | None = None,
    upcoming_limit: int = 6,
) -> OwnerDashboardSummary:
    current_local = now or current_vietnam_datetime()
    today = current_local.date()

    owner_bookings = list(
        db.session.scalars(
            db.select(Booking)
            .join(Booking.field)
            .join(Field.venue)
            .options(
                joinedload(Booking.user),
                joinedload(Booking.field).joinedload(Field.venue),
            )
            .where(
                Venue.owner_id == owner_id,
                Booking.booking_date >= today,
            )
            .order_by(Booking.booking_date.asc(), Booking.start_time.asc())
        ).unique()
    )

    active_bookings: list[OwnerDashboardBooking] = []
    for booking in owner_bookings:
        effective_status = get_effective_booking_status(
            booking,
            now=current_local,
        )
        if effective_status in INACTIVE_DASHBOARD_BOOKING_STATUSES:
            continue
        active_bookings.append(
            OwnerDashboardBooking(
                booking=booking,
                effective_status=effective_status,
                start_at=datetime.combine(
                    booking.booking_date,
                    booking.start_time,
                ),
            )
        )

    today_booking_count = sum(
        entry.booking.booking_date == today for entry in active_bookings
    )
    upcoming_bookings = [
        entry for entry in active_bookings if entry.start_at > current_local
    ]

    owner_maintenances = list(
        db.session.scalars(
            db.select(FieldMaintenance)
            .join(FieldMaintenance.field)
            .join(Field.venue)
            .where(
                Venue.owner_id == owner_id,
                FieldMaintenance.maintenance_date >= today,
                FieldMaintenance.status == FieldMaintenanceStatus.ACTIVE.value,
            )
        )
    )
    current_maintenance_count = 0
    upcoming_maintenance_count = 0
    for maintenance in owner_maintenances:
        if (
            get_effective_maintenance_status(
                maintenance,
                now=current_local,
            )
            != FieldMaintenanceStatus.ACTIVE.value
        ):
            continue
        start_at = datetime.combine(
            maintenance.maintenance_date,
            maintenance.start_time,
        )
        if start_at <= current_local:
            current_maintenance_count += 1
        else:
            upcoming_maintenance_count += 1

    return OwnerDashboardSummary(
        generated_at=current_local,
        today_booking_count=today_booking_count,
        upcoming_booking_count=len(upcoming_bookings),
        venue_count=_count_owner_venues(owner_id=owner_id),
        active_field_count=_count_owner_fields(
            owner_id=owner_id,
            status=FieldStatus.ACTIVE.value,
        ),
        pending_venue_count=_count_owner_venues(
            owner_id=owner_id,
            status=VenueStatus.PENDING.value,
        ),
        inactive_field_count=_count_owner_fields(
            owner_id=owner_id,
            status=FieldStatus.INACTIVE.value,
        ),
        current_maintenance_count=current_maintenance_count,
        upcoming_maintenance_count=upcoming_maintenance_count,
        upcoming_bookings=tuple(upcoming_bookings[:upcoming_limit]),
    )


def get_owner_schedule_summary(
    owner_id: int,
    *,
    schedule_date: date,
    venue_id: int | None = None,
    field_id: int | None = None,
    now: datetime | None = None,
) -> OwnerScheduleSummary:
    """Build one venue's daily Owner Schedule with four batched reads."""
    current_local = _normalize_schedule_local_datetime(now)
    venues = tuple(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.name.asc(), Venue.id.asc())
        )
    )

    selected_venue = None
    if venue_id is not None:
        selected_venue = next(
            (venue for venue in venues if venue.id == venue_id),
            None,
        )
        if selected_venue is None:
            _raise_schedule_venue_access_error(
                owner_id=owner_id,
                venue_id=venue_id,
            )

    if selected_venue is None:
        return OwnerScheduleSummary(
            generated_at=current_local,
            schedule_date=schedule_date,
            venues=venues,
            selected_venue=None,
            fields=(),
            selected_field=None,
            field_filter_id=None,
            columns=(),
            list_entries=(),
            guides=(),
            grid_start=None,
            grid_end=None,
            grid_minutes=0,
        )

    fields = tuple(
        db.session.scalars(
            db.select(Field)
            .options(joinedload(Field.field_type).joinedload(FieldType.sport))
            .where(Field.venue_id == selected_venue.id)
            .order_by(Field.name.asc(), Field.id.asc())
        ).unique()
    )
    selected_field = fields[0] if fields else None
    if field_id is not None:
        selected_field = next(
            (field for field in fields if field.id == field_id),
            None,
        )
        if selected_field is None:
            _raise_schedule_field_access_error(
                owner_id=owner_id,
                venue_id=selected_venue.id,
                field_id=field_id,
            )

    field_ids = [field.id for field in fields]
    bookings: tuple[Booking, ...] = ()
    maintenances: tuple[FieldMaintenance, ...] = ()
    if field_ids:
        bookings = tuple(
            db.session.scalars(
                db.select(Booking)
                .options(joinedload(Booking.user))
                .where(
                    Booking.field_id.in_(field_ids),
                    Booking.booking_date == schedule_date,
                    Booking.status.in_(SCHEDULE_BOOKING_STATUSES),
                )
                .order_by(Booking.start_time.asc(), Booking.id.asc())
            ).unique()
        )
        maintenances = tuple(
            db.session.scalars(
                db.select(FieldMaintenance)
                .where(
                    FieldMaintenance.field_id.in_(field_ids),
                    FieldMaintenance.maintenance_date == schedule_date,
                    FieldMaintenance.status.in_(
                        (
                            FieldMaintenanceStatus.ACTIVE.value,
                            FieldMaintenanceStatus.COMPLETED.value,
                        )
                    ),
                )
                .order_by(FieldMaintenance.start_time.asc(), FieldMaintenance.id.asc())
            )
        )

    grid_start_minutes = _ceil_to_half_hour(
        _time_to_minutes(selected_venue.opening_time)
    )
    grid_end_minutes = _floor_to_half_hour(
        _time_to_minutes(selected_venue.closing_time)
    )
    if grid_end_minutes <= grid_start_minutes:
        grid_start_minutes = _time_to_minutes(selected_venue.opening_time)
        grid_end_minutes = _time_to_minutes(selected_venue.closing_time)

    booking_by_field: dict[int, list[Booking]] = {
        field.id: [] for field in fields
    }
    for booking in bookings:
        booking_by_field[booking.field_id].append(booking)
    maintenance_by_field: dict[int, list[FieldMaintenance]] = {
        field.id: [] for field in fields
    }
    for maintenance in maintenances:
        maintenance_by_field[maintenance.field_id].append(maintenance)

    current_utc = (
        current_local.replace(tzinfo=VIETNAM_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    columns: list[OwnerScheduleColumn] = []
    for field in fields:
        blocks: list[OwnerScheduleBlock] = []
        for booking in booking_by_field[field.id]:
            effective_status = get_effective_booking_status(
                booking,
                now=current_local,
            )
            is_historical = effective_status == BookingStatus.COMPLETED.value
            is_operational = _booking_is_schedule_occupancy(
                booking,
                now_utc=current_utc,
            )
            if not is_operational and not is_historical:
                continue
            block = _build_schedule_block(
                kind="booking",
                field=field,
                start_time=booking.start_time,
                end_time=booking.end_time,
                effective_status=effective_status,
                is_historical=is_historical,
                grid_start_minutes=grid_start_minutes,
                grid_end_minutes=grid_end_minutes,
                booking=booking,
            )
            blocks.append(block)

        for maintenance in maintenance_by_field[field.id]:
            effective_status = get_effective_maintenance_status(
                maintenance,
                now=current_local,
            )
            block = _build_schedule_block(
                kind="maintenance",
                field=field,
                start_time=maintenance.start_time,
                end_time=maintenance.end_time,
                effective_status=effective_status,
                is_historical=(
                    effective_status == FieldMaintenanceStatus.COMPLETED.value
                ),
                grid_start_minutes=grid_start_minutes,
                grid_end_minutes=grid_end_minutes,
                maintenance=maintenance,
            )
            blocks.append(block)

        columns.append(
            OwnerScheduleColumn(
                field=field,
                blocks=tuple(
                    sorted(
                        blocks,
                        key=lambda item: (
                            item.start_time,
                            item.end_time,
                            item.kind,
                        ),
                    )
                ),
            )
        )

    visible_columns = tuple(
        column
        for column in columns
        if field_id is None or column.field.id == field_id
    )
    list_entries = tuple(
        sorted(
            (
                block
                for column in visible_columns
                for block in column.blocks
            ),
            key=lambda item: (
                item.start_time,
                item.field.name.casefold(),
                item.kind,
            ),
        )
    )
    guides = tuple(
        OwnerScheduleGuide(
            label=_minutes_to_time(minutes).strftime("%H:%M"),
            offset_minutes=minutes - grid_start_minutes,
        )
        for minutes in range(
            grid_start_minutes,
            grid_end_minutes + 1,
            30,
        )
    )
    return OwnerScheduleSummary(
        generated_at=current_local,
        schedule_date=schedule_date,
        venues=venues,
        selected_venue=selected_venue,
        fields=fields,
        selected_field=selected_field,
        field_filter_id=field_id,
        columns=visible_columns,
        list_entries=list_entries,
        guides=guides,
        grid_start=_minutes_to_time(grid_start_minutes),
        grid_end=_minutes_to_time(grid_end_minutes),
        grid_minutes=grid_end_minutes - grid_start_minutes,
    )


def _booking_is_schedule_occupancy(
    booking: Booking,
    *,
    now_utc: datetime,
) -> bool:
    if booking.status in SCHEDULE_ALWAYS_OCCUPYING_STATUSES:
        return True
    return (
        booking.status == BookingStatus.CONFIRMED.value
        and (
            booking.initial_payment_due_at is None
            or booking.initial_payment_due_at > now_utc
        )
    )


def _build_schedule_block(
    *,
    kind: str,
    field: Field,
    start_time: time,
    end_time: time,
    effective_status: str,
    is_historical: bool,
    grid_start_minutes: int,
    grid_end_minutes: int,
    booking: Booking | None = None,
    maintenance: FieldMaintenance | None = None,
) -> OwnerScheduleBlock:
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    visible_start = max(start_minutes, grid_start_minutes)
    visible_end = min(end_minutes, grid_end_minutes)
    is_visible = visible_end > visible_start
    return OwnerScheduleBlock(
        kind=kind,
        field=field,
        start_time=start_time,
        end_time=end_time,
        effective_status=effective_status,
        is_historical=is_historical,
        is_visible=is_visible,
        offset_minutes=max(0, visible_start - grid_start_minutes),
        duration_minutes=max(0, visible_end - visible_start),
        booking=booking,
        maintenance=maintenance,
    )


def _raise_schedule_venue_access_error(*, owner_id: int, venue_id: int) -> None:
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        raise OwnerScheduleNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise OwnerSchedulePermissionError(
            "Bạn không có quyền xem lịch của cơ sở này."
        )


def _raise_schedule_field_access_error(
    *,
    owner_id: int,
    venue_id: int,
    field_id: int,
) -> None:
    field = db.session.scalar(
        db.select(Field).options(joinedload(Field.venue)).where(Field.id == field_id)
    )
    if field is None:
        raise OwnerScheduleNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner_id:
        raise OwnerSchedulePermissionError(
            "Bạn không có quyền xem lịch của sân này."
        )
    if field.venue_id != venue_id:
        raise OwnerScheduleNotFoundError("Sân không thuộc cơ sở đã chọn.")


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _normalize_schedule_local_datetime(value: datetime | None) -> datetime:
    if value is None:
        return current_vietnam_datetime()
    if value.tzinfo is not None:
        return value.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)
    return value


def _minutes_to_time(value: int) -> time:
    return time(hour=value // 60, minute=value % 60)


def _ceil_to_half_hour(value: int) -> int:
    return ((value + 29) // 30) * 30


def _floor_to_half_hour(value: int) -> int:
    return (value // 30) * 30


def _count_owner_venues(*, owner_id: int, status: str | None = None) -> int:
    statement = db.select(func.count(Venue.id)).where(Venue.owner_id == owner_id)
    if status is not None:
        statement = statement.where(Venue.status == status)
    return int(db.session.scalar(statement) or 0)


def _count_owner_fields(*, owner_id: int, status: str) -> int:
    return int(
        db.session.scalar(
            db.select(func.count(Field.id))
            .join(Field.venue)
            .where(
                Venue.owner_id == owner_id,
                Field.status == status,
            )
        )
        or 0
    )
