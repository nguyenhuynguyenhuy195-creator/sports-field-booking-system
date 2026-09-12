from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

from .user import timestamp_type, utc_now

if TYPE_CHECKING:
    from .match import Match
    from .user import User


class MatchMessageType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class MatchSystemEventType(str, Enum):
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_WITHDRAWN = "participant_withdrawn"
    LISTING_CLOSED = "listing_closed"
    MATCH_CANCELLED = "match_cancelled"
    MATCH_COMPLETED = "match_completed"


class MatchMessage(db.Model):
    """One entry of a Match chat room timeline — a user message or a system event.

    SYSTEM rows carry no sender and are keyed by ``event_key`` so a retried
    callback or job can never append the same state transition twice.
    """

    __tablename__ = "match_messages"
    __table_args__ = (
        db.CheckConstraint(
            "message_type IN ('USER', 'SYSTEM')",
            name="ck_match_messages_type",
        ),
        db.CheckConstraint(
            "event_type IS NULL OR event_type IN ("
            "'participant_joined', 'participant_withdrawn', 'listing_closed', "
            "'match_cancelled', 'match_completed')",
            name="ck_match_messages_event_type",
        ),
        db.CheckConstraint(
            "(message_type = 'USER' AND sender_id IS NOT NULL "
            "AND event_type IS NULL AND event_key IS NULL) "
            "OR (message_type = 'SYSTEM' AND sender_id IS NULL "
            "AND event_type IS NOT NULL AND event_key IS NOT NULL)",
            name="ck_match_messages_shape",
        ),
        db.CheckConstraint(
            "content <> ''",
            name="ck_match_messages_content_present",
        ),
        db.Index("ix_match_messages_match_id_id", "match_id", "id"),
        # Filtered so SQL Server does not treat the NULL event_key of every
        # USER message as a duplicate — same idiom as
        # uq_match_participants_active_user.
        db.Index(
            "uq_match_messages_system_event",
            "match_id",
            "event_key",
            unique=True,
            mssql_where=db.text("message_type = 'SYSTEM'"),
            sqlite_where=db.text("message_type = 'SYSTEM'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        db.ForeignKey("matches.id"),
        nullable=False,
    )
    sender_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id"),
        nullable=True,
    )
    message_type: Mapped[str] = mapped_column(db.String(20), nullable=False)
    content: Mapped[str] = mapped_column(db.Unicode(500), nullable=False)
    event_type: Mapped[str | None] = mapped_column(db.String(40), nullable=True)
    event_key: Mapped[str | None] = mapped_column(db.String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        timestamp_type,
        nullable=False,
        default=utc_now,
    )

    match: Mapped[Match] = relationship(foreign_keys=[match_id])
    sender: Mapped[User | None] = relationship(foreign_keys=[sender_id])

    def __repr__(self) -> str:
        return (
            f"<MatchMessage id={self.id!r} match_id={self.match_id!r} "
            f"type={self.message_type!r}>"
        )
