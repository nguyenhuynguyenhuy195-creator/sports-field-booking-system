from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now
from .venue import Venue


class FieldType(str, Enum):
    FIVE_A_SIDE = "FIVE_A_SIDE"
    SEVEN_A_SIDE = "SEVEN_A_SIDE"
    ELEVEN_A_SIDE = "ELEVEN_A_SIDE"


class FieldStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Field(db.Model):
    __tablename__ = "fields"
    __table_args__ = (
        db.CheckConstraint(
            "field_type IN ('FIVE_A_SIDE', 'SEVEN_A_SIDE', 'ELEVEN_A_SIDE')",
            name="ck_fields_type",
        ),
        db.CheckConstraint(
            "capacity > 0",
            name="ck_fields_capacity_positive",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_fields_status",
        ),
        db.UniqueConstraint(
            "venue_id",
            "name",
            name="uq_fields_venue_name",
        ),
        db.Index("ix_fields_venue_status", "venue_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        db.ForeignKey("venues.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    field_type: Mapped[str] = mapped_column(db.String(50), nullable=False)
    surface_type: Mapped[str | None] = mapped_column(
        db.Unicode(50),
        nullable=True,
    )
    capacity: Mapped[int] = mapped_column(db.Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=FieldStatus.INACTIVE.value,
        server_default=FieldStatus.INACTIVE.value,
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

    venue: Mapped[Venue] = relationship()
    price_slots: Mapped[list["FieldPriceSlot"]] = relationship(
        back_populates="field",
        order_by="FieldPriceSlot.day_of_week, FieldPriceSlot.start_time",
    )
    maintenances: Mapped[list["FieldMaintenance"]] = relationship(
        back_populates="field",
        order_by="FieldMaintenance.maintenance_date, FieldMaintenance.start_time",
    )

    @property
    def is_active(self) -> bool:
        return self.status == FieldStatus.ACTIVE.value

    def __repr__(self) -> str:
        return (
            f"<Field id={self.id!r} venue_id={self.venue_id!r} "
            f"status={self.status!r}>"
        )
