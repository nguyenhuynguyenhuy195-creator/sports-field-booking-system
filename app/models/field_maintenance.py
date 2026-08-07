from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .field import Field
from .user import User, timestamp_type, utc_now
from .venue import time_type


class FieldMaintenanceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class FieldMaintenance(db.Model):
    __tablename__ = "field_maintenances"
    __table_args__ = (
        db.CheckConstraint(
            "start_time < end_time",
            name="ck_field_maintenances_start_before_end",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED', 'COMPLETED')",
            name="ck_field_maintenances_status",
        ),
        db.Index(
            "ix_field_maintenances_field_date_status_time",
            "field_id",
            "maintenance_date",
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
    maintenance_date: Mapped[date] = mapped_column(db.Date, nullable=False)
    start_time: Mapped[time] = mapped_column(time_type, nullable=False)
    end_time: Mapped[time] = mapped_column(time_type, nullable=False)
    reason: Mapped[str] = mapped_column(db.Unicode(500), nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=FieldMaintenanceStatus.ACTIVE.value,
        server_default=FieldMaintenanceStatus.ACTIVE.value,
    )
    created_by: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )

    field: Mapped[Field] = relationship(back_populates="maintenances")
    creator: Mapped[User] = relationship(foreign_keys=[created_by])

    @property
    def is_active(self) -> bool:
        return self.status == FieldMaintenanceStatus.ACTIVE.value

    def __repr__(self) -> str:
        return (
            f"<FieldMaintenance id={self.id!r} field_id={self.field_id!r} "
            f"maintenance_date={self.maintenance_date!r} status={self.status!r}>"
        )
