from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Booking,
    BookingStatus,
    Field,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldStatus,
    Venue,
    VenueStatus,
)

from .booking import get_effective_booking_status
from .maintenance import (
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
