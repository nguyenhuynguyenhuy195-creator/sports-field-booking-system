import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import OwnerApplication, OwnerApplicationStatus
from app.services import register_user


def test_partial_unique_index_allows_only_one_pending_application(app):
    with app.app_context():
        user = register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password="MatKhauAnToan123",
        )
        first = OwnerApplication(
            user_id=user.id,
            business_name="Sân bóng A",
            contact_phone="0901234567",
            status=OwnerApplicationStatus.PENDING.value,
        )
        second = OwnerApplication(
            user_id=user.id,
            business_name="Sân bóng B",
            contact_phone="0907654321",
            status=OwnerApplicationStatus.PENDING.value,
        )
        db.session.add_all([first, second])

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_partial_unique_index_allows_history_after_rejection(app):
    with app.app_context():
        user = register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password="MatKhauAnToan123",
        )
        rejected = OwnerApplication(
            user_id=user.id,
            business_name="Sân bóng cũ",
            contact_phone="0901234567",
            status=OwnerApplicationStatus.REJECTED.value,
            rejection_reason="Thiếu thông tin.",
        )
        pending = OwnerApplication(
            user_id=user.id,
            business_name="Sân bóng mới",
            contact_phone="0907654321",
            status=OwnerApplicationStatus.PENDING.value,
        )
        db.session.add_all([rejected, pending])
        db.session.commit()

        assert db.session.scalar(
            db.select(db.func.count(OwnerApplication.id))
        ) == 2
