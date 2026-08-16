from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingStatus,
    ContributionStatus,
    Field,
    FieldType,
    Match,
    MatchParticipant,
    MatchStatus,
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


ADMIN_PAGE_SIZE = 20
ADMIN_VENUE_PAGE_SIZE = 10


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
    active_bookings: int
    pending_payments: int
    pending_refunds: int
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


def get_admin_dashboard_summary() -> AdminDashboardSummary:
    return AdminDashboardSummary(
        total_accounts=_count(User),
        active_accounts=_count(User, User.status == UserStatus.ACTIVE.value),
        locked_accounts=_count(User, User.status == UserStatus.LOCKED.value),
        pending_owner_applications=_count(
            OwnerApplication,
            OwnerApplication.status == OwnerApplicationStatus.PENDING.value,
        ),
        pending_venues=_count(Venue, Venue.status == VenueStatus.PENDING.value),
        total_bookings=_count(Booking),
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
        pending_payments=_count(
            Payment,
            Payment.status == PaymentStatus.PENDING.value,
        ),
        pending_refunds=_count(
            Refund,
            Refund.status.in_(
                {RefundStatus.PENDING.value, RefundStatus.PROCESSING.value}
            ),
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


def list_admin_monitoring_cities() -> tuple[str, ...]:
    statement = (
        db.select(Venue.city)
        .where(Venue.city != "")
        .distinct()
        .order_by(Venue.city.asc())
    )
    return tuple(db.session.scalars(statement))


def list_admin_monitoring_districts(*, city: str | None = None) -> tuple[str, ...]:
    statement = db.select(Venue.district).where(
        Venue.district.is_not(None),
        Venue.district != "",
    )
    if city:
        statement = statement.where(Venue.city == city)
    statement = statement.distinct().order_by(Venue.district.asc())
    return tuple(value for value in db.session.scalars(statement) if value)


def list_admin_monitoring_locations(
    *,
    query: str | None = None,
    city: str | None = None,
    district: str | None = None,
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
                func.lower(Venue.city).like(pattern, escape="\\"),
                func.lower(func.coalesce(Venue.district, "")).like(
                    pattern,
                    escape="\\",
                ),
            )
        )
    if city:
        statement = statement.where(Venue.city == city)
    if district:
        statement = statement.where(Venue.district == district)

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


def list_admin_bookings(
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
        )
    )
    normalized_query = _normalize_query(query)
    if normalized_query:
        pattern = _contains_pattern(normalized_query)
        statement = statement.where(
            or_(
                func.lower(Booking.booking_code).like(pattern, escape="\\"),
                func.lower(User.email).like(pattern, escape="\\"),
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
    return _paginate(
        statement.order_by(Booking.created_at.desc(), Booking.id.desc()),
        page,
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
            selectinload(Match.participants),
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


def _paginate(statement: Any, page: int) -> AdminPage:
    normalized_page = max(page, 1)
    pagination = db.paginate(
        statement,
        page=normalized_page,
        per_page=ADMIN_PAGE_SIZE,
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
