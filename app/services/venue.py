from __future__ import annotations

from datetime import time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import User, UserRole, Venue, VenueStatus
from app.models.user import utc_now
from app.services.auth import normalize_full_name, normalize_phone


class VenueError(ValueError):
    """Base error for venue business rules."""


class VenueNotFoundError(VenueError):
    """Raised when a venue id does not exist or is not publicly visible."""


class VenuePermissionError(VenueError):
    """Raised when an owner tries to manage another owner's venue."""


class InvalidVenueStateError(VenueError):
    """Raised when a moderation transition would not change the venue."""


def _normalize_required_text(value: str) -> str:
    return normalize_full_name(value)


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    return normalized or None


def _validate_operating_hours(opening_time: time, closing_time: time) -> None:
    if opening_time >= closing_time:
        raise VenueError("Giờ đóng cửa phải sau giờ mở cửa.")


def list_public_venues() -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.status == VenueStatus.ACTIVE.value)
            .order_by(Venue.name.asc())
        )
    )


def get_public_venue(venue_id: int) -> Venue:
    venue = db.session.scalar(
        db.select(Venue)
        .options(joinedload(Venue.owner))
        .where(
            Venue.id == venue_id,
            Venue.status == VenueStatus.ACTIVE.value,
        )
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở đang hoạt động.")
    return venue


def list_owner_venues(owner_id: int) -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.created_at.desc())
        )
    )


def get_owner_venue(*, venue_id: int, owner_id: int) -> Venue:
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner_id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")
    return venue


def list_admin_venues() -> list[Venue]:
    return list(
        db.session.scalars(
            db.select(Venue)
            .options(joinedload(Venue.owner), joinedload(Venue.reviewer))
            .order_by(Venue.created_at.desc())
        )
    )


def create_venue(
    *,
    owner: User,
    name: str,
    address: str,
    district: str | None,
    city: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được tạo cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)

    venue = Venue(
        owner_id=owner.id,
        name=_normalize_required_text(name),
        address=_normalize_required_text(address),
        district=_normalize_optional_text(district),
        city=_normalize_required_text(city),
        phone=normalize_phone(phone),
        description=(description or "").strip() or None,
        opening_time=opening_time,
        closing_time=closing_time,
        status=VenueStatus.PENDING.value,
    )
    db.session.add(venue)
    _commit_or_raise("Không thể tạo cơ sở lúc này. Vui lòng thử lại.")
    return venue


def update_venue(
    *,
    venue_id: int,
    owner: User,
    name: str,
    address: str,
    district: str | None,
    city: str,
    phone: str | None,
    description: str | None,
    opening_time: time,
    closing_time: time,
) -> Venue:
    if owner.role != UserRole.OWNER.value:
        raise VenuePermissionError("Chỉ chủ sân được sửa cơ sở thể thao.")
    _validate_operating_hours(opening_time, closing_time)

    venue = db.session.scalar(
        db.select(Venue).where(Venue.id == venue_id).with_for_update()
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.owner_id != owner.id:
        raise VenuePermissionError("Bạn không có quyền quản lý cơ sở này.")

    venue.name = _normalize_required_text(name)
    venue.address = _normalize_required_text(address)
    venue.district = _normalize_optional_text(district)
    venue.city = _normalize_required_text(city)
    venue.phone = normalize_phone(phone)
    venue.description = (description or "").strip() or None
    venue.opening_time = opening_time
    venue.closing_time = closing_time

    _commit_or_raise("Không thể cập nhật cơ sở lúc này. Vui lòng thử lại.")
    return venue


def moderate_venue(
    *,
    venue_id: int,
    reviewer: User,
    decision: str,
    moderation_note: str | None,
) -> Venue:
    if reviewer.role != UserRole.ADMIN.value:
        raise VenuePermissionError("Chỉ quản trị viên được kiểm duyệt cơ sở.")
    if decision not in {VenueStatus.ACTIVE.value, VenueStatus.HIDDEN.value}:
        raise VenueError("Trạng thái kiểm duyệt không hợp lệ.")

    venue = db.session.scalar(
        db.select(Venue).where(Venue.id == venue_id).with_for_update()
    )
    if venue is None:
        raise VenueNotFoundError("Không tìm thấy cơ sở.")
    if venue.status == decision:
        raise InvalidVenueStateError(
            "Cơ sở đã ở trạng thái này nên không có thay đổi nào được lưu."
        )

    venue.status = decision
    venue.reviewed_by = reviewer.id
    venue.reviewed_at = utc_now()
    venue.moderation_note = (moderation_note or "").strip() or None

    _commit_or_raise(
        "Không thể lưu kết quả kiểm duyệt lúc này. Vui lòng thử lại."
    )
    return venue


def _commit_or_raise(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise VenueError(message) from exc
