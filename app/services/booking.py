from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
    BookingPriceDetail,
    BookingStatus,
    ContributionStatus,
    Field,
    FieldType,
    FieldMaintenance,
    FieldMaintenanceStatus,
    FieldStatus,
    Refund,
    PlayFormat,
    SportCode,
    User,
    UserRole,
    VenueStatus,
)

from .contribution import (
    DEPOSIT_RATE,
    ContributionError,
    add_initial_contributions,
    build_contribution_plan,
    calculate_deposit_amount,
)
from .locking import with_update_lock
from .maintenance import current_vietnam_datetime
from .pricing import PriceQuote, PricingError, calculate_price_quote


VIETNAM_TIMEZONE = timezone(timedelta(hours=7))
ALWAYS_OCCUPYING_STATUSES = (
    BookingStatus.PARTIALLY_PAID.value,
    BookingStatus.PAID.value,
    BookingStatus.REFUND_PENDING.value,
)


class BookingError(ValueError):
    """Base error for booking business rules."""


class BookingNotFoundError(BookingError):
    """Raised when a booking or bookable field does not exist."""


class BookingPermissionError(BookingError):
    """Raised when a user acts on a booking without permission."""


class BookingUnavailableError(BookingError):
    """Raised when a requested field interval is unavailable."""


class InvalidBookingStateError(BookingError):
    """Raised when a booking state transition is not allowed."""


def create_booking(
    *,
    user: User,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    booking_mode: str,
    play_format: str | None = None,
    requested_players: int | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Booking:
    _validate_booker(user)
    normalized_mode = _validate_booking_mode(booking_mode)
    normalized_note = _normalize_optional_text(note, field_name="Ghi chú")
    current_local = _normalize_local_datetime(now)
    current_utc = _local_to_utc(current_local)

    field = _get_bookable_field(field_id=field_id, lock=True)
    _validate_field_is_active(field)
    normalized_play_format, normalized_requested_players = (
        _validate_booking_configuration(
            field=field,
            booking_mode=normalized_mode,
            play_format=play_format,
            requested_players=requested_players,
        )
    )
    _validate_booking_time(
        field=field,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        booking_mode=normalized_mode,
        current_local=current_local,
    )

    _expire_stale_bookings_for_field(field_id=field.id, now_utc=current_utc)
    if _maintenance_overlap_exists(
        field_id=field.id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
    ):
        raise BookingUnavailableError(
            "Khoảng giờ này đang được khóa để bảo trì sân."
        )
    if _booking_overlap_exists(
        field_id=field.id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        now_utc=current_utc,
    ):
        raise BookingUnavailableError(
            "Khoảng giờ này đã có người đặt hoặc đang chờ xử lý."
        )

    try:
        quote = calculate_price_quote(
            field_id=field.id,
            day_of_week=booking_date.weekday(),
            start_time=start_time,
            end_time=end_time,
        )
    except PricingError as exc:
        raise BookingError(str(exc)) from exc
    try:
        deposit_amount = calculate_deposit_amount(quote.total)
        contribution_plan = build_contribution_plan(
            booking_mode=normalized_mode,
            deposit_amount=deposit_amount,
            requested_players=normalized_requested_players,
        )
    except ContributionError as exc:
        raise BookingError(str(exc)) from exc

    start_at_local = datetime.combine(booking_date, start_time)
    matchmaking_deadline = None
    funding_deadline = None
    if normalized_mode == BookingMode.FIND_OPPONENT.value:
        matchmaking_deadline = _local_to_utc(
            start_at_local - timedelta(hours=12)
        )
        funding_deadline = matchmaking_deadline + timedelta(minutes=30)

    booking = Booking(
        booking_code=_generate_booking_code(current_utc),
        user_id=user.id,
        field_id=field.id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        booking_mode=normalized_mode,
        play_format=normalized_play_format,
        requested_players=normalized_requested_players,
        payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
        total_amount=quote.total,
        deposit_rate=DEPOSIT_RATE,
        deposit_amount=deposit_amount,
        paid_amount=Decimal("0.00"),
        cancellation_fee_amount=Decimal("0.00"),
        status=BookingStatus.CONFIRMED.value,
        initial_payment_due_at=current_utc + timedelta(minutes=15),
        matchmaking_deadline=matchmaking_deadline,
        funding_deadline=funding_deadline,
        note=normalized_note,
    )
    db.session.add(booking)
    db.session.flush()
    for segment in quote.segments:
        db.session.add(
            BookingPriceDetail(
                booking_id=booking.id,
                price_slot_id=segment.price_slot_id,
                start_time=segment.start_time,
                end_time=segment.end_time,
                duration_minutes=segment.duration_minutes,
                hourly_price=segment.hourly_price,
                subtotal=segment.subtotal,
            )
        )
    add_initial_contributions(
        booking=booking,
        creator_user_id=user.id,
        plan=contribution_plan,
    )

    _commit_booking("Không thể tạo booking lúc này. Vui lòng thử lại.")
    return booking


def quote_booking(
    *,
    user: User,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    booking_mode: str,
    play_format: str | None = None,
    requested_players: int | None = None,
    now: datetime | None = None,
) -> PriceQuote:
    """Validate a proposed interval and return a server-calculated quote.

    This is advisory for the booking screen. ``create_booking`` repeats every
    check while holding the field lock before it commits the reservation.
    """
    _validate_booker(user)
    normalized_mode = _validate_booking_mode(booking_mode)
    current_local = _normalize_local_datetime(now)
    current_utc = _local_to_utc(current_local)
    field = _get_bookable_field(field_id=field_id)
    _validate_field_is_active(field)
    _, normalized_requested_players = _validate_booking_configuration(
        field=field,
        booking_mode=normalized_mode,
        play_format=play_format,
        requested_players=requested_players,
    )
    _validate_booking_time(
        field=field,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        booking_mode=normalized_mode,
        current_local=current_local,
    )
    if _maintenance_overlap_exists(
        field_id=field.id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
    ):
        raise BookingUnavailableError(
            "Khoảng giờ này đang được khóa để bảo trì sân."
        )
    if _booking_overlap_exists(
        field_id=field.id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        now_utc=current_utc,
    ):
        raise BookingUnavailableError(
            "Khoảng giờ này đã có người đặt hoặc đang được giữ chỗ."
        )
    try:
        quote = calculate_price_quote(
            field_id=field.id,
            day_of_week=booking_date.weekday(),
            start_time=start_time,
            end_time=end_time,
        )
    except PricingError as exc:
        raise BookingError(str(exc)) from exc
    try:
        build_contribution_plan(
            booking_mode=normalized_mode,
            deposit_amount=calculate_deposit_amount(quote.total),
            requested_players=normalized_requested_players,
        )
    except ContributionError as exc:
        raise BookingError(str(exc)) from exc
    return quote


def get_booking_field(*, venue_id: int, field_id: int) -> Field:
    field = _get_bookable_field(field_id=field_id)
    if field.venue_id != venue_id:
        raise BookingNotFoundError("Không tìm thấy sân trong cơ sở này.")
    _validate_field_is_active(field)
    return field


def list_user_bookings(user_id: int) -> list[Booking]:
    return list(
        db.session.scalars(
            _booking_with_details_statement()
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        ).unique()
    )


def list_owner_bookings(owner_id: int) -> list[Booking]:
    return list(
        db.session.scalars(
            _booking_with_details_statement()
            .join(Booking.field)
            .join(Field.venue)
            .where(Field.venue.has(owner_id=owner_id))
            .order_by(Booking.created_at.desc())
        ).unique()
    )


def get_user_booking(*, booking_code: str, user_id: int) -> Booking:
    booking = db.session.scalar(
        _booking_with_details_statement().where(
            Booking.booking_code == booking_code
        )
    )
    if booking is None:
        raise BookingNotFoundError("Không tìm thấy booking.")
    if booking.user_id != user_id:
        raise BookingPermissionError("Bạn không có quyền xem booking này.")
    return booking


def get_owner_booking(*, booking_code: str, owner_id: int) -> Booking:
    booking = db.session.scalar(
        _booking_with_details_statement().where(
            Booking.booking_code == booking_code
        )
    )
    if booking is None:
        raise BookingNotFoundError("Không tìm thấy booking.")
    if booking.field.venue.owner_id != owner_id:
        raise BookingPermissionError("Bạn không có quyền quản lý booking này.")
    return booking


def cancel_user_booking(
    *,
    booking_code: str,
    user: User,
    now: datetime | None = None,
) -> Booking:
    booking = _lock_user_booking(booking_code=booking_code, user_id=user.id)
    current_local = _normalize_local_datetime(now)
    effective_status = get_effective_booking_status(booking, now=current_local)
    if effective_status == BookingStatus.EXPIRED.value:
        booking.status = BookingStatus.EXPIRED.value
        _commit_booking("Không thể cập nhật booking đã hết hạn.")
        raise InvalidBookingStateError("Booking đã hết hạn.")
    if booking.status not in {
        BookingStatus.PENDING.value,
        BookingStatus.CONFIRMED.value,
        BookingStatus.PARTIALLY_PAID.value,
    }:
        raise InvalidBookingStateError(
            "Bạn chỉ có thể tự hủy booking chưa thanh toán đủ."
        )

    start_at = datetime.combine(booking.booking_date, booking.start_time)
    if start_at - current_local < timedelta(hours=2):
        raise InvalidBookingStateError(
            "Bạn chỉ có thể hủy trước giờ bắt đầu ít nhất 2 giờ."
        )

    if booking.status == BookingStatus.PARTIALLY_PAID.value:
        from .refund import RefundError, apply_funding_shortfall_refunds

        try:
            apply_funding_shortfall_refunds(
                booking=booking,
                reason="Người tạo hủy booking chưa góp đủ tiền.",
                now=_local_to_utc(current_local),
            )
        except RefundError as exc:
            raise InvalidBookingStateError(str(exc)) from exc
    else:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancellation_reason = "Người đặt sân chủ động hủy booking."
        _set_pending_contributions_status(
            booking_ids=[booking.id],
            status=ContributionStatus.WAIVED.value,
        )
    _commit_booking("Không thể hủy booking lúc này.")
    _attempt_momo_refunds(booking.id)
    return booking


def cancel_owner_booking(
    *,
    booking_code: str,
    owner: User,
    reason: str,
) -> Booking:
    _validate_owner(owner)
    normalized_reason = _normalize_required_text(reason, field_name="Lý do hủy")
    booking = _lock_owner_booking(booking_code=booking_code, owner_id=owner.id)
    if booking.status not in {
        BookingStatus.CONFIRMED.value,
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
    }:
        raise InvalidBookingStateError(
            "Chủ sân chỉ có thể hủy booking đang giữ chỗ hoặc đã thu tiền."
        )

    if Decimal(booking.paid_amount) > 0:
        from .refund import RefundError, apply_owner_cancellation_refunds

        try:
            apply_owner_cancellation_refunds(
                booking=booking,
                reason=normalized_reason,
            )
        except RefundError as exc:
            raise InvalidBookingStateError(str(exc)) from exc
    else:
        booking.status = BookingStatus.CANCELLED.value
        booking.cancellation_reason = normalized_reason
        _set_pending_contributions_status(
            booking_ids=[booking.id],
            status=ContributionStatus.WAIVED.value,
        )
    _commit_booking("Không thể hủy booking lúc này.")
    _attempt_momo_refunds(booking.id)
    return booking


def booking_blocks_time(
    *,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    now: datetime | None = None,
) -> bool:
    if start_time >= end_time:
        raise BookingError("Giờ kết thúc phải sau giờ bắt đầu.")
    return _booking_overlap_exists(
        field_id=field_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        now_utc=_normalize_utc_datetime_from_local(now),
    )


def get_effective_booking_status(
    booking: Booking,
    *,
    now: datetime | None = None,
) -> str:
    current_utc = _normalize_utc_datetime_from_local(now)
    if (
        booking.status == BookingStatus.CONFIRMED.value
        and booking.initial_payment_due_at is not None
        and booking.initial_payment_due_at <= current_utc
        and Decimal(booking.paid_amount) == Decimal("0.00")
    ):
        return BookingStatus.EXPIRED.value
    return booking.status


def expire_stale_bookings(*, now: datetime | None = None) -> int:
    """Persist expired pre-payment bookings; safe to run repeatedly."""
    current_utc = _normalize_utc_datetime(now)
    statement = db.select(Booking).where(
        Booking.status == BookingStatus.CONFIRMED.value,
        Booking.initial_payment_due_at.is_not(None),
        Booking.initial_payment_due_at <= current_utc,
        Booking.paid_amount == Decimal("0.00"),
    )
    statement = with_update_lock(statement, Booking)
    stale_bookings = list(db.session.scalars(statement))
    for booking in stale_bookings:
        booking.status = BookingStatus.EXPIRED.value
    if stale_bookings:
        _set_pending_contributions_status(
            booking_ids=[booking.id for booking in stale_bookings],
            status=ContributionStatus.EXPIRED.value,
        )
        _commit_booking("Không thể cập nhật các booking đã hết hạn.")
    return len(stale_bookings)


def _booking_with_details_statement():
    return db.select(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.field).joinedload(Field.venue),
        selectinload(Booking.price_details),
        selectinload(Booking.contributions).joinedload(BookingContribution.user),
        selectinload(Booking.contributions).selectinload(
            BookingContribution.payments
        ),
        selectinload(Booking.payments),
        selectinload(Booking.refunds).joinedload(Refund.recipient),
    )


def _get_bookable_field(*, field_id: int, lock: bool = False) -> Field:
    statement = (
        db.select(Field)
        .options(
            joinedload(Field.venue),
            joinedload(Field.field_type).joinedload(FieldType.sport),
        )
        .where(Field.id == field_id)
    )
    if lock:
        statement = with_update_lock(statement, Field)
    field = db.session.scalar(statement)
    if field is None:
        raise BookingNotFoundError("Không tìm thấy sân.")
    return field


def _validate_field_is_active(field: Field) -> None:
    if field.status != FieldStatus.ACTIVE.value:
        raise BookingUnavailableError("Sân này chưa nhận đặt lịch.")
    if field.venue.status != VenueStatus.ACTIVE.value:
        raise BookingUnavailableError("Cơ sở này chưa nhận đặt lịch.")


def _validate_booking_time(
    *,
    field: Field,
    booking_date: date,
    start_time: time,
    end_time: time,
    booking_mode: str,
    current_local: datetime,
) -> None:
    if not isinstance(booking_date, date):
        raise BookingError("Ngày đặt sân không hợp lệ.")
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise BookingError("Khoảng giờ đặt sân không hợp lệ.")
    if start_time >= end_time:
        raise BookingError("Giờ kết thúc phải sau giờ bắt đầu.")
    if any(
        value.minute not in {0, 30} or value.second != 0 or value.microsecond != 0
        for value in (start_time, end_time)
    ):
        raise BookingError("Giờ bắt đầu và kết thúc phải theo bước 30 phút.")

    start_at = datetime.combine(booking_date, start_time)
    end_at = datetime.combine(booking_date, end_time)
    if end_at - start_at < timedelta(minutes=60):
        raise BookingError("Thời lượng đặt sân tối thiểu là 60 phút.")
    if (
        start_time < field.venue.opening_time
        or end_time > field.venue.closing_time
    ):
        raise BookingUnavailableError(
            "Khoảng giờ phải nằm trong giờ hoạt động của cơ sở."
        )
    if start_at <= current_local:
        raise BookingError("Thời gian đặt sân phải ở trong tương lai.")
    if start_at > current_local + timedelta(days=30):
        raise BookingError("Chỉ được đặt sân trước tối đa 30 ngày.")

    minimum_lead = (
        timedelta(hours=1)
        if booking_mode
        in {
            BookingMode.DIRECT_BOOKING.value,
            BookingMode.FIND_PLAYERS.value,
        }
        else timedelta(hours=24)
    )
    if start_at - current_local < minimum_lead:
        hours = (
            1
            if booking_mode
            in {
                BookingMode.DIRECT_BOOKING.value,
                BookingMode.FIND_PLAYERS.value,
            }
            else 24
        )
        raise BookingError(
            f"Hình thức này phải được đặt trước ít nhất {hours} giờ."
        )


def _maintenance_overlap_exists(
    *,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    return (
        db.session.scalar(
            db.select(FieldMaintenance.id)
            .where(
                FieldMaintenance.field_id == field_id,
                FieldMaintenance.maintenance_date == booking_date,
                FieldMaintenance.status == FieldMaintenanceStatus.ACTIVE.value,
                FieldMaintenance.start_time < end_time,
                FieldMaintenance.end_time > start_time,
            )
            .limit(1)
        )
        is not None
    )


def _booking_overlap_exists(
    *,
    field_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    now_utc: datetime,
) -> bool:
    occupancy_condition = or_(
        Booking.status.in_(ALWAYS_OCCUPYING_STATUSES),
        and_(
            Booking.status == BookingStatus.CONFIRMED.value,
            or_(
                Booking.initial_payment_due_at.is_(None),
                Booking.initial_payment_due_at > now_utc,
            ),
        ),
    )
    return (
        db.session.scalar(
            db.select(Booking.id)
            .where(
                Booking.field_id == field_id,
                Booking.booking_date == booking_date,
                Booking.start_time < end_time,
                Booking.end_time > start_time,
                occupancy_condition,
            )
            .limit(1)
        )
        is not None
    )


def _expire_stale_bookings_for_field(*, field_id: int, now_utc: datetime) -> None:
    stale_bookings = list(
        db.session.scalars(
            db.select(Booking).where(
                Booking.field_id == field_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.initial_payment_due_at.is_not(None),
                Booking.initial_payment_due_at <= now_utc,
                Booking.paid_amount == Decimal("0.00"),
            )
        )
    )
    for booking in stale_bookings:
        booking.status = BookingStatus.EXPIRED.value
    if stale_bookings:
        _set_pending_contributions_status(
            booking_ids=[booking.id for booking in stale_bookings],
            status=ContributionStatus.EXPIRED.value,
        )


def _set_pending_contributions_status(*, booking_ids: list[int], status: str) -> None:
    if not booking_ids:
        return
    contributions = db.session.scalars(
        db.select(BookingContribution).where(
            BookingContribution.booking_id.in_(booking_ids),
            BookingContribution.status == ContributionStatus.PENDING.value,
        )
    )
    for contribution in contributions:
        contribution.status = status


def _lock_owner_booking(*, booking_code: str, owner_id: int) -> Booking:
    booking = db.session.scalar(
        db.select(Booking)
        .options(joinedload(Booking.field).joinedload(Field.venue))
        .where(Booking.booking_code == booking_code)
    )
    if booking is None:
        raise BookingNotFoundError("Không tìm thấy booking.")
    _lock_field(field_id=booking.field_id)
    statement = with_update_lock(
        db.select(Booking)
        .options(joinedload(Booking.field).joinedload(Field.venue))
        .where(Booking.id == booking.id),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking.field.venue.owner_id != owner_id:
        raise BookingPermissionError("Bạn không có quyền quản lý booking này.")
    return booking


def _lock_user_booking(*, booking_code: str, user_id: int) -> Booking:
    booking = db.session.scalar(
        db.select(Booking).where(Booking.booking_code == booking_code)
    )
    if booking is None:
        raise BookingNotFoundError("Không tìm thấy booking.")
    _lock_field(field_id=booking.field_id)
    statement = with_update_lock(
        db.select(Booking).where(Booking.id == booking.id),
        Booking,
    )
    booking = db.session.scalar(statement)
    if booking.user_id != user_id:
        raise BookingPermissionError("Bạn không có quyền quản lý booking này.")
    return booking


def _lock_field(*, field_id: int) -> Field:
    statement = with_update_lock(
        db.select(Field).where(Field.id == field_id),
        Field,
    )
    field = db.session.scalar(statement)
    if field is None:
        raise BookingNotFoundError("Không tìm thấy sân.")
    return field


def _validate_booker(user: User) -> None:
    if user.role not in {UserRole.USER.value, UserRole.OWNER.value}:
        raise BookingPermissionError("Tài khoản này không thể tạo booking.")


def _validate_owner(owner: User) -> None:
    if owner.role != UserRole.OWNER.value:
        raise BookingPermissionError("Chỉ chủ sân được xử lý booking.")


def _validate_booking_mode(booking_mode: str) -> str:
    valid_modes = {mode.value for mode in BookingMode}
    if booking_mode not in valid_modes:
        raise BookingError("Hình thức booking không hợp lệ.")
    return booking_mode


def _validate_booking_configuration(
    *,
    field: Field,
    booking_mode: str,
    play_format: str | None,
    requested_players: int | None,
) -> tuple[str | None, int | None]:
    normalized_play_format = (play_format or "").strip().upper() or None
    sport_code = field.field_type.sport.code

    if sport_code == SportCode.FOOTBALL.value:
        if normalized_play_format is not None:
            raise BookingError("Booking bóng đá không chọn đánh đơn hoặc đánh đôi.")
        maximum_players = max(field.capacity - 1, 0)
    else:
        if normalized_play_format not in {item.value for item in PlayFormat}:
            raise BookingError("Vui lòng chọn đánh đơn hoặc đánh đôi.")
        if (
            normalized_play_format == PlayFormat.SINGLES.value
            and booking_mode == BookingMode.FIND_PLAYERS.value
        ):
            raise BookingError("Đánh đơn chỉ hỗ trợ đặt trực tiếp hoặc tìm đối thủ.")
        maximum_players = (
            1
            if normalized_play_format == PlayFormat.SINGLES.value
            else 3
        )

    if booking_mode == BookingMode.FIND_PLAYERS.value:
        if (
            isinstance(requested_players, bool)
            or not isinstance(requested_players, int)
            or requested_players < 1
        ):
            raise BookingError("Số người muốn tìm phải từ 1 trở lên.")
        if requested_players > maximum_players:
            raise BookingError(
                f"Số người muốn tìm không được vượt quá {maximum_players}."
            )
        return normalized_play_format, requested_players
    if requested_players is not None:
        raise BookingError(
            "Số người muốn tìm chỉ dùng cho hình thức tìm thêm người."
        )
    return normalized_play_format, None


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    normalized = " ".join((value or "").split())
    if not normalized:
        return None
    if len(normalized) > 500:
        raise BookingError(f"{field_name} tối đa 500 ký tự.")
    return normalized


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = _normalize_optional_text(value, field_name=field_name)
    if normalized is None:
        raise BookingError(f"Vui lòng nhập {field_name.lower()}.")
    return normalized


def _normalize_local_datetime(value: datetime | None) -> datetime:
    if value is None:
        return current_vietnam_datetime()
    if value.tzinfo is not None:
        return value.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)
    return value


def _normalize_utc_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _normalize_utc_datetime_from_local(value: datetime | None) -> datetime:
    return _local_to_utc(_normalize_local_datetime(value))


def _local_to_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=VIETNAM_TIMEZONE)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def _generate_booking_code(current_utc: datetime) -> str:
    return f"BK{current_utc:%Y%m%d%H%M%S}{uuid4().hex[:8].upper()}"


def _commit_booking(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise BookingError(message) from exc


def _attempt_momo_refunds(booking_id: int) -> None:
    from .refund import RefundError, process_pending_momo_refunds

    try:
        process_pending_momo_refunds(booking_id=booking_id)
    except RefundError:
        # The durable PENDING record is retried by the refunds CLI command.
        db.session.rollback()
