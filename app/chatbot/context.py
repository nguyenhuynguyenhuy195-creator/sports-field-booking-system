"""Read-only dynamic context for the logged-in USER.

Phase 2B. Static RAG explains policy; this explains the viewer's current state.

Three rules govern everything here.

1. **The frontend is not authorization.** ``page_type`` and ``resource_id``
   arrive from the browser and are treated as untrusted hints. Every resource
   is re-queried with the viewer's id in the WHERE clause, so a booking that
   belongs to someone else is indistinguishable from one that does not exist.

2. **Least privilege.** Only allowlisted fields leave this module, and only as
   JSON-safe primitives. No ORM object, no order/request/transaction id, no
   checkout URL, no other user's contact details, money or notes.

3. **Nothing is written.** Every query is a SELECT. No expiry job, payment
   refresh, refund processor or state transition is reachable from here, and
   the helpers reused from the services layer (``get_effective_booking_status``,
   ``match_accepts_actions``, ``effective_participant_status``,
   ``can_read_match_chat``, ``match_chat_is_active``) are all pure readers that
   deliberately avoid assigning to ORM attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    Field,
    FieldStatus,
    Match,
    MatchParticipant,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    UserRole,
    Venue,
    VenueStatus,
)
from app.services.booking import get_effective_booking_status
from app.services.match_chat import can_read_match_chat, match_chat_is_active
from app.services.matchmaking import (
    effective_participant_status,
    match_accepts_actions,
    match_view_status,
)


PAGE_GENERAL = "general"
PAGE_BOOKING_DETAIL = "booking_detail"
PAGE_MATCH_DETAIL = "match_detail"
PAGE_VENUE_DETAIL = "venue_detail"

# The complete allowlist. Anything else is refused outright.
ALLOWED_PAGE_TYPES = frozenset(
    {PAGE_GENERAL, PAGE_BOOKING_DETAIL, PAGE_MATCH_DETAIL, PAGE_VENUE_DETAIL}
)
RESOURCE_PAGE_TYPES = frozenset(
    {PAGE_BOOKING_DETAIL, PAGE_MATCH_DETAIL, PAGE_VENUE_DETAIL}
)

# Stable reasons, so tests and logs can assert on *why* nothing was resolved.
REASON_OK = "resolved"
REASON_GENERAL_PAGE = "general_page"
REASON_UNKNOWN_PAGE_TYPE = "unknown_page_type"
REASON_INVALID_RESOURCE_ID = "invalid_resource_id"
REASON_NOT_AVAILABLE = "not_available_to_viewer"
REASON_VIEWER_NOT_ELIGIBLE = "viewer_not_eligible"

# Cap on any single free-text field copied into the prompt, so one long
# owner-authored description cannot crowd out the curated evidence.
MAX_CONTEXT_TEXT = 400


@dataclass(frozen=True)
class ResolvedDynamicContext:
    """What the backend decided this viewer may see on this page."""

    page_type: str
    reason: str
    data: dict | None = None
    prompt_lines: tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return self.data is not None

    def to_dict(self) -> dict:
        return {
            "page_type": self.page_type,
            "reason": self.reason,
            "available": self.available,
            "data": self.data,
        }


def _unavailable(page_type: str, reason: str) -> ResolvedDynamicContext:
    return ResolvedDynamicContext(page_type=page_type, reason=reason)


# --------------------------------------------------------------- validation


def _valid_resource_id(value: object) -> int | None:
    """Strict: a real positive int. ``True`` is not 1 here."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _eligible_viewer(viewer: object) -> bool:
    """An active USER account. Owners and admins get no personal context."""
    if viewer is None:
        return False
    if not getattr(viewer, "is_authenticated", True):
        return False
    if getattr(viewer, "role", None) != UserRole.USER.value:
        return False
    if not getattr(viewer, "is_active", False):
        return False
    return isinstance(getattr(viewer, "id", None), int)


# ------------------------------------------------------------------- money


def _vnd(value: Decimal | int | float | None) -> str:
    """Money as a plain VND string. Never a float in the output."""
    amount = Decimal(str(value or 0))
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.quantize(Decimal("0.01")))


def _local(value: datetime | None) -> str | None:
    return value.isoformat(sep=" ", timespec="minutes") if value else None


VIETNAM_TIMEZONE = timezone(timedelta(hours=7))


def _aware_utc(now: datetime | None) -> datetime | None:
    """``now`` is UTC by contract; a naive value is taken as UTC.

    Made explicit because the services disagree about what ``now`` means:
    get_effective_booking_status normalises to Vietnam local,
    match_accepts_actions and effective_participant_status normalise to UTC,
    and all three do so correctly *only* for an aware datetime. Handing any of
    them a naive value would silently shift the answer by seven hours.
    """
    if now is None:
        return None
    return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)


def _vietnam_naive(now: datetime | None) -> datetime | None:
    """Vietnam-local naive, which is what match_chat_is_active compares against.

    That helper does no normalisation of its own and compares to
    ``datetime.combine(booking_date, end_time)``, so an aware value would raise
    on comparison rather than merely be wrong.
    """
    aware = _aware_utc(now)
    if aware is None:
        return None
    return aware.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)


# --------------------------------------------------------------- resolvers


def resolve_dynamic_context(
    *,
    viewer,
    page_type: object,
    resource_id: object = None,
    now: datetime | None = None,
) -> ResolvedDynamicContext:
    """Resolve backend-selected read-only context for this viewer.

    Never raises for an unknown page, a bad id, a missing resource or a
    resource belonging to someone else: all of those return an unavailable
    context, so the caller cannot distinguish them and neither can a probing
    user.
    """
    normalized_page = page_type if isinstance(page_type, str) else ""
    if normalized_page not in ALLOWED_PAGE_TYPES:
        return _unavailable(PAGE_GENERAL, REASON_UNKNOWN_PAGE_TYPE)
    if normalized_page == PAGE_GENERAL:
        return _unavailable(PAGE_GENERAL, REASON_GENERAL_PAGE)
    if not _eligible_viewer(viewer):
        return _unavailable(normalized_page, REASON_VIEWER_NOT_ELIGIBLE)

    identifier = _valid_resource_id(resource_id)
    if identifier is None:
        return _unavailable(normalized_page, REASON_INVALID_RESOURCE_ID)

    moment = _aware_utc(now)
    if normalized_page == PAGE_BOOKING_DETAIL:
        return _resolve_booking(viewer=viewer, booking_id=identifier, now=moment)
    if normalized_page == PAGE_MATCH_DETAIL:
        return _resolve_match(viewer=viewer, match_id=identifier, now=moment)
    return _resolve_venue(venue_id=identifier)


def _resolve_booking(*, viewer, booking_id: int, now) -> ResolvedDynamicContext:
    """A booking is private to the person who made it.

    Ownership is part of the query, not a check afterwards, so "not yours" and
    "does not exist" are the same outcome. Being a JOINED participant in the
    match attached to this booking grants nothing here.
    """
    booking = db.session.scalar(
        db.select(Booking).where(
            Booking.id == booking_id,
            Booking.user_id == viewer.id,
        )
    )
    if booking is None:
        return _unavailable(PAGE_BOOKING_DETAIL, REASON_NOT_AVAILABLE)

    money = _viewer_money(booking_id=booking.id, viewer_id=viewer.id)
    field_ = booking.field
    venue = field_.venue

    data = {
        "booking_code": booking.booking_code,
        "booking_mode": booking.booking_mode,
        "status": get_effective_booking_status(booking, now=now),
        "stored_status": booking.status,
        "venue_name": venue.name,
        "venue_address": venue.address,
        "field_name": field_.name,
        "sport": field_.field_type.sport.name if field_.field_type else None,
        "booking_date": booking.booking_date.isoformat(),
        "start_time": booking.start_time.strftime("%H:%M"),
        "end_time": booking.end_time.strftime("%H:%M"),
        # Aggregate figures: these cover every contributor, not just the viewer.
        "total_amount": _vnd(booking.total_amount),
        "deposit_amount": _vnd(booking.deposit_amount),
        "booking_paid_amount": _vnd(booking.paid_amount),
        # deposit_remaining is what is still owed ONLINE toward the deposit.
        "deposit_remaining": _vnd(booking.remaining_amount),
        # balance_due_at_venue is what is paid IN PERSON at the venue. These
        # two are different numbers and must never be conflated.
        "balance_due_at_venue": _vnd(booking.balance_due_at_venue),
        "cancellation_reason": booking.cancellation_reason,
        # Everything below is the viewer's own money only.
        "current_user_paid_gross": money["gross"],
        "current_user_paid_net": money["net"],
        "current_user_refunded": money["refunded"],
        "current_user_contributions": money["contributions"],
        "current_user_payments": money["payments"],
        "current_user_refunds": money["refunds"],
    }
    return ResolvedDynamicContext(
        page_type=PAGE_BOOKING_DETAIL,
        reason=REASON_OK,
        data=data,
        prompt_lines=_booking_lines(data),
    )


def _resolve_match(*, viewer, match_id: int, now) -> ResolvedDynamicContext:
    """Public match facts plus the viewer's own state — nothing else.

    The match detail page is public, so the public half is not a disclosure.
    The viewer-specific half is scoped to ``viewer.id`` at every step.
    """
    match = db.session.scalar(db.select(Match).where(Match.id == match_id))
    if match is None:
        return _unavailable(PAGE_MATCH_DETAIL, REASON_NOT_AVAILABLE)

    booking = match.booking
    field_ = booking.field
    venue = field_.venue

    joined_count = sum(
        participant.status == "JOINED" for participant in match.participants
    )
    participant = _viewer_participant(match=match, viewer_id=viewer.id)
    is_creator = match.creator_id == viewer.id

    # Always resolve the viewer's own money from their own contributions on
    # this booking. Scoping through participant.contribution_id alone lost the
    # creator entirely: create_match() never makes a MatchParticipant for them,
    # so the person who paid the booking deposit saw zero. A participant is
    # still narrowed to their own slot; anyone with no contributions gets
    # zeros, because the query is keyed on user_id either way.
    money = _viewer_money(
        booking_id=booking.id,
        viewer_id=viewer.id,
        contribution_id=(
            participant.contribution_id if participant is not None else None
        ),
    )

    data = {
        "match_id": match.id,
        "match_type": match.match_type,
        # The lifecycle a user is actually shown (PAST / CLOSED_LISTING /
        # INACTIVE / ...), shared with the web route so the two cannot drift.
        "match_status": match_view_status(match, now=now),
        # The raw column, kept separately for support questions only.
        "stored_match_status": match.status,
        "title": match.title,
        "skill_level": match.skill_level,
        "venue_name": venue.name,
        "venue_address": venue.address,
        "field_name": field_.name,
        "sport": field_.field_type.sport.name if field_.field_type else None,
        "booking_date": booking.booking_date.isoformat(),
        "start_time": booking.start_time.strftime("%H:%M"),
        "end_time": booking.end_time.strftime("%H:%M"),
        "required_players": match.required_players,
        "total_players": match.total_players,
        "joined_count": joined_count,
        "remaining_slots": max(match.required_players - joined_count, 0),
        "accepts_actions": match_accepts_actions(match, now=now),
        # Viewer's own state only.
        "is_creator": is_creator,
        "viewer_role": (
            "creator" if is_creator
            else ("participant" if participant is not None else "viewer")
        ),
        "viewer_participant_status": (
            effective_participant_status(participant, now=now)
            if participant is not None else None
        ),
        "chat_can_read": can_read_match_chat(match, viewer),
        # Read and send are separate rules: a closed room stays readable.
        # match_chat_is_active closes at the booking END time, not the start.
        "chat_can_send": (
            can_read_match_chat(match, viewer)
            and match_chat_is_active(match, now=_vietnam_naive(now))
        ),
        "current_user_paid_gross": money["gross"],
        "current_user_paid_net": money["net"],
        "current_user_refunded": money["refunded"],
        "current_user_contributions": money["contributions"],
        "current_user_payments": money["payments"],
        "current_user_refunds": money["refunds"],
    }
    return ResolvedDynamicContext(
        page_type=PAGE_MATCH_DETAIL,
        reason=REASON_OK,
        data=data,
        prompt_lines=_match_lines(data),
    )


def _resolve_venue(*, venue_id: int) -> ResolvedDynamicContext:
    """Public venue facts, with the same ACTIVE-only rule as the public page."""
    venue = db.session.scalar(
        db.select(Venue).where(
            Venue.id == venue_id,
            Venue.status == VenueStatus.ACTIVE.value,
        )
    )
    if venue is None:
        return _unavailable(PAGE_VENUE_DETAIL, REASON_NOT_AVAILABLE)

    data = {
        "venue_id": venue.id,
        "name": venue.name,
        "address": venue.address,
        "ward": venue.ward_name,
        "province": venue.province_name,
        "phone": venue.phone,
        "description": venue.description,
        "opening_time": venue.opening_time.strftime("%H:%M"),
        "closing_time": venue.closing_time.strftime("%H:%M"),
        # Venue has no `fields` relationship, so the active fields are queried
        # directly rather than walked off the ORM object.
        "fields": [
            {
                "name": item.name,
                "sport": item.field_type.sport.name if item.field_type else None,
                "field_type": item.field_type.name if item.field_type else None,
                "capacity": item.capacity,
            }
            for item in db.session.scalars(
                db.select(Field)
                .where(
                    Field.venue_id == venue.id,
                    Field.status == FieldStatus.ACTIVE.value,
                )
                .order_by(Field.name, Field.id)
            )
        ],
    }
    return ResolvedDynamicContext(
        page_type=PAGE_VENUE_DETAIL,
        reason=REASON_OK,
        data=data,
        prompt_lines=_venue_lines(data),
    )


# ------------------------------------------------------- viewer-scoped money


def _viewer_participant(*, match: Match, viewer_id: int) -> MatchParticipant | None:
    """The viewer's most recent request in this match, whatever its status."""
    candidates = [
        participant
        for participant in match.participants
        if participant.user_id == viewer_id
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.id)[-1]


def _viewer_money(
    *,
    booking_id: int,
    viewer_id: int,
    contribution_id: int | None = None,
) -> dict:
    """Every money figure here is the viewer's own.

    Scoped by ``user_id`` / ``payer_id`` / ``recipient_id`` — never by
    ``booking_id`` alone, which would expose whatever other contributors paid.

    Gross and net are reported separately on purpose: when a refund reaches
    SUCCESS the refund service already reduces ``contribution.amount_paid``,
    so subtracting refunds from the contribution total again would double
    count. Gross comes from the payments, net from the contributions.
    """
    contribution_filter = [
        BookingContribution.booking_id == booking_id,
        BookingContribution.user_id == viewer_id,
    ]
    if contribution_id is not None:
        contribution_filter.append(BookingContribution.id == contribution_id)

    contributions = list(
        db.session.scalars(
            db.select(BookingContribution)
            .where(*contribution_filter)
            .order_by(BookingContribution.id)
        )
    )
    contribution_ids = [item.id for item in contributions]

    payments: list[Payment] = []
    refunds: list[Refund] = []
    if contribution_ids:
        payments = list(
            db.session.scalars(
                db.select(Payment)
                .where(
                    Payment.booking_id == booking_id,
                    Payment.contribution_id.in_(contribution_ids),
                    # Ownership, not just association.
                    Payment.payer_id == viewer_id,
                )
                .order_by(Payment.id)
            )
        )
        refunds = list(
            db.session.scalars(
                db.select(Refund)
                .join(Refund.payment)
                .where(
                    Refund.booking_id == booking_id,
                    Refund.recipient_id == viewer_id,
                    Payment.contribution_id.in_(contribution_ids),
                    Payment.payer_id == viewer_id,
                )
                .order_by(Refund.id)
            )
        )

    gross = sum(
        (Decimal(item.amount) for item in payments
         if item.status == PaymentStatus.SUCCESS.value),
        Decimal("0"),
    )
    net = sum((Decimal(item.amount_paid) for item in contributions), Decimal("0"))
    refunded = sum(
        (Decimal(item.amount) for item in refunds
         if item.status == RefundStatus.SUCCESS.value),
        Decimal("0"),
    )

    return {
        "gross": _vnd(gross),
        "net": _vnd(net),
        "refunded": _vnd(refunded),
        "contributions": [
            {
                "type": item.contribution_type,
                "amount_due": _vnd(item.amount_due),
                "amount_paid": _vnd(item.amount_paid),
                "status": item.status,
            }
            for item in contributions
        ],
        # No order_id, request_id, provider_trans_id or checkout_url.
        "payments": [
            {
                "status": item.status,
                "amount": _vnd(item.amount),
                "paid_at": _local(item.paid_at),
            }
            for item in payments
        ],
        "refunds": [
            {
                "status": item.status,
                "amount": _vnd(item.amount),
                "refunded_at": _local(item.refunded_at),
            }
            for item in refunds
        ],
    }


# ----------------------------------------------------------- prompt rendering


def _booking_lines(data: dict) -> tuple[str, ...]:
    lines = [
        f"Mã lịch đặt: {data['booking_code']}",
        f"Trạng thái: {data['status']}",
        f"Hình thức đặt sân: {data['booking_mode']}",
        f"Sân: {data['field_name']} - {data['venue_name']}",
        f"Thời gian: {data['booking_date']} {data['start_time']}-{data['end_time']}",
        f"Tổng tiền sân: {data['total_amount']} VND",
        f"Khoản cọc phải đóng: {data['deposit_amount']} VND",
        f"Tổng đã đóng của cả lịch đặt (mọi người cộng lại):"
        f" {data['booking_paid_amount']} VND",
        f"Khoản cọc còn thiếu (phải trả trực tuyến):"
        f" {data['deposit_remaining']} VND",
        f"Số tiền trả tại sân: {data['balance_due_at_venue']} VND",
        f"Riêng người dùng này đã thanh toán thành công:"
        f" {data['current_user_paid_gross']} VND",
        f"Riêng người dùng này còn được ghi nhận sau hoàn tiền:"
        f" {data['current_user_paid_net']} VND",
        f"Riêng người dùng này đã được hoàn: {data['current_user_refunded']} VND",
    ]
    if data.get("cancellation_reason"):
        lines.append(f"Lý do hủy: {data['cancellation_reason']}")
    lines.extend(_money_status_lines(data))
    return tuple(lines)


def _match_lines(data: dict) -> tuple[str, ...]:
    lines = [
        f"Kèo: {data['title']}",
        f"Loại kèo: {data['match_type']}",
        f"Trạng thái kèo: {data['match_status']}",
        f"Sân: {data['field_name']} - {data['venue_name']}",
        f"Thời gian: {data['booking_date']} {data['start_time']}-{data['end_time']}",
        f"Đã tham gia: {data['joined_count']}/{data['required_players']}",
        f"Còn thiếu: {data['remaining_slots']}",
        f"Kèo còn nhận thao tác: {'có' if data['accepts_actions'] else 'không'}",
        f"Vai trò của người dùng này: {data['viewer_role']}",
        f"Trạng thái tham gia của người dùng này:"
        f" {data['viewer_participant_status'] or 'chưa tham gia'}",
        f"Người dùng này xem được phòng chat:"
        f" {'có' if data['chat_can_read'] else 'không'}",
        f"Người dùng này gửi được tin nhắn:"
        f" {'có' if data['chat_can_send'] else 'không'}",
        f"Riêng người dùng này đã thanh toán thành công:"
        f" {data['current_user_paid_gross']} VND",
        f"Riêng người dùng này đã được hoàn: {data['current_user_refunded']} VND",
    ]
    lines.extend(_money_status_lines(data))
    return tuple(lines)


def _money_status_lines(data: dict) -> list[str]:
    """Statuses of the viewer's OWN payments and refunds.

    Shared by booking and match context so both can answer "thanh toán của tôi
    đang ở trạng thái gì?" and "hoàn tiền của tôi đã xong chưa?".

    Statuses and amounts only. The DTO deliberately never carries order ids,
    request ids, provider transaction ids, checkout URLs or result codes, so
    there is nothing here that could identify or replay a transaction.
    """
    lines: list[str] = []
    for item in data.get("current_user_contributions") or []:
        lines.append(
            f"Khoản phải đóng của người dùng này ({item['type']}):"
            f" cần {item['amount_due']} VND, đã đóng {item['amount_paid']} VND,"
            f" trạng thái {item['status']}"
        )
    for item in data.get("current_user_payments") or []:
        when = f" lúc {item['paid_at']}" if item.get("paid_at") else ""
        lines.append(
            f"Giao dịch thanh toán của người dùng này: {item['amount']} VND"
            f" - trạng thái {item['status']}{when}"
        )
    for item in data.get("current_user_refunds") or []:
        when = f" lúc {item['refunded_at']}" if item.get("refunded_at") else ""
        lines.append(
            f"Khoản hoàn tiền của người dùng này: {item['amount']} VND"
            f" - trạng thái {item['status']}{when}"
        )
    return lines


def _venue_lines(data: dict) -> tuple[str, ...]:
    location = ", ".join(
        part for part in (data["address"], data.get("ward"), data.get("province"))
        if part
    )
    lines = [
        f"Cơ sở: {data['name']}",
        f"Địa chỉ: {location}",
        f"Giờ mở cửa: {data['opening_time']}-{data['closing_time']}",
    ]
    if data.get("phone"):
        lines.append(f"Điện thoại cơ sở: {data['phone']}")
    if data.get("description"):
        # Owner-authored free text. Truncated so one venue cannot dominate the
        # prompt; boundary neutralisation happens where the block is rendered.
        lines.append(f"Mô tả cơ sở: {data['description'][:MAX_CONTEXT_TEXT]}")
    for item in data["fields"]:
        lines.append(
            f"Sân: {item['name']} - {item['field_type'] or ''}"
            f" ({item['sport'] or ''}), sức chứa {item['capacity']}"
        )
    return tuple(lines)


__all__ = [
    "ALLOWED_PAGE_TYPES",
    "PAGE_BOOKING_DETAIL",
    "PAGE_GENERAL",
    "PAGE_MATCH_DETAIL",
    "PAGE_VENUE_DETAIL",
    "REASON_GENERAL_PAGE",
    "REASON_INVALID_RESOURCE_ID",
    "REASON_NOT_AVAILABLE",
    "REASON_OK",
    "REASON_UNKNOWN_PAGE_TYPE",
    "REASON_VIEWER_NOT_ELIGIBLE",
    "RESOURCE_PAGE_TYPES",
    "ResolvedDynamicContext",
    "resolve_dynamic_context",
]
