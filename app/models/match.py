from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .booking import Booking
    from .match_participant import MatchParticipant
    from .user import User


class MatchType(str, Enum):
    FIND_PLAYERS = "FIND_PLAYERS"
    FIND_OPPONENT = "FIND_OPPONENT"


class MatchStatus(str, Enum):
    OPEN = "OPEN"
    FULL = "FULL"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Match(db.Model):
    __tablename__ = "matches"
    __table_args__ = (
        db.CheckConstraint(
            "match_type IN ('FIND_PLAYERS', 'FIND_OPPONENT')",
            name="ck_matches_type",
        ),
        db.CheckConstraint(
            "status IN ('OPEN', 'FULL', 'CONFIRMED', 'CANCELLED', 'COMPLETED')",
            name="ck_matches_status",
        ),
        db.CheckConstraint(
            "required_players > 0",
            name="ck_matches_required_players_positive",
        ),
        db.CheckConstraint(
            "((match_type = 'FIND_OPPONENT' "
            "AND required_players = 1 AND total_players IS NULL) "
            "OR (match_type = 'FIND_PLAYERS' "
            "AND total_players IS NOT NULL AND total_players > 1 "
            "AND required_players < total_players))",
            name="ck_matches_configuration",
        ),
        db.Index("ix_matches_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    booking_id: Mapped[int] = mapped_column(
        db.ForeignKey("bookings.id"),
        unique=True,
        nullable=False,
    )
    match_type: Mapped[str] = mapped_column(db.String(30), nullable=False)
    title: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    description: Mapped[str | None] = mapped_column(db.UnicodeText, nullable=True)
    skill_level: Mapped[str | None] = mapped_column(db.String(30), nullable=True)
    creator_contact_phone: Mapped[str | None] = mapped_column(
        db.String(20),
        nullable=True,
    )
    total_players: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    required_players: Mapped[int] = mapped_column(db.Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default=MatchStatus.OPEN.value,
        server_default=MatchStatus.OPEN.value,
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

    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    booking: Mapped[Booking] = relationship(back_populates="match")
    participants: Mapped[list[MatchParticipant]] = relationship(
        back_populates="match",
        order_by="MatchParticipant.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Match id={self.id!r} booking_id={self.booking_id!r} "
            f"type={self.match_type!r} status={self.status!r}>"
        )
