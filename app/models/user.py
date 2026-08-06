from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from flask_login import UserMixin
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class UserRole(str, Enum):
    USER = "USER"
    OWNER = "OWNER"
    ADMIN = "ADMIN"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    INACTIVE = "INACTIVE"


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for SQL Server DATETIME2."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


timestamp_type = db.DateTime().with_variant(DATETIME2(), "mssql")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('USER', 'OWNER', 'ADMIN')",
            name="ck_users_role",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'LOCKED', 'INACTIVE')",
            name="ck_users_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=UserRole.USER.value,
    )
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=UserStatus.ACTIVE.value,
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

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE.value

    @property
    def is_owner(self) -> bool:
        return self.role == UserRole.OWNER.value

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"
