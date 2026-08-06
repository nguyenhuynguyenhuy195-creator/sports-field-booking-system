from __future__ import annotations

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    OwnerApplication,
    OwnerApplicationStatus,
    User,
    UserRole,
)
from app.models.user import utc_now
from app.services.auth import normalize_full_name, normalize_phone


class OwnerApplicationError(ValueError):
    """Base error for owner-application business rules."""


class PendingOwnerApplicationError(OwnerApplicationError):
    """Raised when a user already has a pending application."""


class OwnerApplicationNotFoundError(OwnerApplicationError):
    """Raised when an application id does not exist."""


class InvalidOwnerApplicationStateError(OwnerApplicationError):
    """Raised when an application cannot make the requested transition."""


def find_pending_application(user_id: int) -> OwnerApplication | None:
    return db.session.scalar(
        db.select(OwnerApplication).where(
            OwnerApplication.user_id == user_id,
            OwnerApplication.status == OwnerApplicationStatus.PENDING.value,
        )
    )


def list_user_applications(user_id: int) -> list[OwnerApplication]:
    return list(
        db.session.scalars(
            db.select(OwnerApplication)
            .where(OwnerApplication.user_id == user_id)
            .order_by(OwnerApplication.created_at.desc())
        )
    )


def list_pending_applications() -> list[OwnerApplication]:
    return list(
        db.session.scalars(
            db.select(OwnerApplication)
            .options(joinedload(OwnerApplication.applicant))
            .where(
                OwnerApplication.status
                == OwnerApplicationStatus.PENDING.value
            )
            .order_by(OwnerApplication.created_at.asc())
        )
    )


def submit_owner_application(
    *,
    user: User,
    business_name: str,
    contact_phone: str,
    note: str | None,
) -> OwnerApplication:
    if user.role != UserRole.USER.value:
        raise OwnerApplicationError(
            "Chỉ tài khoản người chơi mới được gửi yêu cầu trở thành chủ sân."
        )
    if find_pending_application(user.id) is not None:
        raise PendingOwnerApplicationError(
            "Bạn đã có một yêu cầu đang chờ xét duyệt."
        )

    application = OwnerApplication(
        user_id=user.id,
        business_name=normalize_full_name(business_name),
        contact_phone=normalize_phone(contact_phone) or "",
        note=(note or "").strip() or None,
        status=OwnerApplicationStatus.PENDING.value,
    )
    db.session.add(application)

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise PendingOwnerApplicationError(
            "Bạn đã có một yêu cầu đang chờ xét duyệt."
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise OwnerApplicationError(
            "Không thể lưu yêu cầu lúc này. Vui lòng thử lại."
        ) from exc

    return application


def review_owner_application(
    *,
    application_id: int,
    reviewer: User,
    decision: str,
    rejection_reason: str | None,
) -> OwnerApplication:
    if reviewer.role != UserRole.ADMIN.value:
        raise OwnerApplicationError("Chỉ quản trị viên được xét duyệt yêu cầu.")
    if decision not in {
        OwnerApplicationStatus.APPROVED.value,
        OwnerApplicationStatus.REJECTED.value,
    }:
        raise OwnerApplicationError("Kết quả xét duyệt không hợp lệ.")

    normalized_reason = (rejection_reason or "").strip() or None
    if (
        decision == OwnerApplicationStatus.REJECTED.value
        and normalized_reason is None
    ):
        raise OwnerApplicationError("Phải nhập lý do khi từ chối yêu cầu.")

    application = db.session.scalar(
        db.select(OwnerApplication)
        .where(OwnerApplication.id == application_id)
        .with_for_update()
    )
    if application is None:
        raise OwnerApplicationNotFoundError("Không tìm thấy yêu cầu.")
    if not application.is_pending:
        raise InvalidOwnerApplicationStateError(
            "Yêu cầu này đã được xử lý trước đó."
        )

    applicant = db.session.scalar(
        db.select(User)
        .where(User.id == application.user_id)
        .with_for_update()
    )
    if applicant is None:
        raise OwnerApplicationNotFoundError(
            "Không tìm thấy tài khoản gửi yêu cầu."
        )

    application.status = decision
    application.reviewed_by = reviewer.id
    application.reviewed_at = utc_now()
    application.rejection_reason = (
        normalized_reason
        if decision == OwnerApplicationStatus.REJECTED.value
        else None
    )
    if decision == OwnerApplicationStatus.APPROVED.value:
        applicant.role = UserRole.OWNER.value

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise OwnerApplicationError(
            "Không thể lưu kết quả xét duyệt lúc này. Vui lòng thử lại."
        ) from exc

    return application
