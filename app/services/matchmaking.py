from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    ACTIVE_PARTICIPANT_STATUSES,
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
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

from .auth import normalize_phone
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
        raise MatchPermissionError("Chỉ người đặt sân được mở kèo.")
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
    contact_phone: str | None = None,
    share_contact: bool = False,
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
        raise InvalidMatchStateError("Lịch đặt sân này đã có một kèo.")

    normalized_type = _resolve_match_type(booking, match_type)
    total_players, normalized_required = _resolve_player_configuration(
        booking=booking,
        match_type=normalized_type,
        required_players=required_players,
    )
    shared_phone = _required_shared_contact_phone(
        contact_phone,
        share_contact=share_contact,
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
        creator_contact_phone=shared_phone,
        total_players=total_players,
        required_players=normalized_required,
        status=MatchStatus.OPEN.value,
    )
    creator.phone = shared_phone
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
                    Booking.start_time > _utc_to_vietnam_time(current_utc),
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
            joinedload(MatchParticipant.match).joinedload(Match.creator),
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
    contact_phone: str | None = None,
    share_contact: bool = False,
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
        with_update_lock(
            db.select(MatchParticipant).where(
                MatchParticipant.match_id == match.id,
                MatchParticipant.user_id == user.id,
                MatchParticipant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
            ),
            MatchParticipant,
        )
    )
    if active_request is not None:
        if (
            opponent_join_is_automatic(match)
            and active_request.status == MatchParticipantStatus.PENDING.value
        ):
            shared_phone = _required_shared_contact_phone(
                contact_phone,
                share_contact=share_contact,
            )
            _ensure_match_has_capacity(match)
            active_request.contact_phone = shared_phone
            user.phone = shared_phone
            _reserve_or_join_participant(
                match=match,
                participant=active_request,
                current_utc=current_utc,
            )
            _commit_matchmaking("Không thể giữ suất thanh toán lúc này.")
            return active_request
        raise DuplicateMatchRequestError(
            "Bạn đã có một yêu cầu đang hoạt động trong kèo này."
        )
    _ensure_match_has_capacity(match)

    shared_phone = _required_shared_contact_phone(
        contact_phone,
        share_contact=share_contact,
    )

    participant = MatchParticipant(
        match_id=match.id,
        user_id=user.id,
        participant_type=(
            MatchParticipantType.OPPONENT_REPRESENTATIVE.value
            if match.match_type == MatchType.FIND_OPPONENT.value
            else MatchParticipantType.PLAYER.value
        ),
        message=_optional_text(message, field_name="Lời nhắn", maximum=500),
        contact_phone=shared_phone,
        status=MatchParticipantStatus.PENDING.value,
    )
    user.phone = shared_phone
    if opponent_join_is_automatic(match):
        _reserve_or_join_participant(
            match=match,
            participant=participant,
            current_utc=current_utc,
        )
    db.session.add(participant)
    _commit_matchmaking(
        "Không thể giữ suất thanh toán lúc này."
        if opponent_join_is_automatic(match)
        else "Không thể gửi yêu cầu tham gia lúc này."
    )
    return participant


def update_match_contact(
    *,
    match_id: int,
    user: User,
    contact_phone: str | None,
    share_contact: bool,
    now: datetime | None = None,
) -> MatchParticipant | None:
    """Save a private contact snapshot for one side of an active match."""
    _validate_actor(user)
    current_utc = _normalize_utc(now)
    match = _lock_match(match_id)
    if (
        match.status in {MatchStatus.CANCELLED.value, MatchStatus.COMPLETED.value}
        or _booking_has_ended(match.booking, current_utc=current_utc)
    ):
        raise InvalidMatchStateError("Kèo đã kết thúc nên không thể đổi số liên hệ.")

    shared_phone = _required_shared_contact_phone(
        contact_phone,
        share_contact=share_contact,
    )
    participant = None
    if match.creator_id == user.id:
        match.creator_contact_phone = shared_phone
    else:
        participant = db.session.scalar(
            with_update_lock(
                db.select(MatchParticipant).where(
                    MatchParticipant.match_id == match.id,
                    MatchParticipant.user_id == user.id,
                    MatchParticipant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
                ),
                MatchParticipant,
            )
        )
        if participant is None:
            raise MatchPermissionError(
                "Chỉ người tạo hoặc người đang tham gia kèo được cập nhật liên hệ."
            )
        participant.contact_phone = shared_phone

    user.phone = shared_phone
    _commit_matchmaking("Không thể lưu số liên hệ lúc này.")
    return participant


def opponent_join_is_automatic(match: Match) -> bool:
    """Return whether an opponent can reserve the payment slot directly."""
    return bool(
        match.match_type == MatchType.FIND_OPPONENT.value
        and _uses_current_match_policy(match.booking)
    )


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
    if opponent_join_is_automatic(match):
        raise InvalidMatchStateError(
            "Kèo tìm đối thủ này tự động giữ suất thanh toán và không cần "
            "người tạo duyệt."
        )
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
    _reserve_or_join_participant(
        match=match,
        participant=participant,
        current_utc=current_utc,
    )

    _commit_matchmaking("Không thể chấp nhận yêu cầu lúc này.")
    return participant


def withdraw_match_request(
    *,
    match_id: int,
    user: User,
    now: datetime | None = None,
) -> MatchParticipant:
    """Withdraw a request and apply the paid-participant refund policy."""
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
    free_player_join = (
        match.match_type == MatchType.FIND_PLAYERS.value
        and match.booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
    )
    if participant.status == MatchParticipantStatus.JOINED.value and not free_player_join:
        if _booking_has_started(match.booking, current_utc=current_utc):
            raise InvalidMatchStateError("Kèo đã bắt đầu nên không thể báo rút.")
        contribution = participant.contribution
        if participant_withdrawal_gets_refund(
            match.booking,
            now=current_utc,
        ):
            if (
                contribution is not None
                and contribution.status == ContributionStatus.PAID.value
                and Decimal(contribution.amount_paid) > 0
            ):
                from .refund import RefundError, refund_joined_participant

                try:
                    refund_joined_participant(
                        booking=match.booking,
                        contribution=contribution,
                        participant_id=participant.id,
                        now=current_utc,
                    )
                except RefundError as exc:
                    raise InvalidMatchStateError(str(exc)) from exc
            elif (
                contribution is not None
                and contribution.status == ContributionStatus.WAIVED.value
            ):
                contribution.user_id = None
                contribution.expires_at = match.booking.funding_deadline
        elif (
            contribution is not None
            and contribution.status == ContributionStatus.PAID.value
        ):
            contribution.status = ContributionStatus.FORFEITED.value
    else:
        _release_unpaid_contribution(participant)
    participant.status = MatchParticipantStatus.WITHDRAWN.value
    participant.decided_at = current_utc
    participant.payment_due_at = None
    if match.status in {MatchStatus.FULL.value, MatchStatus.CONFIRMED.value}:
        match.status = MatchStatus.OPEN.value
    _commit_matchmaking("Không thể rút yêu cầu lúc này.")
    from .refund import RefundError, process_pending_momo_refunds

    try:
        process_pending_momo_refunds(booking_id=match.booking_id)
    except RefundError:
        db.session.rollback()
    return participant


def participant_withdrawal_gets_refund(
    booking: Booking,
    *,
    now: datetime | None = None,
) -> bool:
    """Return the legacy 12-hour refund result for old matchmaking records."""
    if _uses_current_match_policy(booking):
        return False
    current_utc = _normalize_utc(now)
    return _booking_start_utc(booking) - current_utc > timedelta(hours=12)


def expire_stale_match_participants(
    *,
    now: datetime | None = None,
    match_id: int | None = None,
) -> int:
    """Expire unpaid requests at their payment due time or at kick-off."""
    current_utc = _normalize_utc(now)
    statement = (
        db.select(MatchParticipant)
        .options(joinedload(MatchParticipant.match).joinedload(Match.booking))
        .where(
            MatchParticipant.status.in_(
                (
                    MatchParticipantStatus.PENDING.value,
                    MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
                )
            )
        )
    )
    if match_id is not None:
        statement = statement.where(MatchParticipant.match_id == match_id)
    records = list(
        db.session.scalars(with_update_lock(statement, MatchParticipant))
    )
    match_ids: set[int] = set()
    expired_count = 0
    for participant in records:
        payment_expired = (
            participant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
            and participant.payment_due_at is not None
            and participant.payment_due_at <= current_utc
        )
        match_started = _booking_has_started(
            participant.match.booking,
            current_utc=current_utc,
        )
        if not payment_expired and not match_started:
            continue
        _expire_participant(participant, current_utc=current_utc)
        match_ids.add(participant.match_id)
        expired_count += 1
    for current_match_id in match_ids:
        match = db.session.get(Match, current_match_id)
        if match is not None and not _booking_has_started(
            match.booking,
            current_utc=current_utc,
        ):
            match.status = MatchStatus.OPEN.value
    if expired_count:
        _commit_matchmaking("Không thể cập nhật yêu cầu tham gia đã hết hạn.")
    return expired_count


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
        raise MatchNotFoundError("Không tìm thấy lịch đặt sân.")
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


def _reserve_or_join_participant(
    *,
    match: Match,
    participant: MatchParticipant,
    current_utc: datetime,
) -> None:
    contribution = _lock_available_contribution(match)
    participant.decided_at = current_utc
    participant.contribution_id = contribution.id if contribution else None

    if contribution is not None and contribution.status == ContributionStatus.PENDING.value:
        payment_due_at = current_utc + timedelta(
            minutes=PARTICIPANT_PAYMENT_MINUTES
        )
        payment_cutoff = _match_request_cutoff(match.booking)
        if current_utc >= payment_cutoff:
            raise InvalidMatchStateError(
                "Đã hết hạn nhận đối thủ cho lịch đặt này."
            )
        if payment_due_at > payment_cutoff:
            payment_due_at = payment_cutoff
        contribution.user_id = participant.user_id
        contribution.expires_at = payment_due_at
        participant.payment_due_at = payment_due_at
        participant.status = (
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
        return

    if contribution is not None:
        contribution.user_id = participant.user_id
    participant.payment_due_at = None
    participant.status = MatchParticipantStatus.JOINED.value
    _refresh_match_status(match)


def _lock_available_contribution(match: Match) -> BookingContribution | None:
    if (
        match.match_type == MatchType.FIND_PLAYERS.value
        and match.booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
    ):
        return None
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
    if match.booking.booking_mode == BookingMode.DIRECT_BOOKING.value:
        return None
    if match.booking.status == BookingStatus.PAID.value:
        return None
    raise InvalidMatchStateError("Không còn phần tiền trống cho vị trí này.")


def _validate_booking_can_open_match(
    booking: Booking,
    *,
    current_utc: datetime,
) -> None:
    if booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value:
        if booking.booking_mode == BookingMode.DIRECT_BOOKING.value:
            raise InvalidMatchStateError(
                "Lịch đá nội bộ hoặc đã có kèo không thể mở tin tìm người."
            )
        if booking.booking_mode == BookingMode.FIND_OPPONENT.value:
            allowed = booking.status == BookingStatus.PARTIALLY_PAID.value
            if current_utc >= _match_request_cutoff(booking):
                raise InvalidMatchStateError("Đã hết hạn tìm đối thủ cho lịch đặt này.")
        else:
            allowed = booking.status == BookingStatus.PAID.value
    elif booking.booking_mode == BookingMode.DIRECT_BOOKING.value:
        allowed = booking.status == BookingStatus.PAID.value
    else:
        allowed = booking.status in MATCHABLE_BOOKING_STATUSES
    if not allowed:
        raise InvalidMatchStateError(
            "Hãy hoàn thành khoản thanh toán bắt buộc trước khi mở kèo."
        )
    if _booking_has_started(booking, current_utc=current_utc):
        raise InvalidMatchStateError("Không thể mở kèo khi lịch sân đã bắt đầu.")


def _resolve_match_type(booking: Booking, requested_type: str | None) -> str:
    if booking.booking_mode == BookingMode.FIND_OPPONENT.value:
        expected = MatchType.FIND_OPPONENT.value
    elif booking.booking_mode == BookingMode.FIND_PLAYERS.value:
        expected = MatchType.FIND_PLAYERS.value
    else:
        expected = requested_type or ""
    if expected not in {item.value for item in MatchType}:
        raise MatchmakingError("Loại kèo không hợp lệ.")
    if requested_type and booking.booking_mode != BookingMode.DIRECT_BOOKING.value:
        if requested_type != expected:
            raise MatchmakingError("Loại kèo không khớp hình thức đặt sân.")
    return expected


def _resolve_player_configuration(
    *,
    booking: Booking,
    match_type: str,
    required_players: int | None,
) -> tuple[int | None, int]:
    if match_type == MatchType.FIND_OPPONENT.value:
        return None, 1
    total_players = booking.field.capacity
    normalized_required = (
        booking.requested_players
        if booking.booking_mode == BookingMode.FIND_PLAYERS.value
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
        raise InvalidMatchStateError("Lịch đặt sân của kèo không còn hiệu lực.")
    if _booking_has_started(match.booking, current_utc=current_utc):
        raise InvalidMatchStateError("Kèo đã đến giờ bắt đầu.")
    if (
        match.match_type == MatchType.FIND_OPPONENT.value
        and match.booking.uses_deposit_policy
        and match.booking.matchmaking_deadline is not None
        and current_utc >= match.booking.matchmaking_deadline
    ):
        raise InvalidMatchStateError("Đã hết hạn tìm đối thủ cho lịch đặt này.")


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
    match_started = _booking_has_started(match.booking, current_utc=current_utc)
    for participant in match.participants:
        payment_expired = (
            participant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
            and participant.payment_due_at is not None
            and participant.payment_due_at <= current_utc
        )
        unresolved_at_start = (
            match_started
            and participant.status
            in {
                MatchParticipantStatus.PENDING.value,
                MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
            }
        )
        if payment_expired or unresolved_at_start:
            _expire_participant(participant, current_utc=current_utc)
            if not match_started:
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


def _booking_has_started(booking: Booking, *, current_utc: datetime) -> bool:
    return _booking_start_utc(booking) <= current_utc


def _uses_current_match_policy(booking: Booking) -> bool:
    return bool(
        booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
        and booking.booking_mode == BookingMode.FIND_OPPONENT.value
        and booking.matchmaking_deadline is None
        and booking.funding_deadline is None
    )


def _match_request_cutoff(booking: Booking) -> datetime:
    if not booking.uses_deposit_policy and booking.funding_deadline is not None:
        return booking.funding_deadline
    if (
        booking.booking_mode == BookingMode.FIND_OPPONENT.value
        and booking.matchmaking_deadline is not None
    ):
        return booking.matchmaking_deadline
    return _booking_start_utc(booking)


def _booking_start_utc(booking: Booking) -> datetime:
    local_start = datetime.combine(booking.booking_date, booking.start_time)
    return local_start - timedelta(hours=7)


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


def _required_shared_contact_phone(
    value: str | None,
    *,
    share_contact: bool,
) -> str:
    normalized = normalize_phone(value)
    if not normalized:
        raise MatchmakingError("Vui lòng nhập số điện thoại có Zalo.")
    if len(normalized) > 20 or re.fullmatch(r"\+?[0-9][0-9 .-]{8,18}", normalized) is None:
        raise MatchmakingError("Số điện thoại không hợp lệ.")
    if not share_contact:
        raise MatchmakingError("Bạn cần đồng ý chia sẻ số liên hệ cho bên còn lại.")
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
