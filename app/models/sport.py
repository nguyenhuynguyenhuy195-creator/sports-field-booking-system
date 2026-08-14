from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .field_type import FieldType


class CatalogStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SportCode(str, Enum):
    FOOTBALL = "FOOTBALL"
    BADMINTON = "BADMINTON"
    PICKLEBALL = "PICKLEBALL"
    TENNIS = "TENNIS"


class Sport(db.Model):
    __tablename__ = "sports"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_sports_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(db.String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(100), unique=True, nullable=False)
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

    field_types: Mapped[list["FieldType"]] = relationship(
        back_populates="sport",
        order_by="FieldType.id",
    )

    @property
    def is_active(self) -> bool:
        return self.status == CatalogStatus.ACTIVE.value

    def __repr__(self) -> str:
        return f"<Sport id={self.id!r} code={self.code!r} status={self.status!r}>"
