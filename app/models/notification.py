"""Private, plain-text notifications for player accounts."""
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from .user import timestamp_type, utc_now


class NotificationType(str, Enum):
    PAYMENT_SUCCESS = "payment_success"
    JOIN_REQUEST = "join_request"
    REQUEST_ACCEPTED = "request_accepted"
    REQUEST_REJECTED = "request_rejected"
    OPPONENT_JOINED = "opponent_joined"
    PARTICIPANT_WITHDRAWN = "participant_withdrawn"
    BOOKING_CANCELLED = "booking_cancelled"
    MATCH_CANCELLED = "match_cancelled"
    REFUND_SUCCESS = "refund_success"


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event"),
        db.Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
        db.CheckConstraint(
            "type IN (" + ", ".join(repr(t.value) for t in NotificationType) + ")",
            name="ck_notifications_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    event_key: Mapped[str] = mapped_column(db.String(160), nullable=False)
    type: Mapped[str] = mapped_column(db.String(40), nullable=False)
    title: Mapped[str] = mapped_column(db.Unicode(160), nullable=False)
    message: Mapped[str] = mapped_column(db.Unicode(500), nullable=False)
    target_url: Mapped[str] = mapped_column(db.String(250), nullable=False)
    is_read: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at: Mapped[datetime] = mapped_column(timestamp_type, nullable=False, default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(timestamp_type, nullable=True)
