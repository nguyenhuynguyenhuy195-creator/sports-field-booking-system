from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .booking_contribution import BookingContribution
    from .match import Match
    from .user import User


class MatchParticipantType(str, Enum):
    PLAYER = "PLAYER"
    OPPONENT_REPRESENTATIVE = "OPPONENT_REPRESENTATIVE"


class MatchParticipantStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED_AWAITING_PAYMENT = "ACCEPTED_AWAITING_PAYMENT"
    JOINED = "JOINED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


ACTIVE_PARTICIPANT_STATUSES = (
    MatchParticipantStatus.PENDING.value,
    MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
    MatchParticipantStatus.JOINED.value,
)


class MatchParticipant(db.Model):
    __tablename__ = "match_participants"
    __table_args__ = (
        db.CheckConstraint(
            "participant_type IN ('PLAYER', 'OPPONENT_REPRESENTATIVE')",
            name="ck_match_participants_type",
        ),
        db.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED_AWAITING_PAYMENT', 'JOINED', "
            "'REJECTED', 'EXPIRED', 'WITHDRAWN')",
            name="ck_match_participants_status",
        ),
        db.Index(
            "ix_match_participants_match_status",
            "match_id",
            "status",
        ),
        db.Index(
            "uq_match_participants_active_user",
            "match_id",
            "user_id",
            unique=True,
            mssql_where=db.text(
                "status IN ('PENDING', 'ACCEPTED_AWAITING_PAYMENT', 'JOINED')"
            ),
            sqlite_where=db.text(
                "status IN ('PENDING', 'ACCEPTED_AWAITING_PAYMENT', 'JOINED')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        db.ForeignKey("matches.id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=False,
    )
    contribution_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("booking_contributions.id"),
        nullable=True,
    )
    participant_type: Mapped[str] = mapped_column(db.String(30), nullable=False)
    message: Mapped[str | None] = mapped_column(db.Unicode(500), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        db.String(30),
        nullable=False,
        default=MatchParticipantStatus.PENDING.value,
        server_default=MatchParticipantStatus.PENDING.value,
    )
    payment_due_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        timestamp_type,
        nullable=True,
        onupdate=utc_now,
    )

    match: Mapped[Match] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    contribution: Mapped[BookingContribution | None] = relationship(
        foreign_keys=[contribution_id]
    )

    def __repr__(self) -> str:
        return (
            f"<MatchParticipant id={self.id!r} match_id={self.match_id!r} "
            f"user_id={self.user_id!r} status={self.status!r}>"
        )
