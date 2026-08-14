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
    from .booking_contribution import BookingContribution
    from .refund import Refund
    from .user import User


class PaymentProvider(str, Enum):
    MOCK = "MOCK"
    MOMO = "MOMO"


class PaymentMethod(str, Enum):
    SIMULATED = "SIMULATED"
    MOMO_WALLET = "MOMO_WALLET"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        db.CheckConstraint(
            "provider IN ('MOCK', 'MOMO')",
            name="ck_payments_provider",
        ),
        db.CheckConstraint(
            "payment_method IN ('SIMULATED', 'MOMO_WALLET')",
            name="ck_payments_method",
        ),
        db.CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="ck_payments_status",
        ),
        db.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        db.Index("ix_payments_booking_created", "booking_id", "created_at"),
        db.Index(
            "uq_payments_provider_trans_id_not_null",
            "provider_trans_id",
            unique=True,
            mssql_where=db.text("provider_trans_id IS NOT NULL"),
            sqlite_where=db.text("provider_trans_id IS NOT NULL"),
        ),
        db.Index(
            "uq_payments_success_contribution",
            "contribution_id",
            unique=True,
            mssql_where=db.text("status = 'SUCCESS'"),
            sqlite_where=db.text("status = 'SUCCESS'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        db.ForeignKey("bookings.id"),
        nullable=False,
    )
    contribution_id: Mapped[int] = mapped_column(
        db.ForeignKey("booking_contributions.id"),
        nullable=False,
    )
    payer_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(db.String(20), nullable=False)
    payment_method: Mapped[str] = mapped_column(db.String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
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
    provider_trans_id: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(db.String(20), nullable=False)
    result_code: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(
        db.Unicode(2000),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(timestamp_type, nullable=True)
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

    booking: Mapped[Booking] = relationship(back_populates="payments")
    contribution: Mapped[BookingContribution] = relationship(
        back_populates="payments"
    )
    payer: Mapped[User] = relationship(foreign_keys=[payer_id])
    refunds: Mapped[list[Refund]] = relationship(
        back_populates="payment",
        order_by="Refund.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id!r} order_id={self.order_id!r} "
            f"status={self.status!r}>"
        )
