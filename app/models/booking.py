from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .field import Field
from .user import User, timestamp_type, utc_now
from .venue import time_type

if TYPE_CHECKING:
    from .booking_contribution import BookingContribution
    from .match import Match
    from .payment import Payment
    from .refund import Refund


class BookingMode(str, Enum):
    DIRECT_BOOKING = "DIRECT_BOOKING"
    FIND_OPPONENT = "FIND_OPPONENT"
    FIND_PLAYERS = "FIND_PLAYERS"


class PlayFormat(str, Enum):
    SINGLES = "SINGLES"
    DOUBLES = "DOUBLES"


class BookingPaymentPolicy(str, Enum):
    LEGACY_FULL_ONLINE = "LEGACY_FULL_ONLINE"
    DEPOSIT_30 = "DEPOSIT_30"


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    REFUND_PENDING = "REFUND_PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


OCCUPYING_BOOKING_STATUSES = frozenset(
    {
        BookingStatus.CONFIRMED.value,
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
        BookingStatus.REFUND_PENDING.value,
    }
)


class Booking(db.Model):
    __tablename__ = "bookings"
    __table_args__ = (
        db.CheckConstraint(
            "booking_mode IN ('DIRECT_BOOKING', 'FIND_OPPONENT', 'FIND_PLAYERS')",
            name="ck_bookings_booking_mode",
        ),
        db.CheckConstraint(
            "play_format IS NULL OR play_format IN ('SINGLES', 'DOUBLES')",
            name="ck_bookings_play_format",
        ),
        db.CheckConstraint(
            "payment_policy IN ('LEGACY_FULL_ONLINE', 'DEPOSIT_30')",
            name="ck_bookings_payment_policy",
        ),
        db.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'PARTIALLY_PAID', 'PAID', "
            "'REFUND_PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED')",
            name="ck_bookings_status",
        ),
        db.CheckConstraint(
            "start_time < end_time",
            name="ck_bookings_start_before_end",
        ),
        db.CheckConstraint(
            "total_amount > 0",
            name="ck_bookings_total_amount_positive",
        ),
        db.CheckConstraint(
            "deposit_rate > 0 AND deposit_rate <= 1",
            name="ck_bookings_deposit_rate",
        ),
        db.CheckConstraint(
            "deposit_amount > 0 AND deposit_amount <= total_amount",
            name="ck_bookings_deposit_amount_range",
        ),
        db.CheckConstraint(
            "paid_amount >= 0 AND paid_amount <= deposit_amount",
            name="ck_bookings_paid_amount_range",
        ),
        db.CheckConstraint(
            "cancellation_fee_amount >= 0 "
            "AND cancellation_fee_amount <= paid_amount",
            name="ck_bookings_cancellation_fee_range",
        ),
        db.CheckConstraint(
            "((booking_mode = 'FIND_PLAYERS' "
            "AND requested_players IS NOT NULL AND requested_players > 0) "
            "OR (booking_mode <> 'FIND_PLAYERS' AND requested_players IS NULL))",
            name="ck_bookings_requested_players",
        ),
        db.Index(
            "ix_bookings_field_date_status_time",
            "field_id",
            "booking_date",
            "status",
            "start_time",
            "end_time",
        ),
        db.Index("ix_bookings_user_created", "user_id", "created_at"),
        db.Index(
            "ix_bookings_status_initial_payment_due",
            "status",
            "initial_payment_due_at",
        ),
        db.Index(
            "ix_bookings_status_funding_deadline",
            "status",
            "funding_deadline",
        ),
        db.Index(
            "ix_bookings_status_matchmaking_deadline",
            "status",
            "matchmaking_deadline",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_code: Mapped[str] = mapped_column(
        db.String(30),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    field_id: Mapped[int] = mapped_column(
        db.ForeignKey("fields.id"),
        nullable=False,
    )
    booking_date: Mapped[date] = mapped_column(db.Date, nullable=False)
    start_time: Mapped[time] = mapped_column(time_type, nullable=False)
    end_time: Mapped[time] = mapped_column(time_type, nullable=False)
    booking_mode: Mapped[str] = mapped_column(db.String(30), nullable=False)
    play_format: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    requested_players: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    payment_policy: Mapped[str] = mapped_column(db.String(30), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
    deposit_rate: Mapped[Decimal] = mapped_column(db.Numeric(5, 4), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    cancellation_fee_amount: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        db.String(30),
        nullable=False,
        default=BookingStatus.CONFIRMED.value,
        server_default=BookingStatus.PENDING.value,
    )
    initial_payment_due_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    funding_deadline: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    matchmaking_deadline: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(db.Unicode(500), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(
        db.Unicode(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
        onupdate=utc_now,
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    field: Mapped[Field] = relationship(back_populates="bookings")
    price_details: Mapped[list["BookingPriceDetail"]] = relationship(
        back_populates="booking",
        order_by="BookingPriceDetail.start_time",
    )
    contributions: Mapped[list[BookingContribution]] = relationship(
        back_populates="booking",
        order_by="BookingContribution.id",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="booking",
        order_by="Payment.created_at",
    )
    refunds: Mapped[list[Refund]] = relationship(
        back_populates="booking",
        order_by="Refund.created_at",
    )
    match: Mapped[Match | None] = relationship(
        back_populates="booking",
        uselist=False,
    )

    @property
    def remaining_amount(self) -> Decimal:
        return Decimal(self.deposit_amount) - Decimal(self.paid_amount)

    @property
    def balance_due_at_venue(self) -> Decimal:
        return Decimal(self.total_amount) - Decimal(self.paid_amount)

    @property
    def uses_deposit_policy(self) -> bool:
        return self.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value

    def __repr__(self) -> str:
        return (
            f"<Booking id={self.id!r} code={self.booking_code!r} "
            f"field_id={self.field_id!r} status={self.status!r}>"
        )
