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


class RefundStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Refund(db.Model):
    __tablename__ = "refunds"
    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
        db.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED')",
            name="ck_refunds_status",
        ),
        db.Index("ix_refunds_booking_created", "booking_id", "created_at"),
        db.Index(
            "uq_refunds_provider_trans_id_not_null",
            "provider_refund_trans_id",
            unique=True,
            mssql_where=db.text("provider_refund_trans_id IS NOT NULL"),
            sqlite_where=db.text("provider_refund_trans_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        db.ForeignKey("bookings.id"),
        nullable=False,
    )
    payment_id: Mapped[int] = mapped_column(
        db.ForeignKey("payments.id"),
        nullable=False,
    )
    recipient_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(db.Unicode(500), nullable=False)
    order_id: Mapped[str] = mapped_column(
        db.String(100),
        unique=True,
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(
        db.String(100),
        unique=True,
        nullable=False,
    )
    provider_refund_trans_id: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(db.String(30), nullable=False)
    result_code: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(timestamp_type, nullable=True)
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

    booking: Mapped[Booking] = relationship(back_populates="refunds")
    payment: Mapped[Payment] = relationship(back_populates="refunds")
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])

    def __repr__(self) -> str:
        return (
            f"<Refund id={self.id!r} order_id={self.order_id!r} "
            f"status={self.status!r}>"
        )
