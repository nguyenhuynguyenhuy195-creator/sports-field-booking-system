from __future__ import annotations

from datetime import datetime, time
from enum import Enum

from sqlalchemy.dialects.mssql import TIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import User, timestamp_type, utc_now


class VenueStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    HIDDEN = "HIDDEN"
    INACTIVE = "INACTIVE"


time_type = db.Time().with_variant(TIME(precision=0), "mssql")


class Venue(db.Model):
    __tablename__ = "venues"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'HIDDEN', 'INACTIVE')",
            name="ck_venues_status",
        ),
        db.CheckConstraint(
            "opening_time < closing_time",
            name="ck_venues_opening_before_closing",
        ),
        db.Index("ix_venues_owner_created", "owner_id", "created_at"),
        db.Index("ix_venues_status_city", "status", "city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(db.Unicode(150), nullable=False)
    address: Mapped[str] = mapped_column(db.Unicode(255), nullable=False)
    district: Mapped[str | None] = mapped_column(db.Unicode(100), nullable=True)
    city: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(db.UnicodeText, nullable=True)
    opening_time: Mapped[time] = mapped_column(time_type, nullable=False)
    closing_time: Mapped[time] = mapped_column(time_type, nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=VenueStatus.PENDING.value,
        server_default=VenueStatus.PENDING.value,
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    moderation_note: Mapped[str | None] = mapped_column(
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

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])

    @property
    def is_active(self) -> bool:
        return self.status == VenueStatus.ACTIVE.value

    def __repr__(self) -> str:
        return (
            f"<Venue id={self.id!r} owner_id={self.owner_id!r} "
            f"status={self.status!r}>"
        )
