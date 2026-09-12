"""Match chat room: read/send authorization, message history and system events.

Authorization lives here — routes and templates only ask this module. READ and
SEND are two separate rules on purpose: a cancelled or finished room stays
readable for everyone who could read it, but nobody can post into it any more.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    BookingStatus,
    Match,
    MatchMessage,
    MatchMessageType,
    MatchParticipantStatus,
    MatchStatus,
    MatchSystemEventType,
    User,
)
from app.template_filters import local_datetime


VIETNAM_TIMEZONE = timezone(timedelta(hours=7))

MESSAGE_MAX_LENGTH = 500
DEFAULT_MESSAGE_PAGE_SIZE = 50

SENDER_ROLE_CREATOR = "Chủ kèo"
SENDER_ROLE_MEMBER = "Thành viên"
SYSTEM_SENDER_NAME = "Hệ thống"

READ_ONLY_NOTICE = (
    "Phòng kèo đã đóng. Bạn vẫn xem lại được toàn bộ nội dung đã trao đổi."
)


class MatchChatError(ValueError):
    """Base error for the match chat room."""


class MatchChatNotFoundError(MatchChatError):
    """Raised when the match does not exist."""


class MatchChatPermissionError(MatchChatError):
    """Raised when the user may not read this room."""


class MatchChatClosedError(MatchChatError):
    """Raised when the user may read but the room no longer accepts messages."""


class MatchChatValidationError(MatchChatError):
    """Raised when the submitted message is empty or too long."""


def current_vietnam_time() -> datetime:
    """Naive Vietnam local time, matching the booking_date/end_time columns."""
    return datetime.now(VIETNAM_TIMEZONE).replace(tzinfo=None)


def can_read_match_chat(match: Match | None, user) -> bool:
    """Creator forever; participants only while their current status is JOINED.

    Nobody else — an admin or the venue owner has no privilege here unless
    they are themselves the creator or a joined participant.
    """
    if match is None or user is None or not getattr(user, "is_authenticated", False):
        return False
    if user.id == match.creator_id:
        return True
    return any(
        participant.user_id == user.id
        and participant.status == MatchParticipantStatus.JOINED.value
        for participant in match.participants
    )


def match_chat_is_active(match: Match, *, now: datetime | None = None) -> bool:
    """Whether the room still accepts new messages.

    Deliberately NOT match_accepts_actions(): that helper closes at the booking
    START time, while the room stays open until the booking END time.
    """
    if match.status in {MatchStatus.CANCELLED.value, MatchStatus.COMPLETED.value}:
        # A creator-closed FIND_OPPONENT listing also lands here; the timeline
        # keeps the two apart through its own system event, not through status.
        return False
    if match.booking.status == BookingStatus.CANCELLED.value:
        return False
    local_now = now or current_vietnam_time()
    end_at = datetime.combine(match.booking.booking_date, match.booking.end_time)
    return local_now < end_at


def assert_can_read_match_chat(*, match: Match, user) -> None:
    if not can_read_match_chat(match, user):
        raise MatchChatPermissionError("Bạn không có quyền vào phòng kèo này.")


def assert_can_send_match_chat(
    *,
    match: Match,
    user,
    now: datetime | None = None,
) -> None:
    assert_can_read_match_chat(match=match, user=user)
    if not match_chat_is_active(match, now=now):
        raise MatchChatClosedError(
            "Phòng kèo đã đóng nên không thể gửi thêm tin nhắn."
        )


def list_match_messages(
    *,
    match_id: int,
    after_id: int | None = None,
    limit: int = DEFAULT_MESSAGE_PAGE_SIZE,
) -> list[MatchMessage]:
    """Oldest → newest. Without after_id, the newest ``limit`` rows."""
    statement = (
        db.select(MatchMessage)
        .options(joinedload(MatchMessage.sender))
        .where(MatchMessage.match_id == match_id)
    )
    if after_id is None:
        rows = list(
            db.session.scalars(
                statement.order_by(MatchMessage.id.desc()).limit(limit)
            )
        )
        rows.reverse()
        return rows
    return list(
        db.session.scalars(
            statement.where(MatchMessage.id > after_id)
            .order_by(MatchMessage.id)
            .limit(limit)
        )
    )


def serialize_message(message: MatchMessage, *, creator_id: int) -> dict:
    """The single shape used by BOTH the server-rendered page and the poll API.

    Keeping one serializer is what stops the initial messages and the polled
    ones from disagreeing on timezone, role label or structure.
    """
    payload = {
        "id": message.id,
        "type": message.message_type,
        "content": message.content,
        "created_at": local_datetime(message.created_at),
    }
    if message.message_type == MatchMessageType.SYSTEM.value:
        payload["sender_name"] = SYSTEM_SENDER_NAME
        payload["sender_role"] = None
        payload["event_type"] = message.event_type
        return payload
    payload["sender_name"] = message.sender.full_name if message.sender else ""
    payload["sender_role"] = (
        SENDER_ROLE_CREATOR
        if message.sender_id == creator_id
        else SENDER_ROLE_MEMBER
    )
    return payload


def serialize_messages(messages, *, creator_id: int) -> list[dict]:
    return [serialize_message(message, creator_id=creator_id) for message in messages]


def send_user_message(
    *,
    match: Match,
    user: User,
    content: str | None,
    now: datetime | None = None,
) -> MatchMessage:
    assert_can_send_match_chat(match=match, user=user, now=now)
    normalized = (content or "").strip()
    if not normalized:
        raise MatchChatValidationError("Vui lòng nhập nội dung tin nhắn.")
    if len(normalized) > MESSAGE_MAX_LENGTH:
        raise MatchChatValidationError(
            f"Tin nhắn tối đa {MESSAGE_MAX_LENGTH} ký tự."
        )
    message = MatchMessage(
        match_id=match.id,
        sender_id=user.id,
        message_type=MatchMessageType.USER.value,
        content=normalized,
    )
    db.session.add(message)
    _commit_match_chat("Không thể gửi tin nhắn lúc này.")
    return message


def record_system_event(
    *,
    match_id: int,
    event_type: str,
    event_key: str,
    content: str,
) -> MatchMessage | None:
    """Append one system event, or do nothing if it is already recorded.

    NEVER commits and NEVER rolls back: the caller's own business transaction
    owns both the state transition and this row, so a rolled-back transition
    takes its event with it.

    Duplicates are resolved by reading first. The read autoflushes, so a second
    call inside the SAME transaction sees the pending row; a retried job or
    callback runs in a LATER transaction and sees the committed row. Concurrent
    transitions of the same transition are already serialized by the row locks
    the callers hold (_lock_match / with_update_lock / the IPN payment lock),
    and uq_match_messages_system_event remains the database-level backstop.
    """
    existing = db.session.scalar(
        db.select(MatchMessage.id).where(
            MatchMessage.match_id == match_id,
            MatchMessage.message_type == MatchMessageType.SYSTEM.value,
            MatchMessage.event_key == event_key,
        )
    )
    if existing is not None:
        return None
    message = MatchMessage(
        match_id=match_id,
        sender_id=None,
        message_type=MatchMessageType.SYSTEM.value,
        content=content[:MESSAGE_MAX_LENGTH],
        event_type=event_type,
        event_key=event_key,
    )
    db.session.add(message)
    return message


def record_participant_joined(participant) -> MatchMessage | None:
    name = participant.user.full_name if participant.user else "Một người chơi"
    return record_system_event(
        match_id=participant.match_id,
        event_type=MatchSystemEventType.PARTICIPANT_JOINED.value,
        event_key=f"{MatchSystemEventType.PARTICIPANT_JOINED.value}:{participant.id}",
        content=f"{name} đã tham gia kèo.",
    )


def record_participant_withdrawn(participant) -> MatchMessage | None:
    name = participant.user.full_name if participant.user else "Một người chơi"
    return record_system_event(
        match_id=participant.match_id,
        event_type=MatchSystemEventType.PARTICIPANT_WITHDRAWN.value,
        event_key=(
            f"{MatchSystemEventType.PARTICIPANT_WITHDRAWN.value}:{participant.id}"
        ),
        content=f"{name} đã rút khỏi kèo.",
    )


def record_listing_closed(match: Match) -> MatchMessage | None:
    return record_system_event(
        match_id=match.id,
        event_type=MatchSystemEventType.LISTING_CLOSED.value,
        event_key=f"{MatchSystemEventType.LISTING_CLOSED.value}:{match.id}",
        content=(
            "Người tạo kèo đã đóng bài tìm đối thủ. "
            "Lịch đặt sân và tiền cọc vẫn được giữ nguyên."
        ),
    )


def record_match_cancelled(match: Match) -> MatchMessage | None:
    """Booking cancellation closed this match — described as the booking event
    it actually is, because some cancellation paths never touch Match.status."""
    return record_system_event(
        match_id=match.id,
        event_type=MatchSystemEventType.MATCH_CANCELLED.value,
        event_key=f"{MatchSystemEventType.MATCH_CANCELLED.value}:{match.id}",
        content="Lịch đặt sân đã bị hủy nên kèo này không còn hiệu lực.",
    )


def record_match_completed(match: Match) -> MatchMessage | None:
    return record_system_event(
        match_id=match.id,
        event_type=MatchSystemEventType.MATCH_COMPLETED.value,
        event_key=f"{MatchSystemEventType.MATCH_COMPLETED.value}:{match.id}",
        content="Kèo đã kết thúc. Phòng kèo chuyển sang chế độ chỉ xem.",
    )


def _commit_match_chat(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise MatchChatError(message) from exc
