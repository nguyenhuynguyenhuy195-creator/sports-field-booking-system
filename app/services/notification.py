"""Best-effort delivery AFTER business commit, using an independent session.

Only small event descriptors are queued, never Notification ORM rows in the
business session. A process crash between commit and delivery can lose an alert;
there is deliberately no durable outbox/retry infrastructure in this MVP.
"""
import logging
import re

from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Booking, Match, MatchParticipant, Notification, NotificationType, Payment, Refund, User
from app.models.user import utc_now

logger = logging.getLogger(__name__)
_QUEUE = "notification_events"
_LOCAL_PATH = re.compile(r"/(?:notifications|bookings(?:/[A-Za-z0-9_-]+)?|matches(?:/[0-9]+)?)\Z")


def validate_target_url(value: str) -> str:
    if not isinstance(value, str) or not _LOCAL_PATH.fullmatch(value):
        raise ValueError("Notification target must be an application-local path")
    return value


def create_notification_once(*, user_id, event_key, type, title, message, target_url):
    """Commit in a private session; never commit/rollback the caller's session.

    Call only after the recipient/business IDs have committed. A unique key
    also arbitrates concurrent deliveries. Other DB failures propagate to the
    delivery boundary below, where they are logged without sensitive values.
    """
    type = NotificationType(type).value
    target_url = validate_target_url(target_url)
    for value, maximum in ((event_key, 160), (title, 160), (message, 500)):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError("Invalid notification text")
    with Session(db.engine, expire_on_commit=False) as session:
        recipient = session.get(User, user_id)
        if recipient is None or recipient.role != "USER":
            return None
        statement = db.select(Notification).where(
            Notification.user_id == user_id, Notification.event_key == event_key,
        )
        existing = session.scalar(statement)
        if existing is not None:
            return existing
        row = Notification(user_id=user_id, event_key=event_key, type=type,
                           title=title, message=message, target_url=target_url)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()  # This is exclusively the private delivery session.
            existing = session.scalar(statement)
            if existing is None:
                raise
            return existing
        return row


def queue_business_notification(kind, entity, *, recipients=None):
    """No SQL, flush, commit or rollback. IDs are read only after commit."""
    try:
        db.session.info.setdefault(_QUEUE, []).append((kind, entity, recipients))
    except Exception:
        logger.warning("Không thể chuẩn bị thông báo.")


def queue_cancellation_notification(booking, *, rejected_recipient_ids=()):
    """No SQL. Rejected IDs come from the existing business cleanup loop.

    Creator and still-active/joined members are resolved AFTER commit. This
    avoids relationship lazy loads or autoflush in the business transaction.
    """
    queue_business_notification("booking_cancelled", booking, recipients=rejected_recipient_ids)


def queue_listing_closed_notification(match):
    try:
        recipients = {match.creator_id}
        recipients.update(p.user_id for p in match.participants
                          if p.status in {"PENDING", "ACCEPTED_AWAITING_PAYMENT"})
        queue_business_notification("match_cancelled", match, recipients=tuple(recipients))
    except Exception:
        logger.warning("Không thể chuẩn bị thông báo đóng kèo.")


@event.listens_for(Session, "after_commit")
def _deliver_after_commit(session):
    if session.in_nested_transaction():
        return
    queued = session.info.pop(_QUEUE, [])
    for kind, entity, recipients in queued:
        try:
            identity = inspect(entity).identity
            if identity is not None:
                _deliver_event(kind, type(entity), identity[0], recipients)
        except Exception:
            # No exception details: DB errors can contain private SQL parameters.
            logger.warning("Không thể lưu thông báo sau khi nghiệp vụ đã hoàn tất.")


@event.listens_for(Session, "after_soft_rollback")
def _discard_after_rollback(session, previous_transaction):
    # Conservative on savepoint rollback too: never deliver a rolled-back event.
    session.info.pop(_QUEUE, None)


@event.listens_for(Session, "after_transaction_end")
def _discard_after_close(session, transaction):
    if transaction.parent is None:
        # Session.close() also rolls back; a reused session must not replay it.
        session.info.pop(_QUEUE, None)


def _deliver_event(kind, model, entity_id, recipients):
    with Session(db.engine) as session:
        entity = session.get(model, entity_id)
        if entity is None:
            return
        deliveries = []
        if isinstance(entity, Payment) and entity.status == "SUCCESS":
            target = _booking_target(entity.booking, entity.payer_id)
            deliveries = [(entity.payer_id, "Thanh toán thành công", "Thanh toán tiền cọc đã được ghi nhận.", target)]
        elif isinstance(entity, Refund) and entity.status == "SUCCESS":
            deliveries = [(entity.recipient_id, "Hoàn tiền thành công", "Khoản hoàn tiền của bạn đã được ghi nhận thành công.", _booking_target(entity.booking, entity.recipient_id))]
        elif isinstance(entity, MatchParticipant):
            match = entity.match
            target = f"/matches/{match.id}"
            if kind == "join_request" and match.match_type == "FIND_PLAYERS":
                deliveries = [(match.creator_id, "Yêu cầu tham gia mới", "Có người gửi yêu cầu tham gia kèo của bạn.", target)]
            elif kind == "request_accepted":
                message = ("Yêu cầu của bạn đã được chấp nhận. Bạn đã tham gia kèo."
                           if entity.status == "JOINED" else "Yêu cầu của bạn đã được chấp nhận. Xem kèo để theo dõi bước tiếp theo.")
                deliveries = [(entity.user_id, "Yêu cầu được chấp nhận", message, target)]
            elif kind == "request_rejected":
                deliveries = [(entity.user_id, "Yêu cầu chưa được chấp nhận", "Người tạo kèo đã từ chối yêu cầu tham gia của bạn.", target)]
            elif kind == "opponent_joined" and match.match_type == "FIND_OPPONENT" and entity.status == "JOINED":
                deliveries = [(match.creator_id, "Đối thủ đã tham gia", "Đối thủ đã hoàn tất điều kiện tham gia kèo của bạn.", target)]
            elif kind == "participant_withdrawn":
                message = "Một người đã rút yêu cầu hoặc ngừng tham gia kèo của bạn."
                if entity.contribution is not None and entity.contribution.status == "FORFEITED":
                    message = "Đối thủ đã rút khỏi kèo. Khoản cọc đã đóng không được hoàn lại theo chính sách của kèo."
                deliveries = [(match.creator_id, "Có người rút khỏi kèo", message, target)]
        elif isinstance(entity, Booking) and entity.status == "CANCELLED":
            affected = {entity.user_id, *(recipients or ())}
            if entity.match is not None:
                affected.update(p.user_id for p in entity.match.participants
                                if p.status in {"PENDING", "ACCEPTED_AWAITING_PAYMENT", "JOINED"})
            deliveries = [(uid, "Lịch sân đã hủy", "Lịch đặt sân đã bị hủy. Xem chi tiết để theo dõi tình trạng của kèo và tiền cọc.", _booking_target(entity, uid)) for uid in affected]
        elif isinstance(entity, Match) and entity.status == "CANCELLED":
            deliveries = [(uid, "Đã đóng bài tìm đối thủ", "Bài tìm đối thủ đã đóng. Các suất đang giữ không còn hiệu lực.", f"/matches/{entity.id}") for uid in (recipients or (entity.creator_id,))]
        for uid, title, message, target in deliveries:
            try:
                create_notification_once(user_id=uid, event_key=f"{kind}:{entity_id}",
                                         type=kind, title=title, message=message, target_url=target)
            except Exception:
                logger.warning("Không thể lưu thông báo cho người nhận.")


def _booking_target(booking, user_id):
    if booking.user_id == user_id:
        return f"/bookings/{booking.booking_code}"
    return f"/matches/{booking.match.id}" if booking.match is not None else "/notifications"


def notification_dto(row):
    try:
        target = validate_target_url(row.target_url)
    except ValueError:
        target = "/notifications"
    return {"id": row.id, "type": row.type, "title": row.title, "message": row.message,
            "target_url": target, "is_read": row.is_read,
            "created_at": row.created_at.isoformat(timespec="seconds") + "Z"}


def count_unread_notifications(user_id):
    return db.session.scalar(db.select(db.func.count(Notification.id)).where(
        Notification.user_id == user_id, Notification.is_read == db.false()))


def _user_statement(user_id):
    return db.select(Notification).where(Notification.user_id == user_id).order_by(
        Notification.created_at.desc(), Notification.id.desc())


def list_recent_notifications(user_id):
    return [notification_dto(row) for row in db.session.scalars(_user_statement(user_id).limit(5))]


def list_user_notifications(user_id, *, page=1):
    pagination = db.paginate(_user_statement(user_id), page=max(1, page), per_page=20, error_out=False)
    return pagination, [notification_dto(row) for row in pagination.items]


def mark_notification_read(user_id, notification_id):
    row = db.session.scalar(db.select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user_id))
    if row is None:
        return False
    db.session.execute(db.update(Notification).where(
        Notification.id == notification_id, Notification.user_id == user_id,
        Notification.is_read == db.false()).values(is_read=True, read_at=utc_now()))
    db.session.commit()
    return True


def mark_all_notifications_read(user_id):
    db.session.execute(db.update(Notification).where(
        Notification.user_id == user_id, Notification.is_read == db.false()
    ).values(is_read=True, read_at=utc_now()))
    db.session.commit()
