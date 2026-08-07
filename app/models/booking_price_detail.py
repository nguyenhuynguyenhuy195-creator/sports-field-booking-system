from __future__ import annotations

from datetime import time
from decimal import Decimal

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .booking import Booking
from .price_slot import FieldPriceSlot
from .venue import time_type


class BookingPriceDetail(db.Model):
    __tablename__ = "booking_price_details"
    __table_args__ = (
        db.CheckConstraint(
            "start_time < end_time",
            name="ck_booking_price_details_start_before_end",
        ),
        db.CheckConstraint(
            "duration_minutes > 0",
            name="ck_booking_price_details_duration_positive",
        ),
        db.CheckConstraint(
            "hourly_price > 0",
            name="ck_booking_price_details_hourly_price_positive",
        ),
        db.CheckConstraint(
            "subtotal > 0",
            name="ck_booking_price_details_subtotal_positive",
        ),
        db.Index(
            "ix_booking_price_details_booking_time",
            "booking_id",
            "start_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        db.ForeignKey("bookings.id"),
        nullable=False,
    )
    price_slot_id: Mapped[int] = mapped_column(
        db.ForeignKey("field_price_slots.id"),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(time_type, nullable=False)
    end_time: Mapped[time] = mapped_column(time_type, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False)
    hourly_price: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)

    booking: Mapped[Booking] = relationship(back_populates="price_details")
    price_slot: Mapped[FieldPriceSlot] = relationship()

    def __repr__(self) -> str:
        return (
            f"<BookingPriceDetail id={self.id!r} booking_id={self.booking_id!r} "
            f"start_time={self.start_time!r} end_time={self.end_time!r}>"
        )
