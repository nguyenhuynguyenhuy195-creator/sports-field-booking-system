from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingPaymentPolicy,
    BookingStatus,
    ContributionStatus,
    Field,
    FieldType,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    MatchType,
    OwnerApplication,
    OwnerApplicationStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    Sport,
    User,
    UserRole,
    UserStatus,
    Venue,
    VenueStatus,
)

from .locking import with_update_lock
from .administrative_unit import (
    AdministrativeUnitError,
    list_provinces,
    list_wards,
    resolve_administrative_address,
    resolve_province,
)
from app.models.user import utc_now


ADMIN_PAGE_SIZE = 20
ADMIN_MONITORING_PAGE_SIZE = 6
ADMIN_BOOKING_PAGE_SIZE = 6
ADMIN_MATCH_PAGE_SIZE = 6
ADMIN_VENUE_PAGE_SIZE = 10
ADMIN_MATCH_EFFECTIVE_ENDED_STATUS = "ENDED"
ADMIN_MATCH_OPERATIONAL_STATUSES = frozenset(
    {
        MatchStatus.OPEN.value,
        MatchStatus.FULL.value,
        MatchStatus.CONFIRMED.value,
    }
)


class AdminError(ValueError):
    """Base error for administrator business rules."""


class AdminPermissionError(AdminError):
    """Raised when a non-admin invokes an administrator service."""


class AdminAccountNotFoundError(AdminError):
    """Raised when the selected account does not exist."""


class InvalidAdminAccountActionError(AdminError):
    """Raised when an account status transition is unsafe or unsupported."""


@dataclass(frozen=True)
class AdminDashboardSummary:
    total_accounts: int
    active_accounts: int
    locked_accounts: int
    pending_owner_applications: int
    pending_venues: int
    total_bookings: int
    today_bookings: int
    active_bookings: int
    pending_payments: int
    failed_payments: int
    pending_refunds: int
    issues_requiring_attention: int
    open_matches: int
    successful_deposit_amount: Decimal
    successful_refund_amount: Decimal


@dataclass(frozen=True)
class AdminMonitoringSummary:
    incomplete_deposit_bookings: int
    payment_issues: int
    pending_refunds: int
    open_matches: int


@dataclass(frozen=True)
class AdminAccountSummary:
    total: int
    active: int
    locked: int
    users: int
    owners: int
    administrators: int


@dataclass(frozen=True)
class AdminAccountDetail:
    account: User
    latest_owner_application: OwnerApplication | None
    venue_count: int
    booking_count: int


@dataclass(frozen=True)
class AdminFieldLocationSummary:
    field: Field
    total_bookings: int
    incomplete_deposit_bookings: int


@dataclass(frozen=True)
class AdminVenueLocationSummary:
    venue: Venue
    fields: tuple[AdminFieldLocationSummary, ...]
    total_bookings: int


@dataclass(frozen=True)
class AdminPage:
    items: tuple[Any, ...]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


@dataclass(frozen=True)
class AdminBookingListItem:
    booking: Booking
    attention_label: str | None
    attention_kind: str | None


@dataclass(frozen=True)
class AdminBookingFilterOptions:
    provinces: tuple[Any, ...]
    wards: tuple[Any, ...]
    venues: tuple[Venue, ...]
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class AdminMatchListItem:
    match: Match
    effective_status: str
    total_participants: int
    joined_participants: int
    pending_participants: int
    awaiting_payment_participants: int
    closed_participants: int


@dataclass(frozen=True)
class AdminMatchDetail:
    match: Match
    effective_status: str
    total_participants: int
    joined_participants: int
    pending_participants: int
    awaiting_payment_participants: int
    closed_participants: int
    historical_events: tuple[AdminHistoricalEvent, ...]


@dataclass(frozen=True)
class AdminContributionBreakdown:
    contribution: BookingContribution
    gross_successful_payment_amount: Decimal
    successful_refund_amount: Decimal
    history_net_amount: Decimal
    requires_reconciliation: bool
    legacy_history_only: bool


@dataclass(frozen=True)
class AdminPaymentHistoryItem:
    payment: Payment
    related_refunds: tuple[Refund, ...]


@dataclass(frozen=True)
class AdminHistoricalEvent:
    occurred_at: datetime
    event_type: str
    record: Any


@dataclass(frozen=True)
class AdminMatchContext:
    match: Match
    total_participants: int
    joined_participants: int
    pending_participants: int
    closed_participants: int


@dataclass(frozen=True)
class AdminBookingDetail:
    booking: Booking
    contributions: tuple[AdminContributionBreakdown, ...]
    payments: tuple[AdminPaymentHistoryItem, ...]
    refunds: tuple[Refund, ...]
    match_context: AdminMatchContext | None
    historical_events: tuple[AdminHistoricalEvent, ...]
    payment_attention: tuple[Payment, ...]
    refund_attention: tuple[Refund, ...]
    missing_payment_history_kind: str | None
    financial_history_requires_reconciliation: bool


def get_admin_dashboard_summary() -> AdminDashboardSummary:
    pending_owner_applications = _count(
        OwnerApplication,
        OwnerApplication.status == OwnerApplicationStatus.PENDING.value,
    )
    pending_venues = _count(
        Venue,
        Venue.status == VenueStatus.PENDING.value,
    )
    pending_payments = _count(
        Payment,
        Payment.status == PaymentStatus.PENDING.value,
    )
    failed_payments = _count(
        Payment,
        Payment.status == PaymentStatus.FAILED.value,
    )
    pending_refunds = _count(
        Refund,
        Refund.status.in_(
            {RefundStatus.PENDING.value, RefundStatus.PROCESSING.value}
        ),
    )

    return AdminDashboardSummary(
        total_accounts=_count(User),
        active_accounts=_count(User, User.status == UserStatus.ACTIVE.value),
        locked_accounts=_count(User, User.status == UserStatus.LOCKED.value),
        pending_owner_applications=pending_owner_applications,
        pending_venues=pending_venues,
        total_bookings=_count(Booking),
        today_bookings=_count(Booking, Booking.booking_date == date.today()),
        active_bookings=_count(
            Booking,
            Booking.status.in_(
                {
                    BookingStatus.CONFIRMED.value,
                    BookingStatus.PARTIALLY_PAID.value,
                    BookingStatus.PAID.value,
                    BookingStatus.REFUND_PENDING.value,
                }
            ),
        ),
        pending_payments=pending_payments,
        failed_payments=failed_payments,
        pending_refunds=pending_refunds,
        issues_requiring_attention=(
            pending_owner_applications
            + pending_venues
            + pending_payments
            + failed_payments
            + pending_refunds
        ),
        open_matches=_count(Match, Match.status == MatchStatus.OPEN.value),
        successful_deposit_amount=_sum_amount(
            Payment.amount,
            Payment.status == PaymentStatus.SUCCESS.value,
        ),
        successful_refund_amount=_sum_amount(
            Refund.amount,
            Refund.status == RefundStatus.SUCCESS.value,
        ),
    )


def get_admin_monitoring_summary() -> AdminMonitoringSummary:
    return AdminMonitoringSummary(
        incomplete_deposit_bookings=_count(
            Booking,
            Booking.status.in_(
                {
                    BookingStatus.CONFIRMED.value,
                    BookingStatus.PARTIALLY_PAID.value,
                }
            ),
            Booking.paid_amount < Booking.deposit_amount,
        ),
        payment_issues=_count(
            Payment,
            Payment.status.in_(
                {PaymentStatus.PENDING.value, PaymentStatus.FAILED.value}
            ),
        ),
        pending_refunds=_count(
            Refund,
            Refund.status.in_(
                {RefundStatus.PENDING.value, RefundStatus.PROCESSING.value}
            ),
        ),
        open_matches=_count(Match, Match.status == MatchStatus.OPEN.value),
    )


def get_admin_account_summary() -> AdminAccountSummary:
    return AdminAccountSummary(
        total=_count(User),
        active=_count(User, User.status == UserStatus.ACTIVE.value),
        locked=_count(User, User.status == UserStatus.LOCKED.value),
        users=_count(User, User.role == UserRole.USER.value),
        owners=_count(User, User.role == UserRole.OWNER.value),
        administrators=_count(User, User.role == UserRole.ADMIN.value),
    )


def list_admin_monitoring_provinces() -> tuple[str, ...]:
    location_province = func.coalesce(Venue.province_name, Venue.city)
    statement = (
        db.select(location_province)
        .where(location_province.is_not(None), location_province != "")
        .distinct()
        .order_by(location_province.asc())
    )
    return tuple(db.session.scalars(statement))


def list_admin_monitoring_wards(
    *,
    province: str | None = None,
) -> tuple[str, ...]:
    location_province = func.coalesce(Venue.province_name, Venue.city)
    location_ward = func.coalesce(Venue.ward_name, Venue.district)
    statement = db.select(location_ward).where(
        location_ward.is_not(None),
        location_ward != "",
    )
    if province:
        statement = statement.where(location_province == province)
    statement = statement.distinct().order_by(location_ward.asc())
    return tuple(value for value in db.session.scalars(statement) if value)


def list_admin_monitoring_locations(
    *,
    query: str | None = None,
    province: str | None = None,
    ward: str | None = None,
    page: int = 1,
) -> AdminPage:
    statement = db.select(Venue)
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Venue.name).like(pattern, escape="\\"),
                func.lower(Venue.address).like(pattern, escape="\\"),
                func.lower(
                    func.coalesce(Venue.province_name, Venue.city, "")
                ).like(pattern, escape="\\"),
                func.lower(
                    func.coalesce(Venue.ward_name, Venue.district, "")
                ).like(
                    pattern,
                    escape="\\",
                ),
            )
        )
    if province:
        statement = statement.where(
            func.coalesce(Venue.province_name, Venue.city) == province
        )
    if ward:
        statement = statement.where(
            func.coalesce(Venue.ward_name, Venue.district) == ward
        )

    normalized_page = max(page, 1)
    pagination = db.paginate(
        statement.order_by(Venue.name.asc(), Venue.id.asc()),
        page=normalized_page,
        per_page=ADMIN_VENUE_PAGE_SIZE,
        error_out=False,
    )
    return AdminPage(
        items=_build_admin_venue_summaries(tuple(pagination.items)),
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
    )


def get_admin_monitoring_location(
    venue_id: int,
) -> AdminVenueLocationSummary | None:
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        return None
    return _build_admin_venue_summaries((venue,))[0]


def _build_admin_venue_summaries(
    venues: tuple[Venue, ...],
) -> tuple[AdminVenueLocationSummary, ...]:
    if not venues:
        return ()

    venue_ids = tuple(venue.id for venue in venues)
    fields = tuple(
        db.session.scalars(
            db.select(Field)
            .where(Field.venue_id.in_(venue_ids))
            .options(
                joinedload(Field.venue),
                joinedload(Field.field_type).joinedload(FieldType.sport),
            )
            .order_by(Field.venue_id.asc(), Field.name.asc(), Field.id.asc())
        )
    )
    incomplete_condition = (
        Booking.status.in_(
            {BookingStatus.CONFIRMED.value, BookingStatus.PARTIALLY_PAID.value}
        )
        & (Booking.paid_amount < Booking.deposit_amount)
    )
    field_ids = tuple(field.id for field in fields)
    booking_stats = {}
    if field_ids:
        booking_stats = {
            int(field_id): (int(total or 0), int(incomplete or 0))
            for field_id, total, incomplete in db.session.execute(
                db.select(
                    Booking.field_id,
                    func.count(Booking.id),
                    func.sum(case((incomplete_condition, 1), else_=0)),
                )
                .where(Booking.field_id.in_(field_ids))
                .group_by(Booking.field_id)
            )
        }

    fields_by_venue: dict[int, list[AdminFieldLocationSummary]] = {
        venue.id: [] for venue in venues
    }
    for field in fields:
        total, incomplete = booking_stats.get(field.id, (0, 0))
        fields_by_venue.setdefault(field.venue_id, []).append(
            AdminFieldLocationSummary(
                field=field,
                total_bookings=total,
                incomplete_deposit_bookings=incomplete,
            )
        )

    return tuple(
        AdminVenueLocationSummary(
            venue=venue,
            fields=tuple(fields_by_venue.get(venue.id, [])),
            total_bookings=sum(
                item.total_bookings for item in fields_by_venue.get(venue.id, [])
            ),
        )
        for venue in venues
    )


def get_admin_booking(booking_code: str) -> Booking:
    statement = (
        db.select(Booking)
        .where(Booking.booking_code == booking_code)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.field)
            .joinedload(Field.venue)
            .joinedload(Venue.owner),
            joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            selectinload(Booking.contributions).joinedload(
                BookingContribution.user
            ),
            selectinload(Booking.payments).joinedload(Payment.payer),
            selectinload(Booking.payments).joinedload(Payment.contribution),
            selectinload(Booking.refunds).joinedload(Refund.recipient),
            selectinload(Booking.refunds).joinedload(Refund.payment),
            joinedload(Booking.match).joinedload(Match.creator),
            joinedload(Booking.match)
            .selectinload(Match.participants)
            .joinedload(MatchParticipant.user),
        )
    )
    booking = db.session.scalar(statement)
    if booking is None:
        raise AdminError("Không tìm thấy lịch đặt sân cần theo dõi.")
    return booking


def get_admin_booking_detail(booking_code: str) -> AdminBookingDetail:
    """Build the read-only investigation model for one Booking."""
    booking = get_admin_booking(booking_code)
    payments = tuple(booking.payments)
    refunds = tuple(booking.refunds)

    refunds_by_payment: dict[int, list[Refund]] = {}
    for refund in refunds:
        refunds_by_payment.setdefault(refund.payment_id, []).append(refund)

    payment_items = tuple(
        AdminPaymentHistoryItem(
            payment=payment,
            related_refunds=tuple(refunds_by_payment.get(payment.id, ())),
        )
        for payment in payments
    )

    successful_payment_amounts: dict[int, Decimal] = {}
    for payment in payments:
        if payment.status == PaymentStatus.SUCCESS.value:
            successful_payment_amounts[payment.contribution_id] = (
                successful_payment_amounts.get(
                    payment.contribution_id,
                    Decimal("0.00"),
                )
                + Decimal(payment.amount)
            )

    successful_refund_amounts: dict[int, Decimal] = {}
    for refund in refunds:
        if refund.status != RefundStatus.SUCCESS.value:
            continue
        contribution_id = refund.payment.contribution_id
        successful_refund_amounts[contribution_id] = (
            successful_refund_amounts.get(contribution_id, Decimal("0.00"))
            + Decimal(refund.amount)
        )

    legacy_history_only = bool(
        booking.payment_policy == BookingPaymentPolicy.LEGACY_FULL_ONLINE.value
        and Decimal(booking.paid_amount) > 0
        and not payments
    )
    contribution_rows = []
    for contribution in booking.contributions:
        gross_amount = successful_payment_amounts.get(
            contribution.id,
            Decimal("0.00"),
        )
        refunded_amount = successful_refund_amounts.get(
            contribution.id,
            Decimal("0.00"),
        )
        history_net_amount = gross_amount - refunded_amount
        contribution_uses_legacy_history = bool(
            legacy_history_only and Decimal(contribution.amount_paid) > 0
        )
        contribution_rows.append(
            AdminContributionBreakdown(
                contribution=contribution,
                gross_successful_payment_amount=gross_amount,
                successful_refund_amount=refunded_amount,
                history_net_amount=history_net_amount,
                requires_reconciliation=bool(
                    not contribution_uses_legacy_history
                    and history_net_amount != Decimal(contribution.amount_paid)
                ),
                legacy_history_only=contribution_uses_legacy_history,
            )
        )

    missing_payment_history_kind = None
    if Decimal(booking.paid_amount) > 0 and not payments:
        missing_payment_history_kind = (
            "legacy"
            if booking.payment_policy
            == BookingPaymentPolicy.LEGACY_FULL_ONLINE.value
            else "investigate"
        )

    gross_successful_amount = sum(
        (
            Decimal(payment.amount)
            for payment in payments
            if payment.status == PaymentStatus.SUCCESS.value
        ),
        Decimal("0.00"),
    )
    successful_refund_amount = sum(
        (
            Decimal(refund.amount)
            for refund in refunds
            if refund.status == RefundStatus.SUCCESS.value
        ),
        Decimal("0.00"),
    )
    history_net_amount = gross_successful_amount - successful_refund_amount
    financial_history_requires_reconciliation = bool(
        missing_payment_history_kind == "investigate"
        or (
            not legacy_history_only
            and history_net_amount != Decimal(booking.paid_amount)
        )
        or any(row.requires_reconciliation for row in contribution_rows)
    )

    payment_attention = tuple(
        payment
        for payment in payments
        if payment.status
        in {
            PaymentStatus.PENDING.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.CANCELLED.value,
            PaymentStatus.EXPIRED.value,
        }
    )
    refund_attention = tuple(
        refund
        for refund in refunds
        if refund.status
        in {
            RefundStatus.PENDING.value,
            RefundStatus.PROCESSING.value,
            RefundStatus.FAILED.value,
        }
    )

    return AdminBookingDetail(
        booking=booking,
        contributions=tuple(contribution_rows),
        payments=payment_items,
        refunds=refunds,
        match_context=_admin_match_context(booking.match),
        historical_events=_admin_booking_historical_events(booking),
        payment_attention=payment_attention,
        refund_attention=refund_attention,
        missing_payment_history_kind=missing_payment_history_kind,
        financial_history_requires_reconciliation=(
            financial_history_requires_reconciliation
        ),
    )


def get_admin_match_detail(match_id: int) -> AdminMatchDetail:
    """Build a read-only investigation model for one Match."""
    statement = (
        db.select(Match)
        .where(Match.id == match_id)
        .options(
            joinedload(Match.creator),
            joinedload(Match.booking).joinedload(Booking.user),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            selectinload(Match.participants).joinedload(MatchParticipant.user),
            selectinload(Match.participants).joinedload(
                MatchParticipant.contribution
            ),
        )
    )
    match = db.session.scalar(statement)
    if match is None:
        raise AdminError("Không tìm thấy kèo chơi cần theo dõi.")

    current_utc = utc_now()
    counts = _admin_match_participant_counts(match)
    return AdminMatchDetail(
        match=match,
        effective_status=_admin_match_effective_status(
            match,
            current_utc=current_utc,
        ),
        total_participants=counts["total"],
        joined_participants=counts["joined"],
        pending_participants=counts["pending"],
        awaiting_payment_participants=counts["awaiting_payment"],
        closed_participants=counts["closed"],
        historical_events=_admin_match_historical_events(match),
    )


def list_admin_accounts(
    *,
    query: str | None = None,
    role: str | None = None,
    status: str | None = None,
    page: int = 1,
) -> AdminPage:
    statement = db.select(User)
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(User.full_name).like(pattern, escape="\\"),
                func.lower(User.email).like(pattern, escape="\\"),
                func.lower(func.coalesce(User.phone, "")).like(
                    pattern, escape="\\"
                ),
            )
        )
    if role:
        _require_choice(role, UserRole, "Vai trò")
        statement = statement.where(User.role == role)
    if status:
        _require_choice(status, UserStatus, "Trạng thái tài khoản")
        statement = statement.where(User.status == status)
    return _paginate(statement.order_by(User.created_at.desc(), User.id.desc()), page)


def get_admin_account_detail(account_id: int) -> AdminAccountDetail:
    account = db.session.get(User, account_id)
    if account is None:
        raise AdminAccountNotFoundError("Không tìm thấy tài khoản.")

    latest_owner_application = db.session.scalar(
        db.select(OwnerApplication)
        .where(OwnerApplication.user_id == account.id)
        .order_by(
            OwnerApplication.created_at.desc(),
            OwnerApplication.id.desc(),
        )
        .limit(1)
    )
    return AdminAccountDetail(
        account=account,
        latest_owner_application=latest_owner_application,
        venue_count=_count(Venue, Venue.owner_id == account.id),
        booking_count=_count(Booking, Booking.user_id == account.id),
    )


def set_admin_account_status(
    *,
    account_id: int,
    actor: User,
    new_status: str,
) -> User:
    if actor.role != UserRole.ADMIN.value:
        raise AdminPermissionError("Chỉ quản trị viên được thay đổi tài khoản.")
    if new_status not in {UserStatus.ACTIVE.value, UserStatus.LOCKED.value}:
        raise InvalidAdminAccountActionError(
            "Quản trị viên chỉ có thể khóa hoặc mở khóa tài khoản."
        )
    if account_id == actor.id:
        raise InvalidAdminAccountActionError(
            "Bạn không thể tự khóa hoặc thay đổi trạng thái tài khoản đang dùng."
        )

    account = db.session.scalar(
        with_update_lock(
            db.select(User).where(User.id == account_id),
            User,
        )
    )
    if account is None:
        raise AdminAccountNotFoundError("Không tìm thấy tài khoản.")
    if account.role == UserRole.ADMIN.value:
        raise InvalidAdminAccountActionError(
            "Tài khoản quản trị viên chỉ được xem, không thể khóa hoặc mở khóa."
        )
    if account.status == UserStatus.INACTIVE.value:
        raise InvalidAdminAccountActionError(
            "Tài khoản ngừng hoạt động không thể khóa hoặc mở khóa tại đây."
        )

    account.status = new_status
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise AdminError(
            "Không thể cập nhật tài khoản lúc này. Vui lòng thử lại."
        ) from exc
    return account


def list_admin_catalog() -> tuple[Sport, ...]:
    statement = (
        db.select(Sport)
        .options(selectinload(Sport.field_types))
        .order_by(Sport.name.asc())
    )
    return tuple(db.session.scalars(statement))


def get_admin_booking_filter_options(
    *,
    province_code: str | None = None,
    ward_code: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
) -> AdminBookingFilterOptions:
    """Build and validate the dependent filters for Booking Operations."""
    normalized_province = (province_code or "").strip()
    normalized_ward = (ward_code or "").strip()
    selected_province = None
    selected_ward = None

    if normalized_ward and not normalized_province:
        raise AdminError("Vui lòng chọn tỉnh hoặc thành phố trước phường/xã.")
    try:
        if normalized_ward:
            address = resolve_administrative_address(
                province_code=normalized_province,
                ward_code=normalized_ward,
            )
            selected_province = address.province
            selected_ward = address.ward
        elif normalized_province:
            selected_province = resolve_province(
                province_code=normalized_province
            )
    except AdministrativeUnitError as exc:
        raise AdminError(str(exc)) from exc

    provinces = list_provinces()
    wards = (
        list_wards(province_code=normalized_province)
        if selected_province is not None
        else ()
    )
    venues = tuple(
        db.session.scalars(db.select(Venue).order_by(Venue.name.asc(), Venue.id.asc()))
    )
    fields = tuple(
        db.session.scalars(
            db.select(Field)
            .options(
                joinedload(Field.venue),
                joinedload(Field.field_type).joinedload(FieldType.sport),
            )
            .order_by(Field.name.asc(), Field.id.asc())
        )
    )

    selected_venue = next(
        (venue for venue in venues if venue.id == venue_id),
        None,
    )
    if venue_id is not None and selected_venue is None:
        raise AdminError("Cơ sở được chọn không hợp lệ.")
    if selected_venue is not None and not _venue_matches_admin_location(
        selected_venue,
        selected_province,
        selected_ward,
    ):
        raise AdminError("Cơ sở không thuộc khu vực đã chọn.")

    if field_id is not None and selected_venue is None:
        raise AdminError("Vui lòng chọn cơ sở trước khi chọn sân.")
    selected_field = next(
        (field for field in fields if field.id == field_id),
        None,
    )
    if field_id is not None and (
        selected_field is None or selected_field.venue_id != selected_venue.id
    ):
        raise AdminError("Sân không thuộc cơ sở đã chọn.")

    return AdminBookingFilterOptions(
        provinces=provinces,
        wards=wards,
        venues=venues,
        fields=fields,
    )


def list_admin_booking_operations(
    *,
    query: str | None = None,
    status: str | None = None,
    sport_code: str | None = None,
    booking_date: date | None = None,
    province_code: str | None = None,
    ward_code: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    """Return the compact, read-only model for the dedicated booking list."""
    normalized_province = (province_code or "").strip()
    normalized_ward = (ward_code or "").strip()
    selected_province = None
    selected_ward = None
    try:
        if normalized_ward:
            address = resolve_administrative_address(
                province_code=normalized_province,
                ward_code=normalized_ward,
            )
            selected_province = address.province
            selected_ward = address.ward
        elif normalized_province:
            selected_province = resolve_province(
                province_code=normalized_province
            )
    except AdministrativeUnitError as exc:
        raise AdminError(str(exc)) from exc

    statement = (
        db.select(Booking)
        .join(User, User.id == Booking.user_id)
        .join(Field, Field.id == Booking.field_id)
        .join(Venue, Venue.id == Field.venue_id)
        .join(FieldType, FieldType.id == Field.field_type_id)
        .join(Sport, Sport.id == FieldType.sport_id)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.field).joinedload(Field.venue),
            joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
        )
    )
    search_query = (query or "").strip()[:100]
    if search_query:
        pattern = _contains_pattern(search_query)
        statement = statement.where(
            or_(
                Booking.booking_code.like(pattern, escape="\\"),
                User.full_name.like(pattern, escape="\\"),
                User.email.like(pattern, escape="\\"),
                Booking.payments.any(
                    Payment.order_id.like(pattern, escape="\\")
                ),
                Booking.refunds.any(
                    Refund.order_id.like(pattern, escape="\\")
                ),
            )
        )
    if status:
        _require_choice(status, BookingStatus, "Trạng thái lịch đặt sân")
        statement = statement.where(Booking.status == status)
    if sport_code:
        if db.session.scalar(
            db.select(Sport.id).where(Sport.code == sport_code)
        ) is None:
            raise AdminError("Bộ môn lọc không hợp lệ.")
        statement = statement.where(Sport.code == sport_code)
    if booking_date:
        statement = statement.where(Booking.booking_date == booking_date)
    if selected_province is not None:
        statement = statement.where(
            _admin_province_condition(selected_province)
        )
    if selected_ward is not None:
        statement = statement.where(_admin_ward_condition(selected_ward))
    if venue_id is not None:
        statement = statement.where(Venue.id == venue_id)
    if field_id is not None:
        statement = statement.where(Field.id == field_id)

    booking_page = _paginate(
        statement.order_by(Booking.created_at.desc(), Booking.id.desc()),
        page,
        per_page=ADMIN_BOOKING_PAGE_SIZE,
    )
    payment_states: dict[int, set[str]] = {}
    refund_states: dict[int, set[str]] = {}
    booking_ids = [booking.id for booking in booking_page.items]
    if booking_ids:
        for booking_id, payment_status in db.session.execute(
            db.select(Payment.booking_id, Payment.status).where(
                Payment.booking_id.in_(booking_ids),
                Payment.status.in_(
                    (
                        PaymentStatus.PENDING.value,
                        PaymentStatus.FAILED.value,
                        PaymentStatus.CANCELLED.value,
                        PaymentStatus.EXPIRED.value,
                    )
                ),
            )
        ):
            payment_states.setdefault(booking_id, set()).add(payment_status)
        for booking_id, refund_status in db.session.execute(
            db.select(Refund.booking_id, Refund.status).where(
                Refund.booking_id.in_(booking_ids),
                Refund.status.in_(
                    (
                        RefundStatus.PENDING.value,
                        RefundStatus.PROCESSING.value,
                        RefundStatus.FAILED.value,
                    )
                ),
            )
        ):
            refund_states.setdefault(booking_id, set()).add(refund_status)

    return AdminPage(
        items=tuple(
            _admin_booking_list_item(
                booking,
                payment_states.get(booking.id, set()),
                refund_states.get(booking.id, set()),
            )
            for booking in booking_page.items
        ),
        page=booking_page.page,
        per_page=booking_page.per_page,
        total=booking_page.total,
    )


def list_admin_match_operations(
    *,
    query: str | None = None,
    status: str | None = None,
    match_type: str | None = None,
    sport_code: str | None = None,
    booking_date: date | None = None,
    province_code: str | None = None,
    ward_code: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    """Return the compact, read-only model for dedicated Match Operations."""
    normalized_province = (province_code or "").strip()
    normalized_ward = (ward_code or "").strip()
    selected_province = None
    selected_ward = None
    try:
        if normalized_ward:
            address = resolve_administrative_address(
                province_code=normalized_province,
                ward_code=normalized_ward,
            )
            selected_province = address.province
            selected_ward = address.ward
        elif normalized_province:
            selected_province = resolve_province(
                province_code=normalized_province
            )
    except AdministrativeUnitError as exc:
        raise AdminError(str(exc)) from exc

    current_utc = utc_now()
    statement = (
        db.select(Match)
        .join(User, User.id == Match.creator_id)
        .join(Booking, Booking.id == Match.booking_id)
        .join(Field, Field.id == Booking.field_id)
        .join(Venue, Venue.id == Field.venue_id)
        .join(FieldType, FieldType.id == Field.field_type_id)
        .join(Sport, Sport.id == FieldType.sport_id)
        .options(
            joinedload(Match.creator),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            selectinload(Match.participants).joinedload(MatchParticipant.user),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        search_conditions = [
            func.lower(Match.title).like(pattern, escape="\\"),
            func.lower(Booking.booking_code).like(pattern, escape="\\"),
            func.lower(User.full_name).like(pattern, escape="\\"),
            func.lower(User.email).like(pattern, escape="\\"),
        ]
        if normalized_query.isdigit():
            search_conditions.append(Match.id == int(normalized_query))
        statement = statement.where(or_(*search_conditions))
    if status:
        if status == ADMIN_MATCH_EFFECTIVE_ENDED_STATUS:
            statement = statement.where(
                Match.status.in_(ADMIN_MATCH_OPERATIONAL_STATUSES),
                _admin_booking_has_ended_condition(current_utc),
            )
        else:
            _require_choice(status, MatchStatus, "Trạng thái kèo")
            statement = statement.where(Match.status == status)
            if status in ADMIN_MATCH_OPERATIONAL_STATUSES:
                statement = statement.where(
                    ~_admin_booking_has_ended_condition(current_utc)
                )
    if match_type:
        _require_choice(match_type, MatchType, "Loại kèo")
        statement = statement.where(Match.match_type == match_type)
    if sport_code:
        if db.session.scalar(
            db.select(Sport.id).where(Sport.code == sport_code)
        ) is None:
            raise AdminError("Bộ môn lọc không hợp lệ.")
        statement = statement.where(Sport.code == sport_code)
    if booking_date:
        statement = statement.where(Booking.booking_date == booking_date)
    if selected_province is not None:
        statement = statement.where(
            _admin_province_condition(selected_province)
        )
    if selected_ward is not None:
        statement = statement.where(_admin_ward_condition(selected_ward))
    if venue_id is not None:
        statement = statement.where(Venue.id == venue_id)
    if field_id is not None:
        statement = statement.where(Field.id == field_id)

    match_page = _paginate(
        statement.order_by(Match.created_at.desc(), Match.id.desc()),
        page,
        per_page=ADMIN_MATCH_PAGE_SIZE,
    )
    return AdminPage(
        items=tuple(
            _admin_match_list_item(match, current_utc=current_utc)
            for match in match_page.items
        ),
        page=match_page.page,
        per_page=match_page.per_page,
        total=match_page.total,
    )


def list_admin_bookings(
    *,
    query: str | None = None,
    status: str | None = None,
    sport_code: str | None = None,
    booking_date: date | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    focus: str | None = None,
    page: int = 1,
) -> AdminPage:
    statement = (
        db.select(Booking)
        .join(Field, Field.id == Booking.field_id)
        .join(FieldType, FieldType.id == Field.field_type_id)
        .join(Sport, Sport.id == FieldType.sport_id)
        .options(
            joinedload(Booking.user),
            joinedload(Booking.field).joinedload(Field.venue),
            joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            selectinload(Booking.contributions).joinedload(
                BookingContribution.user
            ),
            selectinload(Booking.payments).joinedload(Payment.payer),
            selectinload(Booking.payments).joinedload(Payment.contribution),
            selectinload(Booking.refunds).joinedload(Refund.recipient),
            selectinload(Booking.refunds).joinedload(Refund.payment),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Booking.booking_code).like(pattern, escape="\\"),
                func.lower(User.email).like(pattern, escape="\\"),
                Booking.payments.any(
                    func.lower(Payment.order_id).like(pattern, escape="\\")
                ),
                Booking.refunds.any(
                    func.lower(Refund.order_id).like(pattern, escape="\\")
                ),
            )
        ).join(User, User.id == Booking.user_id)
    if status:
        _require_choice(status, BookingStatus, "Trạng thái lịch đặt sân")
        statement = statement.where(Booking.status == status)
    if sport_code:
        statement = statement.where(Sport.code == sport_code)
    if booking_date:
        statement = statement.where(Booking.booking_date == booking_date)
    if venue_id:
        statement = statement.where(Field.venue_id == venue_id)
    if field_id:
        statement = statement.where(Field.id == field_id)
    if focus == "incomplete_deposit":
        statement = statement.where(Booking.paid_amount < Booking.deposit_amount)
    elif focus == "payment_issue":
        statement = statement.where(
            Booking.payments.any(
                Payment.status.in_(
                    (
                        PaymentStatus.FAILED.value,
                        PaymentStatus.CANCELLED.value,
                        PaymentStatus.EXPIRED.value,
                    )
                )
            )
        )
    elif focus == "refund_pending":
        statement = statement.where(
            or_(
                Booking.status == BookingStatus.REFUND_PENDING.value,
                Booking.refunds.any(
                    Refund.status.in_(
                        (
                            RefundStatus.PENDING.value,
                            RefundStatus.PROCESSING.value,
                        )
                    )
                ),
            )
        )
    elif focus == "completed":
        statement = statement.where(Booking.status == BookingStatus.COMPLETED.value)
    return _paginate(
        statement.order_by(Booking.created_at.desc(), Booking.id.desc()),
        page,
        per_page=ADMIN_MONITORING_PAGE_SIZE,
    )


def list_admin_contributions(
    *,
    query: str | None = None,
    status: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    statement = (
        db.select(BookingContribution)
        .join(Booking, Booking.id == BookingContribution.booking_id)
        .join(Field, Field.id == Booking.field_id)
        .options(
            joinedload(BookingContribution.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(BookingContribution.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            joinedload(BookingContribution.user),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            func.lower(Booking.booking_code).like(pattern, escape="\\")
        )
    if status:
        _require_choice(status, ContributionStatus, "Trạng thái tiền cọc")
        statement = statement.where(BookingContribution.status == status)
    if venue_id:
        statement = statement.where(Field.venue_id == venue_id)
    if field_id:
        statement = statement.where(Field.id == field_id)
    return _paginate(
        statement.order_by(
            BookingContribution.created_at.desc(),
            BookingContribution.id.desc(),
        ),
        page,
        per_page=ADMIN_MONITORING_PAGE_SIZE,
    )


def list_admin_payments(
    *,
    query: str | None = None,
    status: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    statement = (
        db.select(Payment)
        .join(Booking, Booking.id == Payment.booking_id)
        .join(Field, Field.id == Booking.field_id)
        .options(
            joinedload(Payment.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(Payment.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            joinedload(Payment.contribution),
            joinedload(Payment.payer),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Booking.booking_code).like(pattern, escape="\\"),
                func.lower(Payment.order_id).like(pattern, escape="\\"),
                func.lower(Payment.request_id).like(pattern, escape="\\"),
                func.lower(func.coalesce(Payment.provider_trans_id, "")).like(
                    pattern,
                    escape="\\",
                ),
            )
        )
    if status:
        _require_choice(status, PaymentStatus, "Trạng thái thanh toán")
        statement = statement.where(Payment.status == status)
    if venue_id:
        statement = statement.where(Field.venue_id == venue_id)
    if field_id:
        statement = statement.where(Field.id == field_id)
    return _paginate(
        statement.order_by(Payment.created_at.desc(), Payment.id.desc()),
        page,
        per_page=ADMIN_MONITORING_PAGE_SIZE,
    )


def list_admin_refunds(
    *,
    query: str | None = None,
    status: str | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    statement = (
        db.select(Refund)
        .join(Booking, Booking.id == Refund.booking_id)
        .join(Field, Field.id == Booking.field_id)
        .options(
            joinedload(Refund.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(Refund.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            joinedload(Refund.payment),
            joinedload(Refund.recipient),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Booking.booking_code).like(pattern, escape="\\"),
                func.lower(Refund.order_id).like(pattern, escape="\\"),
                func.lower(Refund.request_id).like(pattern, escape="\\"),
                func.lower(func.coalesce(Refund.provider_refund_trans_id, "")).like(
                    pattern,
                    escape="\\",
                ),
            )
        )
    if status:
        _require_choice(status, RefundStatus, "Trạng thái hoàn tiền")
        statement = statement.where(Refund.status == status)
    if venue_id:
        statement = statement.where(Field.venue_id == venue_id)
    if field_id:
        statement = statement.where(Field.id == field_id)
    return _paginate(
        statement.order_by(Refund.created_at.desc(), Refund.id.desc()),
        page,
        per_page=ADMIN_MONITORING_PAGE_SIZE,
    )


def list_admin_matches(
    *,
    query: str | None = None,
    status: str | None = None,
    sport_code: str | None = None,
    booking_date: date | None = None,
    venue_id: int | None = None,
    field_id: int | None = None,
    page: int = 1,
) -> AdminPage:
    statement = (
        db.select(Match)
        .join(Booking, Booking.id == Match.booking_id)
        .join(Field, Field.id == Booking.field_id)
        .join(FieldType, FieldType.id == Field.field_type_id)
        .join(Sport, Sport.id == FieldType.sport_id)
        .options(
            joinedload(Match.creator),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.venue),
            joinedload(Match.booking)
            .joinedload(Booking.field)
            .joinedload(Field.field_type)
            .joinedload(FieldType.sport),
            selectinload(Match.participants).joinedload(MatchParticipant.user),
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Match.title).like(pattern, escape="\\"),
                func.lower(Booking.booking_code).like(pattern, escape="\\"),
            )
        )
    if status:
        _require_choice(status, MatchStatus, "Trạng thái kèo")
        statement = statement.where(Match.status == status)
    if sport_code:
        statement = statement.where(Sport.code == sport_code)
    if booking_date:
        statement = statement.where(Booking.booking_date == booking_date)
    if venue_id:
        statement = statement.where(Field.venue_id == venue_id)
    if field_id:
        statement = statement.where(Field.id == field_id)
    return _paginate(
        statement.order_by(Match.created_at.desc(), Match.id.desc()),
        page,
        per_page=ADMIN_MONITORING_PAGE_SIZE,
    )


def _count(model: Any, *conditions: Any) -> int:
    statement = db.select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(db.session.scalar(statement) or 0)


def _sum_amount(column: Any, *conditions: Any) -> Decimal:
    statement = db.select(func.coalesce(func.sum(column), 0))
    if conditions:
        statement = statement.where(*conditions)
    return Decimal(db.session.scalar(statement) or 0)


def _paginate(
    statement: Any,
    page: int,
    *,
    per_page: int = ADMIN_PAGE_SIZE,
) -> AdminPage:
    normalized_page = max(page, 1)
    pagination = db.paginate(
        statement,
        page=normalized_page,
        per_page=per_page,
        error_out=False,
    )
    return AdminPage(
        items=tuple(pagination.items),
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
    )


def _normalize_query(value: str | None) -> str:
    return (value or "").strip().lower()[:100]


def _contains_pattern(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("[", "\\[")
    )
    return f"%{escaped}%"


def _require_choice(value: str, enum_type: Any, field_name: str) -> None:
    allowed = {item.value for item in enum_type}
    if value not in allowed:
        raise AdminError(f"{field_name} không hợp lệ.")


def _admin_province_condition(province: Any) -> Any:
    return or_(
        Venue.province_code == province.code,
        and_(
            Venue.province_code.is_(None),
            func.coalesce(Venue.province_name, Venue.city) == province.name,
        ),
    )


def _admin_ward_condition(ward: Any) -> Any:
    return or_(
        Venue.ward_code == ward.code,
        and_(
            Venue.ward_code.is_(None),
            func.coalesce(Venue.ward_name, Venue.district) == ward.full_name,
        ),
    )


def _venue_matches_admin_location(
    venue: Venue,
    province: Any | None,
    ward: Any | None,
) -> bool:
    if province is not None:
        province_matches = venue.province_code == province.code or (
            venue.province_code is None
            and (venue.province_name or venue.city) == province.name
        )
        if not province_matches:
            return False
    if ward is not None:
        ward_matches = venue.ward_code == ward.code or (
            venue.ward_code is None
            and (venue.ward_name or venue.district) == ward.full_name
        )
        if not ward_matches:
            return False
    return True


def _admin_match_context(match: Match | None) -> AdminMatchContext | None:
    if match is None:
        return None
    counts = _admin_match_participant_counts(match)
    return AdminMatchContext(
        match=match,
        total_participants=counts["total"],
        joined_participants=counts["joined"],
        pending_participants=(counts["pending"] + counts["awaiting_payment"]),
        closed_participants=counts["closed"],
    )


def _admin_match_list_item(
    match: Match,
    *,
    current_utc: datetime | None = None,
) -> AdminMatchListItem:
    counts = _admin_match_participant_counts(match)
    return AdminMatchListItem(
        match=match,
        effective_status=_admin_match_effective_status(
            match,
            current_utc=current_utc or utc_now(),
        ),
        total_participants=counts["total"],
        joined_participants=counts["joined"],
        pending_participants=counts["pending"],
        awaiting_payment_participants=counts["awaiting_payment"],
        closed_participants=counts["closed"],
    )


def _admin_match_effective_status(
    match: Match,
    *,
    current_utc: datetime,
) -> str:
    """Derive the Admin-only operational status without writing Match.status."""
    if (
        match.status in ADMIN_MATCH_OPERATIONAL_STATUSES
        and _admin_booking_has_ended(match.booking, current_utc=current_utc)
    ):
        return ADMIN_MATCH_EFFECTIVE_ENDED_STATUS
    return match.status


def _admin_booking_has_ended(
    booking: Booking,
    *,
    current_utc: datetime,
) -> bool:
    local_now = _admin_vietnam_now(current_utc)
    return datetime.combine(booking.booking_date, booking.end_time) <= local_now


def _admin_booking_has_ended_condition(current_utc: datetime):
    local_now = _admin_vietnam_now(current_utc)
    return or_(
        Booking.booking_date < local_now.date(),
        and_(
            Booking.booking_date == local_now.date(),
            Booking.end_time <= local_now.time(),
        ),
    )


def _admin_vietnam_now(current_utc: datetime) -> datetime:
    return current_utc.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=7))
    ).replace(tzinfo=None)


def _admin_match_participant_counts(match: Match) -> dict[str, int]:
    counts = {
        "total": len(match.participants),
        "joined": 0,
        "pending": 0,
        "awaiting_payment": 0,
    }
    for participant in match.participants:
        if participant.status == MatchParticipantStatus.JOINED.value:
            counts["joined"] += 1
        elif participant.status == MatchParticipantStatus.PENDING.value:
            counts["pending"] += 1
        elif (
            participant.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        ):
            counts["awaiting_payment"] += 1
    counts["closed"] = (
        counts["total"]
        - counts["joined"]
        - counts["pending"]
        - counts["awaiting_payment"]
    )
    return counts


def _admin_match_historical_events(
    match: Match,
) -> tuple[AdminHistoricalEvent, ...]:
    events = [
        AdminHistoricalEvent(
            occurred_at=match.created_at,
            event_type="match_created",
            record=match,
        )
    ]
    events.extend(
        AdminHistoricalEvent(
            occurred_at=participant.created_at,
            event_type="participant_created",
            record=participant,
        )
        for participant in match.participants
    )
    meaningful_statuses = {
        MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
        MatchParticipantStatus.JOINED.value,
        MatchParticipantStatus.REJECTED.value,
        MatchParticipantStatus.EXPIRED.value,
        MatchParticipantStatus.WITHDRAWN.value,
    }
    events.extend(
        AdminHistoricalEvent(
            occurred_at=participant.decided_at,
            event_type="participant_decided",
            record=participant,
        )
        for participant in match.participants
        if participant.decided_at is not None
        and participant.status in meaningful_statuses
    )
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                event.event_type,
                event.record.id,
            ),
        )
    )


def _admin_booking_historical_events(
    booking: Booking,
) -> tuple[AdminHistoricalEvent, ...]:
    events = [
        AdminHistoricalEvent(
            occurred_at=booking.created_at,
            event_type="booking_created",
            record=booking,
        )
    ]
    events.extend(
        AdminHistoricalEvent(
            occurred_at=payment.paid_at,
            event_type="payment_success",
            record=payment,
        )
        for payment in booking.payments
        if payment.status == PaymentStatus.SUCCESS.value
        and payment.paid_at is not None
    )
    events.extend(
        AdminHistoricalEvent(
            occurred_at=refund.refunded_at,
            event_type="refund_success",
            record=refund,
        )
        for refund in booking.refunds
        if refund.status == RefundStatus.SUCCESS.value
        and refund.refunded_at is not None
    )
    if booking.match is not None:
        events.append(
            AdminHistoricalEvent(
                occurred_at=booking.match.created_at,
                event_type="match_created",
                record=booking.match,
            )
        )
        meaningful_participant_statuses = {
            MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
            MatchParticipantStatus.JOINED.value,
            MatchParticipantStatus.REJECTED.value,
            MatchParticipantStatus.EXPIRED.value,
            MatchParticipantStatus.WITHDRAWN.value,
        }
        events.extend(
            AdminHistoricalEvent(
                occurred_at=participant.decided_at,
                event_type="participant_decided",
                record=participant,
            )
            for participant in booking.match.participants
            if participant.decided_at is not None
            and participant.status in meaningful_participant_statuses
        )
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                event.event_type,
                event.record.id,
            ),
        )
    )


def _admin_booking_list_item(
    booking: Booking,
    payment_states: set[str],
    refund_states: set[str],
) -> AdminBookingListItem:
    has_refund_attention = bool(refund_states)
    has_payment_problem = bool(
        payment_states
        & {
            PaymentStatus.FAILED.value,
            PaymentStatus.CANCELLED.value,
            PaymentStatus.EXPIRED.value,
        }
    )
    has_pending_payment = PaymentStatus.PENDING.value in payment_states
    if (has_payment_problem or has_pending_payment) and has_refund_attention:
        return AdminBookingListItem(
            booking=booking,
            attention_label="Thanh toán và hoàn tiền cần theo dõi",
            attention_kind="combined",
        )
    if has_payment_problem:
        return AdminBookingListItem(
            booking=booking,
            attention_label="Thanh toán cần kiểm tra",
            attention_kind="payment",
        )
    if has_pending_payment:
        return AdminBookingListItem(
            booking=booking,
            attention_label="Thanh toán chờ xác nhận",
            attention_kind="pending",
        )
    if has_refund_attention:
        return AdminBookingListItem(
            booking=booking,
            attention_label="Hoàn tiền cần theo dõi",
            attention_kind="refund",
        )
    return AdminBookingListItem(
        booking=booking,
        attention_label=None,
        attention_kind=None,
    )
