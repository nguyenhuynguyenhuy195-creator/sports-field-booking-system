from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Booking,
    BookingPaymentPolicy,
    BookingStatus,
    Field,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    Venue,
)

from .maintenance import VIETNAM_TIMEZONE


FINANCE_ACTIVITY_TYPES = frozenset({"PAYMENT", "REFUND"})
FINANCE_ACTIVITY_STATUSES = frozenset(
    {
        PaymentStatus.PENDING.value,
        PaymentStatus.SUCCESS.value,
        PaymentStatus.FAILED.value,
        PaymentStatus.CANCELLED.value,
        PaymentStatus.EXPIRED.value,
        RefundStatus.PROCESSING.value,
    }
)
FUNDED_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.PAID.value,
        BookingStatus.COMPLETED.value,
    }
)
UPCOMING_VENUE_PAYMENT_STATUSES = frozenset(
    {
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
    }
)


class OwnerFinanceError(ValueError):
    """Base error for Owner Finance read-model validation."""


class OwnerFinanceNotFoundError(OwnerFinanceError):
    """Raised when a requested finance filter resource does not exist."""


class OwnerFinancePermissionError(OwnerFinanceError):
    """Raised when an owner requests another owner's finance resource."""


@dataclass(frozen=True)
class OwnerFinanceActivity:
    activity_type: str
    booking: Booking
    payer_name: str
    provider: str
    status: str
    amount: Decimal
    occurred_at: datetime
    reference: str


@dataclass(frozen=True)
class OwnerFinanceSummary:
    venues: tuple[Venue, ...]
    fields: tuple[Field, ...]
    selected_venue: Venue | None
    selected_field: Field | None
    booking_value: Decimal
    funded_booking_count: int
    collected_online: Decimal
    successful_payment_count: int
    refunded_completed: Decimal
    successful_refund_count: int
    recorded_online_balance: Decimal
    expected_at_venue: Decimal
    pending_refund_amount: Decimal
    pending_refund_count: int
    activities: tuple[OwnerFinanceActivity, ...]
    settlement_supported: bool = False


def get_owner_finance_summary(
    owner_id: int,
    *,
    venue_id: int | None = None,
    field_id: int | None = None,
    activity_type: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OwnerFinanceSummary:
    """Build an Owner-scoped finance view without settlement assumptions.

    Venue/field scope applies to both metrics and history. Activity type, status,
    and date range apply only to history so a history filter cannot silently
    redefine the dashboard totals.
    """
    if activity_type is not None and activity_type not in FINANCE_ACTIVITY_TYPES:
        raise OwnerFinanceError("Loại hoạt động tài chính không hợp lệ.")
    if status is not None and status not in FINANCE_ACTIVITY_STATUSES:
        raise OwnerFinanceError("Trạng thái giao dịch không hợp lệ.")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise OwnerFinanceError("Khoảng ngày giao dịch không hợp lệ.")

    venues = tuple(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.name, Venue.id)
        )
    )
    fields = tuple(
        db.session.scalars(
            db.select(Field)
            .join(Field.venue)
            .options(joinedload(Field.venue))
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.name, Field.name, Field.id)
        )
    )
    selected_venue = _validate_venue_filter(owner_id=owner_id, venue_id=venue_id)
    selected_field = _validate_field_filter(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )

    booking_scope = _booking_scope_conditions(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )
    payment_scope = _payment_scope_conditions(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )
    refund_scope = _refund_scope_conditions(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )

    funded = db.session.execute(
        db.select(
            func.coalesce(func.sum(Booking.total_amount), 0),
            func.count(Booking.id),
        ).where(
            *booking_scope,
            Booking.status.in_(FUNDED_BOOKING_STATUSES),
        )
    ).one()
    expected_at_venue = db.session.scalar(
        db.select(
            func.coalesce(
                func.sum(Booking.total_amount - Booking.paid_amount),
                0,
            )
        ).where(
            *booking_scope,
            Booking.status.in_(UPCOMING_VENUE_PAYMENT_STATUSES),
            Booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value,
        )
    )
    payments = db.session.execute(
        db.select(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        ).where(
            *payment_scope,
            Payment.status == PaymentStatus.SUCCESS.value,
        )
    ).one()
    refunds = db.session.execute(
        db.select(
            func.coalesce(func.sum(Refund.amount), 0),
            func.count(Refund.id),
        ).where(
            *refund_scope,
            Refund.status == RefundStatus.SUCCESS.value,
        )
    ).one()
    pending_refunds = db.session.execute(
        db.select(
            func.coalesce(func.sum(Refund.amount), 0),
            func.count(Refund.id),
        ).where(
            *refund_scope,
            Refund.status.in_(
                (RefundStatus.PENDING.value, RefundStatus.PROCESSING.value)
            ),
        )
    ).one()
    recorded_online_balance = db.session.scalar(
        db.select(func.coalesce(func.sum(Booking.paid_amount), 0)).where(
            *booking_scope
        )
    )
    activities = _list_finance_activities(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
        activity_type=activity_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return OwnerFinanceSummary(
        venues=venues,
        fields=fields,
        selected_venue=selected_venue,
        selected_field=selected_field,
        booking_value=Decimal(funded[0]),
        funded_booking_count=int(funded[1] or 0),
        expected_at_venue=Decimal(expected_at_venue or 0),
        collected_online=Decimal(payments[0]),
        successful_payment_count=int(payments[1] or 0),
        refunded_completed=Decimal(refunds[0]),
        successful_refund_count=int(refunds[1] or 0),
        recorded_online_balance=Decimal(recorded_online_balance or 0),
        pending_refund_amount=Decimal(pending_refunds[0]),
        pending_refund_count=int(pending_refunds[1] or 0),
        activities=activities,
    )


def _list_finance_activities(
    *,
    owner_id: int,
    venue_id: int | None,
    field_id: int | None,
    activity_type: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[OwnerFinanceActivity, ...]:
    start_utc, end_utc = _utc_activity_range(date_from=date_from, date_to=date_to)
    activities: list[OwnerFinanceActivity] = []

    if activity_type in (None, "PAYMENT"):
        payment_time = func.coalesce(Payment.paid_at, Payment.created_at)
        statement = (
            db.select(Payment)
            .join(Payment.booking)
            .join(Booking.field)
            .join(Field.venue)
            .options(
                joinedload(Payment.payer),
                joinedload(Payment.booking).joinedload(Booking.user),
                joinedload(Payment.booking)
                .joinedload(Booking.field)
                .joinedload(Field.venue),
            )
            .where(
                *_payment_scope_conditions(
                    owner_id=owner_id,
                    venue_id=venue_id,
                    field_id=field_id,
                )
            )
        )
        if status is not None:
            statement = statement.where(Payment.status == status)
        if start_utc is not None:
            statement = statement.where(payment_time >= start_utc)
        if end_utc is not None:
            statement = statement.where(payment_time < end_utc)
        for payment in db.session.scalars(statement):
            activities.append(
                OwnerFinanceActivity(
                    activity_type="PAYMENT",
                    booking=payment.booking,
                    payer_name=payment.payer.full_name,
                    provider=payment.provider,
                    status=payment.status,
                    amount=Decimal(payment.amount),
                    occurred_at=_utc_to_vietnam(
                        payment.paid_at or payment.created_at
                    ),
                    reference=payment.order_id,
                )
            )

    if activity_type in (None, "REFUND"):
        refund_time = func.coalesce(Refund.refunded_at, Refund.created_at)
        statement = (
            db.select(Refund)
            .join(Refund.booking)
            .join(Booking.field)
            .join(Field.venue)
            .options(
                joinedload(Refund.recipient),
                joinedload(Refund.payment),
                joinedload(Refund.booking).joinedload(Booking.user),
                joinedload(Refund.booking)
                .joinedload(Booking.field)
                .joinedload(Field.venue),
            )
            .where(
                *_refund_scope_conditions(
                    owner_id=owner_id,
                    venue_id=venue_id,
                    field_id=field_id,
                )
            )
        )
        if status is not None:
            statement = statement.where(Refund.status == status)
        if start_utc is not None:
            statement = statement.where(refund_time >= start_utc)
        if end_utc is not None:
            statement = statement.where(refund_time < end_utc)
        for refund in db.session.scalars(statement):
            activities.append(
                OwnerFinanceActivity(
                    activity_type="REFUND",
                    booking=refund.booking,
                    payer_name=refund.recipient.full_name,
                    provider=refund.payment.provider,
                    status=refund.status,
                    amount=Decimal(refund.amount),
                    occurred_at=_utc_to_vietnam(
                        refund.refunded_at or refund.created_at
                    ),
                    reference=refund.order_id,
                )
            )

    activities.sort(
        key=lambda item: (item.occurred_at, item.reference),
        reverse=True,
    )
    return tuple(activities)


def _booking_scope_conditions(
    *, owner_id: int, venue_id: int | None, field_id: int | None
) -> tuple:
    conditions = [
        Booking.field_id == Field.id,
        Field.venue_id == Venue.id,
        Venue.owner_id == owner_id,
    ]
    if venue_id is not None:
        conditions.append(Venue.id == venue_id)
    if field_id is not None:
        conditions.append(Field.id == field_id)
    return tuple(conditions)


def _payment_scope_conditions(
    *, owner_id: int, venue_id: int | None, field_id: int | None
) -> tuple:
    return (Payment.booking_id == Booking.id,) + _booking_scope_conditions(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )


def _refund_scope_conditions(
    *, owner_id: int, venue_id: int | None, field_id: int | None
) -> tuple:
    return (Refund.booking_id == Booking.id,) + _booking_scope_conditions(
        owner_id=owner_id,
        venue_id=venue_id,
        field_id=field_id,
    )


def _validate_venue_filter(*, owner_id: int, venue_id: int | None) -> Venue | None:
    if venue_id is None:
        return None
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        raise OwnerFinanceNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise OwnerFinancePermissionError(
            "Bạn không có quyền xem tài chính của cơ sở này."
        )
    return venue


def _validate_field_filter(
    *, owner_id: int, venue_id: int | None, field_id: int | None
) -> Field | None:
    if field_id is None:
        return None
    field = db.session.scalar(
        db.select(Field).options(joinedload(Field.venue)).where(Field.id == field_id)
    )
    if field is None:
        raise OwnerFinanceNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner_id:
        raise OwnerFinancePermissionError(
            "Bạn không có quyền xem tài chính của sân này."
        )
    if venue_id is not None and field.venue_id != venue_id:
        raise OwnerFinanceNotFoundError("Sân không thuộc cơ sở đã chọn.")
    return field


def _utc_activity_range(
    *, date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    start = _local_midnight_to_utc(date_from) if date_from is not None else None
    end = (
        _local_midnight_to_utc(date_to + timedelta(days=1))
        if date_to is not None
        else None
    )
    return start, end


def _local_midnight_to_utc(value: date) -> datetime:
    return (
        datetime.combine(value, time.min)
        .replace(tzinfo=VIETNAM_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def _utc_to_vietnam(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)
    return value.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TIMEZONE).replace(
        tzinfo=None
    )
