from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Field,
    FieldMaintenance,
    FieldMaintenanceStatus,
    User,
    UserRole,
)

from .locking import with_update_lock


VIETNAM_TIMEZONE = timezone(timedelta(hours=7))


class MaintenanceError(ValueError):
    """Base error for field-maintenance business rules."""


class MaintenanceNotFoundError(MaintenanceError):
    """Raised when a field or maintenance record does not exist."""


class MaintenancePermissionError(MaintenanceError):
    """Raised when an owner manages maintenance outside their venues."""


class OverlappingMaintenanceError(MaintenanceError):
    """Raised when active maintenance intervals overlap."""


class InvalidMaintenanceStateError(MaintenanceError):
    """Raised when a maintenance state transition is not allowed."""


def current_vietnam_datetime() -> datetime:
    return datetime.now(VIETNAM_TIMEZONE).replace(tzinfo=None)


def list_owner_maintenances(
    *,
    field_id: int,
    owner_id: int,
) -> tuple[Field, list[FieldMaintenance]]:
    field = _get_owned_field(field_id=field_id, owner_id=owner_id)
    maintenances = list(
        db.session.scalars(
            db.select(FieldMaintenance)
            .where(FieldMaintenance.field_id == field_id)
            .order_by(
                FieldMaintenance.maintenance_date.asc(),
                FieldMaintenance.start_time.asc(),
            )
        )
    )
    return field, maintenances


def get_owner_maintenance(
    *,
    maintenance_id: int,
    owner_id: int,
) -> FieldMaintenance:
    maintenance = db.session.scalar(
        db.select(FieldMaintenance)
        .options(joinedload(FieldMaintenance.field).joinedload(Field.venue))
        .where(FieldMaintenance.id == maintenance_id)
    )
    if maintenance is None:
        raise MaintenanceNotFoundError("Không tìm thấy lịch bảo trì.")
    if maintenance.field.venue.owner_id != owner_id:
        raise MaintenancePermissionError(
            "Bạn không có quyền quản lý lịch bảo trì của sân này."
        )
    return maintenance


def create_maintenance(
    *,
    owner: User,
    field_id: int,
    maintenance_date: date,
    start_time: time,
    end_time: time,
    reason: str,
    now: datetime | None = None,
) -> FieldMaintenance:
    _validate_owner(owner)
    normalized_reason = _validate_maintenance_data(
        maintenance_date=maintenance_date,
        start_time=start_time,
        end_time=end_time,
        reason=reason,
        now=now,
    )
    field = _get_owned_field(
        field_id=field_id,
        owner_id=owner.id,
        lock=True,
    )
    if _active_overlap_exists(
        field_id=field.id,
        maintenance_date=maintenance_date,
        start_time=start_time,
        end_time=end_time,
    ):
        raise OverlappingMaintenanceError(
            "Khoảng giờ này bị chồng với một lịch bảo trì đang hoạt động."
        )
    from .booking import booking_blocks_time

    if booking_blocks_time(
        field_id=field.id,
        booking_date=maintenance_date,
        start_time=start_time,
        end_time=end_time,
        now=now,
    ):
        raise MaintenanceError(
            "Khoảng giờ này trùng với một lịch đặt sân đang giữ chỗ."
        )

    maintenance = FieldMaintenance(
        field_id=field.id,
        maintenance_date=maintenance_date,
        start_time=start_time,
        end_time=end_time,
        reason=normalized_reason,
        status=FieldMaintenanceStatus.ACTIVE.value,
        created_by=owner.id,
    )
    db.session.add(maintenance)
    _commit_maintenance("Không thể tạo lịch bảo trì lúc này. Vui lòng thử lại.")
    return maintenance


def cancel_maintenance(
    *,
    maintenance_id: int,
    owner: User,
    now: datetime | None = None,
) -> FieldMaintenance:
    _validate_owner(owner)
    maintenance = db.session.get(FieldMaintenance, maintenance_id)
    if maintenance is None:
        raise MaintenanceNotFoundError("Không tìm thấy lịch bảo trì.")

    _get_owned_field(
        field_id=maintenance.field_id,
        owner_id=owner.id,
        lock=True,
    )
    maintenance = db.session.scalar(
        with_update_lock(
            db.select(FieldMaintenance).where(
                FieldMaintenance.id == maintenance_id
            ),
            FieldMaintenance,
        )
    )
    if maintenance is None:
        raise MaintenanceNotFoundError("Không tìm thấy lịch bảo trì.")
    if maintenance.status != FieldMaintenanceStatus.ACTIVE.value:
        raise InvalidMaintenanceStateError(
            "Chỉ lịch bảo trì đang hoạt động mới có thể hủy."
        )
    if get_effective_maintenance_status(maintenance, now=now) != (
        FieldMaintenanceStatus.ACTIVE.value
    ):
        raise InvalidMaintenanceStateError("Lịch bảo trì này đã kết thúc.")

    maintenance.status = FieldMaintenanceStatus.CANCELLED.value
    _commit_maintenance("Không thể hủy lịch bảo trì lúc này. Vui lòng thử lại.")
    return maintenance


def maintenance_blocks_time(
    *,
    field_id: int,
    maintenance_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    _validate_interval(start_time=start_time, end_time=end_time)
    return _active_overlap_exists(
        field_id=field_id,
        maintenance_date=maintenance_date,
        start_time=start_time,
        end_time=end_time,
    )


def get_effective_maintenance_status(
    maintenance: FieldMaintenance,
    *,
    now: datetime | None = None,
) -> str:
    if maintenance.status != FieldMaintenanceStatus.ACTIVE.value:
        return maintenance.status
    current = _normalize_local_datetime(now)
    end_at = datetime.combine(
        maintenance.maintenance_date,
        maintenance.end_time,
    )
    if end_at <= current:
        return FieldMaintenanceStatus.COMPLETED.value
    return FieldMaintenanceStatus.ACTIVE.value


def _get_owned_field(
    *,
    field_id: int,
    owner_id: int,
    lock: bool = False,
) -> Field:
    statement = (
        db.select(Field)
        .options(joinedload(Field.venue))
        .where(Field.id == field_id)
    )
    if lock:
        statement = with_update_lock(statement, Field)
    field = db.session.scalar(statement)
    if field is None:
        raise MaintenanceNotFoundError("Không tìm thấy sân.")
    if field.venue.owner_id != owner_id:
        raise MaintenancePermissionError(
            "Bạn không có quyền quản lý lịch bảo trì của sân này."
        )
    return field


def _validate_owner(owner: User) -> None:
    if owner.role != UserRole.OWNER.value:
        raise MaintenancePermissionError("Chỉ chủ sân được quản lý bảo trì.")


def _validate_maintenance_data(
    *,
    maintenance_date: date,
    start_time: time,
    end_time: time,
    reason: str,
    now: datetime | None,
) -> str:
    if not isinstance(maintenance_date, date):
        raise MaintenanceError("Ngày bảo trì không hợp lệ.")
    _validate_interval(start_time=start_time, end_time=end_time)
    normalized_reason = " ".join((reason or "").split())
    if not normalized_reason:
        raise MaintenanceError("Vui lòng nhập lý do bảo trì.")
    if len(normalized_reason) > 500:
        raise MaintenanceError("Lý do bảo trì tối đa 500 ký tự.")

    current = _normalize_local_datetime(now)
    end_at = datetime.combine(maintenance_date, end_time)
    if end_at <= current:
        raise MaintenanceError("Thời gian bảo trì phải chưa kết thúc.")
    return normalized_reason


def _validate_interval(*, start_time: time, end_time: time) -> None:
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise MaintenanceError("Khoảng giờ bảo trì không hợp lệ.")
    if start_time >= end_time:
        raise MaintenanceError("Giờ kết thúc phải sau giờ bắt đầu.")


def _active_overlap_exists(
    *,
    field_id: int,
    maintenance_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    return (
        db.session.scalar(
            db.select(FieldMaintenance.id)
            .where(
                FieldMaintenance.field_id == field_id,
                FieldMaintenance.maintenance_date == maintenance_date,
                FieldMaintenance.status == FieldMaintenanceStatus.ACTIVE.value,
                FieldMaintenance.start_time < end_time,
                FieldMaintenance.end_time > start_time,
            )
            .limit(1)
        )
        is not None
    )


def _normalize_local_datetime(value: datetime | None) -> datetime:
    if value is None:
        return current_vietnam_datetime()
    if value.tzinfo is not None:
        return value.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)
    return value


def _commit_maintenance(message: str) -> None:
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise MaintenanceError(message) from exc
