from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingPriceDetail,
    CatalogStatus,
    Field,
    FieldMaintenance,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    Match,
    MatchParticipant,
    Payment,
    PriceSlotStatus,
    Refund,
    User,
    UserRole,
    UserStatus,
    Venue,
    VenueStatus,
)
from app.services.administrative_unit import resolve_administrative_address


class DemoDataError(RuntimeError):
    """Raised when development demo data cannot be reset safely."""


@dataclass(frozen=True)
class DemoDataResetSummary:
    removed_counts: dict[str, int]
    venue_id: int
    field_ids: tuple[int, ...]


DELETE_ORDER = (
    Refund,
    MatchParticipant,
    Payment,
    Match,
    BookingPriceDetail,
    BookingContribution,
    Booking,
    FieldMaintenance,
    FieldPriceSlot,
    Field,
    Venue,
)


def reset_and_seed_demo_business_data() -> DemoDataResetSummary:
    """Replace local/testing business records while preserving accounts/catalogs."""
    if current_app.config.get("APP_ENV_NAME") not in {
        "development",
        "testing",
    }:
        raise DemoDataError(
            "Reset dữ liệu demo chỉ được phép trong development hoặc testing."
        )

    owner = db.session.scalar(
        db.select(User)
        .where(
            User.role == UserRole.OWNER.value,
            User.status == UserStatus.ACTIVE.value,
        )
        .order_by(User.id.asc())
    )
    if owner is None:
        raise DemoDataError(
            "Cần ít nhất một tài khoản OWNER đang hoạt động để tạo dữ liệu demo."
        )

    administrative_address = resolve_administrative_address(
        province_code="79",
        ward_code="27073",
    )
    field_types = {
        item.code: item
        for item in db.session.scalars(
            db.select(FieldType).where(
                FieldType.code.in_(
                    [
                        FieldTypeCode.BADMINTON_STANDARD.value,
                        FieldTypeCode.FOOTBALL_5.value,
                    ]
                ),
                FieldType.status == CatalogStatus.ACTIVE.value,
            )
        )
    }
    required_codes = {
        FieldTypeCode.BADMINTON_STANDARD.value,
        FieldTypeCode.FOOTBALL_5.value,
    }
    if set(field_types) != required_codes:
        raise DemoDataError("Danh mục loại sân demo chưa đầy đủ.")

    removed_counts = {
        model.__tablename__: db.session.scalar(
            db.select(db.func.count()).select_from(model)
        )
        for model in DELETE_ORDER
    }

    try:
        for model in DELETE_ORDER:
            db.session.execute(db.delete(model))

        venue = Venue(
            owner_id=owner.id,
            name="Trung tâm Thể thao Phú Nhuận",
            address="49 Phan Đăng Lưu",
            province_code=administrative_address.province.code,
            province_name=administrative_address.province.name,
            ward_code=administrative_address.ward.code,
            ward_name=administrative_address.ward.full_name,
            district=None,
            city=None,
            phone="02835102762",
            description=(
                "Dữ liệu demo có cấu trúc để Chủ sân quản lý cơ sở "
                "và gửi Quản trị viên kiểm duyệt."
            ),
            opening_time=time(6, 0),
            closing_time=time(22, 0),
            status=VenueStatus.PENDING.value,
        )
        db.session.add(venue)
        db.session.flush()

        badminton_field = Field(
            venue_id=venue.id,
            name="Sân cầu lông A",
            field_type_id=field_types[
                FieldTypeCode.BADMINTON_STANDARD.value
            ].id,
            surface_type="Thảm PVC",
            capacity=4,
            status=FieldStatus.ACTIVE.value,
        )
        football_field = Field(
            venue_id=venue.id,
            name="Sân bóng đá 5 người",
            field_type_id=field_types[FieldTypeCode.FOOTBALL_5.value].id,
            surface_type="Cỏ nhân tạo",
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add_all([badminton_field, football_field])
        db.session.flush()

        for day_of_week in range(7):
            db.session.add_all(
                [
                    FieldPriceSlot(
                        field_id=badminton_field.id,
                        day_of_week=day_of_week,
                        start_time=time(6, 0),
                        end_time=time(17, 0),
                        hourly_price=Decimal("120000"),
                        status=PriceSlotStatus.ACTIVE.value,
                    ),
                    FieldPriceSlot(
                        field_id=badminton_field.id,
                        day_of_week=day_of_week,
                        start_time=time(17, 0),
                        end_time=time(22, 0),
                        hourly_price=Decimal("180000"),
                        status=PriceSlotStatus.ACTIVE.value,
                    ),
                    FieldPriceSlot(
                        field_id=football_field.id,
                        day_of_week=day_of_week,
                        start_time=time(6, 0),
                        end_time=time(22, 0),
                        hourly_price=Decimal("350000"),
                        status=PriceSlotStatus.ACTIVE.value,
                    ),
                ]
            )

        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise DemoDataError(
            "Không thể reset và tạo lại dữ liệu demo."
        ) from exc

    return DemoDataResetSummary(
        removed_counts=removed_counts,
        venue_id=venue.id,
        field_ids=(badminton_field.id, football_field.id),
    )
