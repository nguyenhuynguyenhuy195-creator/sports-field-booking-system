from datetime import time
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Field,
    FieldPriceSlot,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    PriceSlotStatus,
    Province,
    Sport,
    User,
    UserRole,
    Venue,
    VenueStatus,
    Ward,
)
from app.services import (
    DemoDataError,
    register_user,
    reset_and_seed_demo_business_data,
)


def _create_owner_and_old_business_data(app) -> int:
    with app.app_context():
        owner = register_user(
            full_name="Chủ sân Demo",
            email="demo-owner@example.com",
            phone="0901234567",
            password="MatKhauAnToan123",
        )
        owner.role = UserRole.OWNER.value
        db.session.flush()
        venue = Venue(
            owner_id=owner.id,
            name="Cơ sở demo cũ",
            address="1 Đường Cũ",
            district="Quận Cũ",
            city="Thành phố Cũ",
            opening_time=time(6, 0),
            closing_time=time(22, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name="Sân demo cũ",
            field_type_id=db.session.scalar(
                db.select(FieldType.id).where(
                    FieldType.code == FieldTypeCode.FOOTBALL_5.value
                )
            ),
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.flush()
        db.session.add(
            FieldPriceSlot(
                field_id=field.id,
                day_of_week=0,
                start_time=time(6, 0),
                end_time=time(22, 0),
                hourly_price=Decimal("100000"),
                status=PriceSlotStatus.ACTIVE.value,
            )
        )
        db.session.commit()
        return owner.id


def test_demo_reset_preserves_accounts_and_catalogs_and_seeds_structured_data(
    app,
):
    owner_id = _create_owner_and_old_business_data(app)
    with app.app_context():
        counts_before = {
            "users": db.session.scalar(db.select(db.func.count(User.id))),
            "sports": db.session.scalar(db.select(db.func.count(Sport.id))),
            "provinces": db.session.scalar(
                db.select(db.func.count(Province.code))
            ),
            "wards": db.session.scalar(db.select(db.func.count(Ward.code))),
        }

        summary = reset_and_seed_demo_business_data()

        venue = db.session.get(Venue, summary.venue_id)
        assert summary.removed_counts["venues"] == 1
        assert db.session.scalar(db.select(db.func.count(User.id))) == counts_before[
            "users"
        ]
        assert db.session.scalar(db.select(db.func.count(Sport.id))) == counts_before[
            "sports"
        ]
        assert db.session.scalar(
            db.select(db.func.count(Province.code))
        ) == counts_before["provinces"]
        assert db.session.scalar(db.select(db.func.count(Ward.code))) == counts_before[
            "wards"
        ]
        assert venue.owner_id == owner_id
        assert venue.name == "Trung tâm Thể thao Phú Nhuận"
        assert venue.province_code == "79"
        assert venue.province_name == "Thành phố Hồ Chí Minh"
        assert venue.ward_code == "27073"
        assert venue.ward_name == "Phường Phú Nhuận"
        assert venue.city is None
        assert venue.district is None
        assert venue.google_place_id is None
        assert venue.latitude is None
        assert venue.longitude is None
        assert venue.description == (
            "Dữ liệu demo có cấu trúc để Chủ sân quản lý cơ sở "
            "và gửi Quản trị viên kiểm duyệt."
        )
        assert "vị trí Google" not in venue.description
        assert venue.status == VenueStatus.PENDING.value
        assert db.session.scalar(db.select(db.func.count(Field.id))) == 2
        assert db.session.scalar(db.select(db.func.count(FieldPriceSlot.id))) == 21


def test_demo_reset_is_blocked_outside_development_or_testing(app):
    _create_owner_and_old_business_data(app)
    with app.app_context():
        app.config["APP_ENV_NAME"] = "production"

        with pytest.raises(DemoDataError):
            reset_and_seed_demo_business_data()

        assert db.session.scalar(db.select(db.func.count(Venue.id))) == 1


def test_demo_cli_rejects_testing_environment(app):
    result = app.test_cli_runner().invoke(
        args=["demo", "reset-business-data", "--yes"]
    )

    assert result.exit_code == 1
    assert "APP_ENV=development" in result.output
