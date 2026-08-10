from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .booking import Booking
    from .payment import Payment
    from .user import User


class ContributionType(str, Enum):
    CREATOR = "CREATOR"
    OPPONENT = "OPPONENT"
    PLAYER = "PLAYER"
    TOP_UP = "TOP_UP"


class ContributionStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    WAIVED = "WAIVED"
    REFUND_PENDING = "REFUND_PENDING"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    FORFEITED = "FORFEITED"


class BookingContribution(db.Model):
    __tablename__ = "booking_contributions"
    __table_args__ = (
        db.CheckConstraint(
            "contribution_type IN ('CREATOR', 'OPPONENT', 'PLAYER', 'TOP_UP')",
            name="ck_booking_contributions_type",
        ),
        db.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'EXPIRED', 'WAIVED', "
            "'REFUND_PENDING', 'PARTIALLY_REFUNDED', 'REFUNDED', 'FORFEITED')",
            name="ck_booking_contributions_status",
        ),
        db.CheckConstraint(
            "amount_due >= 0",
            name="ck_booking_contributions_amount_due_non_negative",
        ),
        db.CheckConstraint(
            "amount_paid >= 0 AND amount_paid <= amount_due",
            name="ck_booking_contributions_amount_paid_range",
        ),
        db.CheckConstraint(
            "((contribution_type IN ('CREATOR', 'TOP_UP') AND slot_number IS NULL) "
            "OR (contribution_type IN ('OPPONENT', 'PLAYER') "
            "AND slot_number IS NOT NULL AND slot_number > 0))",
            name="ck_booking_contributions_slot_number",
        ),
        db.Index(
            "ix_booking_contributions_booking_status",
            "booking_id",
            "status",
        ),
        db.Index(
            "uq_booking_contributions_external_slot",
            "booking_id",
            "contribution_type",
            "slot_number",
            unique=True,
            mssql_where=db.text("slot_number IS NOT NULL"),
            sqlite_where=db.text("slot_number IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        db.ForeignKey("bookings.id"),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=True,
    )
    contribution_type: Mapped[str] = mapped_column(db.String(30), nullable=False)
    slot_number: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    amount_due: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        db.String(30),
        nullable=False,
        default=ContributionStatus.PENDING.value,
        server_default=ContributionStatus.PENDING.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(timestamp_type, nullable=True)
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

    booking: Mapped[Booking] = relationship(back_populates="contributions")
    user: Mapped[User | None] = relationship(foreign_keys=[user_id])
    payments: Mapped[list[Payment]] = relationship(
        back_populates="contribution",
        order_by="Payment.created_at",
    )

    @property
    def remaining_amount(self) -> Decimal:
        return Decimal(self.amount_due) - Decimal(self.amount_paid)

    def __repr__(self) -> str:
        return (
            f"<BookingContribution id={self.id!r} booking_id={self.booking_id!r} "
            f"type={self.contribution_type!r} status={self.status!r}>"
        )
