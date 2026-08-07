from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from enum import Enum

from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .field import Field
from .user import timestamp_type, utc_now
from .venue import time_type


class PriceSlotStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


DAY_OF_WEEK_LABELS = {
    0: "Thứ Hai",
    1: "Thứ Ba",
    2: "Thứ Tư",
    3: "Thứ Năm",
    4: "Thứ Sáu",
    5: "Thứ Bảy",
    6: "Chủ Nhật",
}


day_of_week_type = db.SmallInteger().with_variant(mssql.TINYINT(), "mssql")


class FieldPriceSlot(db.Model):
    __tablename__ = "field_price_slots"
    __table_args__ = (
        db.CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_price_slots_day_of_week",
        ),
        db.CheckConstraint(
            "start_time < end_time",
            name="ck_price_slots_start_before_end",
        ),
        db.CheckConstraint(
            "hourly_price > 0",
            name="ck_price_slots_hourly_price_positive",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_price_slots_status",
        ),
        db.Index(
            "ix_price_slots_field_day_status_time",
            "field_id",
            "day_of_week",
            "status",
            "start_time",
            "end_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    field_id: Mapped[int] = mapped_column(
        db.ForeignKey("fields.id"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(day_of_week_type, nullable=False)
    start_time: Mapped[time] = mapped_column(time_type, nullable=False)
    end_time: Mapped[time] = mapped_column(time_type, nullable=False)
    hourly_price: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=PriceSlotStatus.ACTIVE.value,
        server_default=PriceSlotStatus.ACTIVE.value,
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

    field: Mapped[Field] = relationship(back_populates="price_slots")

    @property
    def is_active(self) -> bool:
        return self.status == PriceSlotStatus.ACTIVE.value

    def __repr__(self) -> str:
        return (
            f"<FieldPriceSlot id={self.id!r} field_id={self.field_id!r} "
            f"day_of_week={self.day_of_week!r} status={self.status!r}>"
        )
