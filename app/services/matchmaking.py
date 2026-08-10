from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    ACTIVE_PARTICIPANT_STATUSES,
    Booking,
    BookingContribution,
    BookingPaymentMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Field,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchParticipantType,
    MatchStatus,
    MatchType,
    User,
    UserRole,
)

from .locking import with_update_lock


PARTICIPANT_PAYMENT_MINUTES = 15
MATCHABLE_BOOKING_STATUSES = (
    BookingStatus.PARTIALLY_PAID.value,
    BookingStatus.PAID.value,
)


class MatchmakingError(ValueError):
    """Base error for find-opponent and find-player rules."""


class MatchNotFoundError(MatchmakingError):
    """Raised when a match or request does not exist."""


class MatchPermissionError(MatchmakingError):
    """Raised when the current user cannot perform an action."""


class InvalidMatchStateError(MatchmakingError):
    """Raised when the requested transition is no longer possible."""


class DuplicateMatchRequestError(MatchmakingError):
    """Raised when a user already has an active request for a match."""


def validate_match_creation(
    *,
    booking: Booking,
    creator: User,
    now: datetime | None = None,
) -> None:
    """Validate whether the booking creation screen may be shown."""
    _validate_actor(creator)
    if booking.user_id != creator.id:
        raise MatchPermissionError("Chỉ người tạo booking được mở kèo.")
    _validate_booking_can_open_match(
        booking,
        current_utc=_normalize_utc(now),
    )


def create_match(
    *,
    booking_code: str,
    creator: User,
    title: str,
    description: str | None = None,
    skill_level: str | None = None,
    match_type: str | None = None,
    required_players: int | None = None,
    now: datetime | None = None,
) -> Match:
    """Create the single MVP match attached to an eligible booking."""
    _validate_actor(creator)
    current_utc = _normalize_utc(now)
    booking = _lock_booking_by_code(booking_code)
    validate_match_creation(
        booking=booking,
        creator=creator,
        now=current_utc,
    )
    if db.session.scalar(db.select(Match.id).where(Match.booking_id == booking.id)):
        raise InvalidMatchStateError("Booking này đã có một kèo.")

    normalized_type = _resolve_match_type(booking, match_type)
    total_players, normalized_required = _resolve_player_configuration(
        booking=booking,
        match_type=normalized_type,
        required_players=required_players,
    )
    record = Match(
        creator_id=creator.id,
        booking_id=booking.id,
        match_type=normalized_type,
        title=_required_text(title, field_name="Tiêu đề", maximum=200),
        description=_optional_text(
            description,
            field_name="Mô tả",
            maximum=2000,
        ),
        skill_level=_optional_text(
            skill_level,
            field_name="Trình độ",
            maximum=30,
        ),
        total_players=total_players,
        required_players=normalized_required,
        status=MatchStatus.OPEN.value,
    )
    db.session.add(record)
    _commit_matchmaking("Không thể tạo kèo lúc này.")
    return record


def list_open_matches(*, now: datetime | None = None) -> list[Match]:
    current_utc = _normalize_utc(now)
    statement = (
        _match_details_statement()
        .join(Match.booking)
        .where(
            Match.status == MatchStatus.OPEN.value,
            Booking.status.in_(MATCHABLE_BOOKING_STATUSES),
            or_(
                Booking.booking_date > _utc_to_vietnam_date(current_utc),
                and_(
                    Booking.booking_date == _utc_to_vietnam_date(current_utc),
                    Booking.end_time > _utc_to_vietnam_time(current_utc),
                ),
            ),
        )
        .order_by(Booking.booking_date, Booking.start_time, Match.created_at)
    )
    return list(db.session.scalars(statement).unique())


def list_created_matches(creator_id: int) -> list[Match]:
    return list(
        db.session.scalars(
            _match_details_statement()
            .where(Match.creator_id == creator_id)
            .order_by(Match.created_at.desc())
        ).unique()
    )


def list_user_match_requests(user_id: int) -> list[MatchParticipant]:
    statement = (
        db.select(MatchParticipant)
        .options(
            joinedload(MatchParticipant.user),
            joinedload(MatchParticipant.contribution),
            joinedload(MatchParticipant.match)
            .joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
        )
        .where(MatchParticipant.user_id == user_id)
        .order_by(MatchParticipant.created_at.desc())
    )
    return list(db.session.scalars(statement).unique())


def get_match(match_id: int) -> Match:
    record = db.session.scalar(
        _match_details_statement().where(Match.id == match_id)
    )
    if record is None:
        raise MatchNotFoundError("Không tìm thấy kèo.")
    return record


def request_to_join_match(
    *,
    match_id: int,
    user: User,
    message: str | None = None,
    now: datetime | None = None,
) -> MatchParticipant:
    _validate_actor(user)
    current_utc = _normalize_utc(now)
    match = _lock_match(match_id)
    _expire_stale_participants_for_match(match, current_utc=current_utc)
    _validate_match_is_open(match, current_utc=current_utc)
    if match.creator_id == user.id:
        raise MatchPermissionError("Bạn không thể tham gia kèo do chính mình tạo.")

    active_request = db.session.scalar(
        db.select(MatchParticipant.id).where(
            MatchParticipant.match_id == match.id,
            MatchParticipant.user_id == user.id,
            MatchParticipant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
        )
    )
    if active_request is not None:
        raise DuplicateMatchRequestError(
            "Bạn đã có một yêu cầu đang hoạt động trong kèo này."
        )
    _ensure_match_has_capacity(match)

    participant = MatchParticipant(
        match_id=match.id,
        user_id=user.id,
        participant_type=(
            MatchParticipantType.OPPONENT_REPRESENTATIVE.value
            if match.match_type == MatchType.FIND_OPPONENT.value
            else MatchParticipantType.PLAYER.value
        ),
        message=_optional_text(message, field_name="Lời nhắn", maximum=500),
        status=MatchParticipantStatus.PENDING.value,
    )
    db.session.add(participant)
    _commit_matchmaking("Không thể gửi yêu cầu tham gia lúc này.")
    return participant


def decide_match_request(
    *,
    match_id: int,
    participant_id: int,
    creator: User,
    accept: bool,
    now: datetime | None = None,
) -> MatchParticipant:
    _validate_actor(creator)
    current_utc = _normalize_utc(now)
    match = _lock_match(match_id)
    if match.creator_id != creator.id:
        raise MatchPermissionError("Chỉ người tạo kèo được duyệt yêu cầu.")
    _expire_stale_participants_for_match(match, current_utc=current_utc)
    participant = _lock_participant(match_id=match.id, participant_id=participant_id)
    if participant.status != MatchParticipantStatus.PENDING.value:
        raise InvalidMatchStateError("Yêu cầu này đã được xử lý.")

    if not accept:
        participant.status = MatchParticipantStatus.REJECTED.value
        participant.decided_at = current_utc
        _commit_matchmaking("Không thể từ chối yêu cầu lúc này.")
        return participant

    _validate_match_is_open(match, current_utc=current_utc)
    _ensure_match_has_capacity(match)
    contribution = _lock_available_contribution(match)
    participant.decided_at = current_utc
    participant.contribution_id = contribution.id if contribution else None

    if contribution is not None and contribution.status == ContributionStatus.PENDING.value:
        payment_due_at = current_utc + timedelta(
            minutes=PARTICIPANT_PAYMENT_MINUTES
        )
        if (
            match.booking.funding_deadline is not None
            and payment_due_at > match.booking.funding_deadline
        ):
            raise InvalidMatchStateError(
                "Không còn đủ 15 phút trước hạn góp tiền. "
                "Người tạo cần trả phần còn thiếu để tiếp tục ghép người."
            )
        contribution.user_id = participant.user_id
        contribution.expires_at = payment_due_at
        participant.payment_due_at = payment_due_at
        participant.status = (
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
    else:
        if contribution is not None:
            contribution.user_id = participant.user_id
        participant.payment_due_at = None
        participant.status = MatchParticipantStatus.JOINED.value
        _refresh_match_status(match)

    _commit_matchmaking("Không thể chấp nhận yêu cầu lúc này.")
    return participant


def withdraw_match_request(
    *,
    match_id: int,
    user: User,
    now: datetime | None = None,
) -> MatchParticipant:
    """Withdraw an unpaid request; paid withdrawals wait for the refund module."""
    _validate_actor(user)
    current_utc = _normalize_utc(now)
    match = _lock_match(match_id)
    participant = db.session.scalar(
        with_update_lock(
            db.select(MatchParticipant)
            .where(
                MatchParticipant.match_id == match.id,
                MatchParticipant.user_id == user.id,
                MatchParticipant.status.in_(
                    (
                        MatchParticipantStatus.PENDING.value,
                        MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
                        MatchParticipantStatus.JOINED.value,
                    )
                ),
            )
            .order_by(MatchParticipant.created_at.desc()),
            MatchParticipant,
        )
    )
    if participant is None:
        raise MatchNotFoundError("Bạn không có yêu cầu đang hoạt động trong kèo này.")
    if participant.status == MatchParticipantStatus.JOINED.value:
        raise InvalidMatchStateError(
            "Yêu cầu đã thanh toán cần đi qua quy trình hoàn tiền trước khi rút."
        )

    _release_unpaid_contribution(participant)
    participant.status = MatchParticipantStatus.WITHDRAWN.value
    participant.decided_at = current_utc
    participant.payment_due_at = None
    if match.status in {MatchStatus.FULL.value, MatchStatus.CONFIRMED.value}:
        match.status = MatchStatus.OPEN.value
    _commit_matchmaking("Không thể rút yêu cầu lúc này.")
    return participant


def expire_stale_match_participants(
    *,
    now: datetime | None = None,
    match_id: int | None = None,
) -> int:
    """Release accepted requests whose 15-minute payment window has passed."""
    current_utc = _normalize_utc(now)
    statement = db.select(MatchParticipant).where(
        MatchParticipant.status
        == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
        MatchParticipant.payment_due_at.is_not(None),
        MatchParticipant.payment_due_at <= current_utc,
    )
    if match_id is not None:
        statement = statement.where(MatchParticipant.match_id == match_id)
    records = list(
        db.session.scalars(with_update_lock(statement, MatchParticipant))
    )
    match_ids: set[int] = set()
    for participant in records:
        _expire_participant(participant, current_utc=current_utc)
        match_ids.add(participant.match_id)
    for current_match_id in match_ids:
        match = db.session.get(Match, current_match_id)
        if match is not None:
            match.status = MatchStatus.OPEN.value
    if records:
        _commit_matchmaking("Không thể cập nhật yêu cầu tham gia đã hết hạn.")
    return len(records)


def expire_participant_for_contribution(
    contribution: BookingContribution,
    *,
    now: datetime,
) -> bool:
    """Expire one awaiting participant inside the caller's payment transaction."""
    participant = db.session.scalar(
        db.select(MatchParticipant).where(
            MatchParticipant.contribution_id == contribution.id,
            MatchParticipant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
        )
    )
    if (
        participant is None
        or participant.payment_due_at is None
        or participant.payment_due_at > now
    ):
        return False
    _expire_participant(participant, current_utc=now)
    participant.match.status = MatchStatus.OPEN.value
    return True


def mark_participant_joined_after_payment(
    contribution: BookingContribution,
    *,
    paid_at: datetime,
) -> MatchParticipant | None:
    """Promote the accepted request as part of the successful payment transaction."""
    participant = db.session.scalar(
        db.select(MatchParticipant)
        .options(joinedload(MatchParticipant.match))
        .where(
            MatchParticipant.contribution_id == contribution.id,
            MatchParticipant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
        )
    )
    if participant is None:
        return None
    participant.status = MatchParticipantStatus.JOINED.value
    participant.decided_at = paid_at
    participant.payment_due_at = None
    _refresh_match_status(participant.match)
    return participant


def join_waived_match_participants(
    *,
    booking_id: int,
    joined_at: datetime,
) -> int:
    """Join accepted users whose obligations were paid by the booking creator."""
    participants = list(
        db.session.scalars(
            db.select(MatchParticipant)
            .join(MatchParticipant.contribution)
            .options(joinedload(MatchParticipant.match))
            .where(
                BookingContribution.booking_id == booking_id,
                BookingContribution.status == ContributionStatus.WAIVED.value,
                MatchParticipant.status
                == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
            )
        )
    )
    touched_matches: dict[int, Match] = {}
    for participant in participants:
        participant.status = MatchParticipantStatus.JOINED.value
        participant.decided_at = joined_at
        participant.payment_due_at = None
        participant.contribution.expires_at = None
        touched_matches[participant.match_id] = participant.match
    for match in touched_matches.values():
        _refresh_match_status(match)
    return len(participants)


def _match_details_statement():
    return db.select(Match).options(
        joinedload(Match.creator),
        joinedload(Match.booking)
        .joinedload(Booking.field)
        .joinedload(Field.venue),
        selectinload(Match.participants).joinedload(MatchParticipant.user),
        selectinload(Match.participants).joinedload(
            MatchParticipant.contribution
        ),
    )


def _lock_booking_by_code(booking_code: str) -> Booking:
    statement = with_update_lock(
        db.select(Booking)
        .options(joinedload(Booking.field))
        .where(Booking.booking_code == booking_code),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking is None:
        raise MatchNotFoundError("Không tìm thấy booking.")
    return booking


def _lock_match(match_id: int) -> Match:
    statement = with_update_lock(
        db.select(Match)
        .options(
            joinedload(Match.booking).joinedload(Booking.field),
            selectinload(Match.participants).joinedload(
                MatchParticipant.contribution
            ),
        )
        .where(Match.id == match_id),
        Match,
    )
    match = db.session.scalar(statement)
    if match is None:
        raise MatchNotFoundError("Không tìm thấy kèo.")
    return match


def _lock_participant(*, match_id: int, participant_id: int) -> MatchParticipant:
    statement = with_update_lock(
        db.select(MatchParticipant).where(
            MatchParticipant.id == participant_id,
            MatchParticipant.match_id == match_id,
        ),
        MatchParticipant,
    )
    participant = db.session.scalar(statement)
    if participant is None:
        raise MatchNotFoundError("Không tìm thấy yêu cầu tham gia.")
    return participant


def _lock_available_contribution(match: Match) -> BookingContribution | None:
    contribution_type = (
        ContributionType.OPPONENT.value
        if match.match_type == MatchType.FIND_OPPONENT.value
        else ContributionType.PLAYER.value
    )
    statement = with_update_lock(
        db.select(BookingContribution)
        .where(
            BookingContribution.booking_id == match.booking_id,
            BookingContribution.contribution_type == contribution_type,
            BookingContribution.user_id.is_(None),
            BookingContribution.status.in_(
                (
                    ContributionStatus.PENDING.value,
                    ContributionStatus.WAIVED.value,
                )
            ),
        )
        .order_by(BookingContribution.slot_number),
        BookingContribution,
    )
    contribution = db.session.scalar(statement)
    if contribution is not None:
        return contribution
    if match.booking.payment_mode == BookingPaymentMode.FULL_PAYMENT.value:
        return None
    if match.booking.status == BookingStatus.PAID.value:
        return None
    raise InvalidMatchStateError("Không còn phần tiền trống cho vị trí này.")


def _validate_booking_can_open_match(
    booking: Booking,
    *,
    current_utc: datetime,
) -> None:
    if booking.payment_mode == BookingPaymentMode.FULL_PAYMENT.value:
        allowed = booking.status == BookingStatus.PAID.value
    else:
        allowed = booking.status in MATCHABLE_BOOKING_STATUSES
    if not allowed:
        raise InvalidMatchStateError(
            "Hãy hoàn thành khoản thanh toán bắt buộc trước khi mở kèo."
        )
    if _booking_has_ended(booking, current_utc=current_utc):
        raise InvalidMatchStateError("Không thể mở kèo cho lịch sân đã kết thúc.")


def _resolve_match_type(booking: Booking, requested_type: str | None) -> str:
    if booking.payment_mode == BookingPaymentMode.SPLIT_OPPONENT.value:
        expected = MatchType.FIND_OPPONENT.value
    elif booking.payment_mode == BookingPaymentMode.SPLIT_PLAYERS.value:
        expected = MatchType.FIND_PLAYERS.value
    else:
        expected = requested_type or ""
    if expected not in {item.value for item in MatchType}:
        raise MatchmakingError("Loại kèo không hợp lệ.")
    if requested_type and booking.payment_mode != BookingPaymentMode.FULL_PAYMENT.value:
        if requested_type != expected:
            raise MatchmakingError("Loại kèo không khớp hình thức booking.")
    return expected


def _resolve_player_configuration(
    *,
    booking: Booking,
    match_type: str,
    required_players: int | None,
) -> tuple[int | None, int]:
    if match_type == MatchType.FIND_OPPONENT.value:
        return None, 1
    total_players = booking.split_total_players or booking.field.capacity
    normalized_required = (
        booking.split_required_players
        if booking.payment_mode == BookingPaymentMode.SPLIT_PLAYERS.value
        else required_players
    )
    if (
        isinstance(normalized_required, bool)
        or not isinstance(normalized_required, int)
        or normalized_required <= 0
        or normalized_required >= total_players
    ):
        raise MatchmakingError(
            f"Số người cần tìm phải từ 1 đến {total_players - 1}."
        )
    return total_players, normalized_required


def _validate_match_is_open(match: Match, *, current_utc: datetime) -> None:
    if match.status != MatchStatus.OPEN.value:
        raise InvalidMatchStateError("Kèo này không còn nhận yêu cầu mới.")
    if match.booking.status not in MATCHABLE_BOOKING_STATUSES:
        raise InvalidMatchStateError("Booking của kèo không còn hiệu lực.")
    if _booking_has_ended(match.booking, current_utc=current_utc):
        raise InvalidMatchStateError("Kèo đã qua thời gian thi đấu.")


def _ensure_match_has_capacity(match: Match) -> None:
    occupied = sum(
        participant.status
        in {
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
            MatchParticipantStatus.JOINED.value,
        }
        for participant in match.participants
    )
    limit = 1 if match.match_type == MatchType.FIND_OPPONENT.value else match.required_players
    if occupied >= limit:
        raise InvalidMatchStateError(
            "Kèo đã có đối thủ hoặc đã đủ số người đang được giữ chỗ."
        )


def _expire_stale_participants_for_match(
    match: Match,
    *,
    current_utc: datetime,
) -> None:
    for participant in match.participants:
        if (
            participant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
            and participant.payment_due_at is not None
            and participant.payment_due_at <= current_utc
        ):
            _expire_participant(participant, current_utc=current_utc)
            match.status = MatchStatus.OPEN.value


def _expire_participant(
    participant: MatchParticipant,
    *,
    current_utc: datetime,
) -> None:
    _release_unpaid_contribution(participant)
    participant.status = MatchParticipantStatus.EXPIRED.value
    participant.decided_at = current_utc
    participant.payment_due_at = None


def _release_unpaid_contribution(participant: MatchParticipant) -> None:
    contribution = participant.contribution
    if (
        contribution is not None
        and contribution.status == ContributionStatus.PENDING.value
        and Decimal(contribution.amount_paid) == 0
    ):
        contribution.user_id = None
        contribution.expires_at = None


def _refresh_match_status(match: Match) -> None:
    joined_count = sum(
        participant.status == MatchParticipantStatus.JOINED.value
        for participant in match.participants
    )
    if match.match_type == MatchType.FIND_OPPONENT.value:
        match.status = (
            MatchStatus.CONFIRMED.value
            if joined_count >= 1
            else MatchStatus.OPEN.value
        )
    else:
        match.status = (
            MatchStatus.FULL.value
            if joined_count >= match.required_players
            else MatchStatus.OPEN.value
        )


def _validate_actor(user: User) -> None:
    if user.role not in {UserRole.USER.value, UserRole.OWNER.value} or not user.is_active:
        raise MatchPermissionError("Tài khoản này không thể thao tác với kèo.")


def _booking_has_ended(booking: Booking, *, current_utc: datetime) -> bool:
    local_now = current_utc.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=7))
    )
    end_at = datetime.combine(booking.booking_date, booking.end_time)
    return end_at <= local_now.replace(tzinfo=None)


def _normalize_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _utc_to_vietnam_date(value: datetime):
    return value.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=7))
    ).date()


def _utc_to_vietnam_time(value: datetime):
    return value.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=7))
    ).time().replace(tzinfo=None)


def _required_text(value: str | None, *, field_name: str, maximum: int) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise MatchmakingError(f"{field_name} không được để trống.")
    if len(normalized) > maximum:
        raise MatchmakingError(f"{field_name} tối đa {maximum} ký tự.")
    return normalized


def _optional_text(
    value: str | None,
    *,
    field_name: str,
    maximum: int,
) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise MatchmakingError(f"{field_name} tối đa {maximum} ký tự.")
    return normalized


def _commit_matchmaking(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise MatchmakingError(message) from exc
