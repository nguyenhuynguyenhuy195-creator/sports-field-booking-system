from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .sport import CatalogStatus, Sport
from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .field import Field


class FieldTypeCode(str, Enum):
    FOOTBALL_5 = "FOOTBALL_5"
    FOOTBALL_7 = "FOOTBALL_7"
    FOOTBALL_11 = "FOOTBALL_11"
    BADMINTON_STANDARD = "BADMINTON_STANDARD"
    PICKLEBALL_STANDARD = "PICKLEBALL_STANDARD"
    TENNIS_STANDARD = "TENNIS_STANDARD"


class FieldType(db.Model):
    __tablename__ = "field_types"
    __table_args__ = (
        db.CheckConstraint(
            "standard_players_per_side IS NULL "
            "OR standard_players_per_side > 0",
            name="ck_field_types_players_per_side_positive",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_field_types_status",
        ),
        db.UniqueConstraint(
            "sport_id",
            "name",
            name="uq_field_types_sport_name",
        ),
        db.Index("ix_field_types_sport_status", "sport_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(
        db.ForeignKey("sports.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    standard_players_per_side: Mapped[int | None] = mapped_column(
        db.Integer,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=CatalogStatus.ACTIVE.value,
        server_default=CatalogStatus.ACTIVE.value,
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

    sport: Mapped[Sport] = relationship(back_populates="field_types")
    fields: Mapped[list["Field"]] = relationship(back_populates="field_type")

    @property
    def is_active(self) -> bool:
        return self.status == CatalogStatus.ACTIVE.value

    def __repr__(self) -> str:
        return (
            f"<FieldType id={self.id!r} code={self.code!r} "
            f"sport_id={self.sport_id!r}>"
        )
