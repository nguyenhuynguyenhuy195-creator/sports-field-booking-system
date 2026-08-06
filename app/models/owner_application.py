from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import User, timestamp_type, utc_now


class OwnerApplicationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OwnerApplication(db.Model):
    __tablename__ = "owner_applications"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_owner_applications_status",
        ),
        db.Index(
            "uq_owner_applications_pending_user",
            "user_id",
            unique=True,
            mssql_where=db.text("status = 'PENDING'"),
            sqlite_where=db.text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    business_name: Mapped[str] = mapped_column(db.Unicode(150), nullable=False)
    contact_phone: Mapped[str] = mapped_column(db.String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(db.Unicode(500), nullable=True)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=OwnerApplicationStatus.PENDING.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        db.Unicode(500),
        nullable=True,
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )

    applicant: Mapped[User] = relationship(foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])

    @property
    def is_pending(self) -> bool:
        return self.status == OwnerApplicationStatus.PENDING.value

    def __repr__(self) -> str:
        return (
            f"<OwnerApplication id={self.id!r} "
            f"user_id={self.user_id!r} status={self.status!r}>"
        )
