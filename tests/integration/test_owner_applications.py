from dataclasses import dataclass

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    OwnerApplication,
    OwnerApplicationStatus,
    User,
    UserRole,
)
from app.services import (
    OwnerApplicationError,
    register_user,
    review_owner_application,
    submit_owner_application,
)


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(
    app,
    *,
    email: str,
    role: UserRole = UserRole.USER,
    full_name: str = "Nguyễn Văn A",
) -> CreatedUser:
    with app.app_context():
        user = register_user(
            full_name=full_name,
            email=email,
            phone="0901234567",
            password=PASSWORD,
        )
        user.role = role.value
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 302


def submit_application(client, *, business_name: str = "Sân bóng Minh Anh"):
    return client.post(
        "/owner-applications/new",
        data={
            "business_name": business_name,
            "contact_phone": " 0909876543 ",
            "note": "  Hoạt động tại Quận 7.  ",
        },
    )


def review_application(
    client,
    *,
    application_id: int,
    decision: OwnerApplicationStatus,
    rejection_reason: str = "",
):
    prefix = f"application-{application_id}"
    return client.post(
        f"/admin/owner-applications/{application_id}/review",
        data={
            f"{prefix}-decision": decision.value,
            f"{prefix}-rejection_reason": rejection_reason,
        },
    )


def seed_owner_application_statuses(app):
    admin = create_user(
        app,
        email="filter-admin@example.com",
        role=UserRole.ADMIN,
        full_name="Quản trị viên Xét duyệt",
    )
    pending_user = create_user(app, email="pending-filter@example.com")
    approved_user = create_user(app, email="approved-filter@example.com")
    rejected_user = create_user(app, email="rejected-filter@example.com")

    with app.app_context():
        applications = {}
        for status_name, user_id, business_name in (
            ("pending", pending_user.id, "Cơ sở đang chờ duyệt"),
            ("approved", approved_user.id, "Cơ sở đã chấp thuận"),
            ("rejected", rejected_user.id, "Cơ sở đã từ chối"),
        ):
            application = submit_owner_application(
                user=db.session.get(User, user_id),
                business_name=business_name,
                contact_phone="0901234567",
                note=f"Ghi chú {status_name}",
            )
            applications[status_name] = application.id

        reviewer = db.session.get(User, admin.id)
        review_owner_application(
            application_id=applications["approved"],
            reviewer=reviewer,
            decision=OwnerApplicationStatus.APPROVED.value,
            rejection_reason=None,
        )
        review_owner_application(
            application_id=applications["rejected"],
            reviewer=reviewer,
            decision=OwnerApplicationStatus.REJECTED.value,
            rejection_reason="Không xác minh được thông tin kinh doanh.",
        )

    return admin, applications


def test_user_submits_normalized_pending_application(app, client):
    user = create_user(app, email="player@example.com")
    login(client, email=user.email)

    response = submit_application(client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/owner-applications/mine")
    with app.app_context():
        application = db.session.scalar(db.select(OwnerApplication))
        assert application is not None
        assert application.user_id == user.id
        assert application.business_name == "Sân bóng Minh Anh"
        assert application.contact_phone == "0909876543"
        assert application.note == "Hoạt động tại Quận 7."
        assert application.status == OwnerApplicationStatus.PENDING.value


def test_user_cannot_submit_two_pending_applications(app, client):
    user = create_user(app, email="player@example.com")
    login(client, email=user.email)
    assert submit_application(client).status_code == 302

    response = submit_application(client, business_name="Sân bóng thứ hai")

    assert response.status_code == 200
    assert "đang chờ xét duyệt" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(OwnerApplication.id))
        ) == 1


def test_owner_application_pages_require_correct_permissions(app, client):
    assert client.get("/owner-applications/new").status_code == 302

    user = create_user(app, email="player@example.com")
    login(client, email=user.email)
    assert client.get("/owner-applications/new").status_code == 200
    assert client.get("/admin/owner-applications").status_code == 403


def test_admin_filters_owner_applications_by_status(app, client):
    admin, _ = seed_owner_application_statuses(app)
    login(client, email=admin.email)

    expected_business_names = {
        OwnerApplicationStatus.PENDING.value: "Cơ sở đang chờ duyệt",
        OwnerApplicationStatus.APPROVED.value: "Cơ sở đã chấp thuận",
        OwnerApplicationStatus.REJECTED.value: "Cơ sở đã từ chối",
    }

    default_response = client.get("/admin/owner-applications")
    default_page = default_response.get_data(as_text=True)
    assert default_response.status_code == 200
    assert (
        expected_business_names[OwnerApplicationStatus.PENDING.value]
        in default_page
    )
    assert (
        expected_business_names[OwnerApplicationStatus.APPROVED.value]
        not in default_page
    )
    assert (
        expected_business_names[OwnerApplicationStatus.REJECTED.value]
        not in default_page
    )
    assert 'data-confirm-title="Chấp thuận hồ sơ chủ sân"' in default_page
    assert 'data-confirm-title="Từ chối hồ sơ chủ sân"' in default_page

    for status, expected_name in expected_business_names.items():
        response = client.get(f"/admin/owner-applications?status={status}")
        page = response.get_data(as_text=True)

        assert response.status_code == 200
        assert expected_name in page
        for other_status, other_name in expected_business_names.items():
            if other_status != status:
                assert other_name not in page


def test_admin_owner_application_filter_rejects_invalid_status(app, client):
    admin = create_user(
        app,
        email="invalid-filter-admin@example.com",
        role=UserRole.ADMIN,
    )
    login(client, email=admin.email)

    response = client.get(
        "/admin/owner-applications?status=UNKNOWN",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.request.path == "/admin/owner-applications"
    assert response.request.query_string == b""
    assert "Bộ lọc trạng thái hồ sơ không hợp lệ." in page
    assert "Chờ duyệt" in page


def test_processed_owner_applications_show_review_history_without_actions(
    app,
    client,
):
    admin, _ = seed_owner_application_statuses(app)
    login(client, email=admin.email)

    approved_response = client.get(
        "/admin/owner-applications?status=APPROVED"
    )
    approved_page = approved_response.get_data(as_text=True)
    assert approved_response.status_code == 200
    assert "Lịch sử xét duyệt" in approved_page
    assert "Đã chấp thuận" in approved_page
    assert "Quản trị viên Xét duyệt" in approved_page
    assert "Thời gian xét duyệt" in approved_page
    assert "Lý do từ chối" not in approved_page
    assert 'data-confirm-title="Chấp thuận hồ sơ chủ sân"' not in approved_page
    assert 'data-confirm-title="Từ chối hồ sơ chủ sân"' not in approved_page

    rejected_response = client.get(
        "/admin/owner-applications?status=REJECTED"
    )
    rejected_page = rejected_response.get_data(as_text=True)
    assert rejected_response.status_code == 200
    assert "Lịch sử xét duyệt" in rejected_page
    assert "Đã từ chối" in rejected_page
    assert "Quản trị viên Xét duyệt" in rejected_page
    assert "Thời gian xét duyệt" in rejected_page
    assert "Lý do từ chối" in rejected_page
    assert "Không xác minh được thông tin kinh doanh." in rejected_page
    assert 'data-confirm-title="Chấp thuận hồ sơ chủ sân"' not in rejected_page
    assert 'data-confirm-title="Từ chối hồ sơ chủ sân"' not in rejected_page


def test_admin_cannot_review_processed_owner_application_again(app, client):
    admin, applications = seed_owner_application_statuses(app)
    login(client, email=admin.email)

    response = review_application(
        client,
        application_id=applications["approved"],
        decision=OwnerApplicationStatus.REJECTED,
        rejection_reason="Thử xử lý lại hồ sơ.",
    )

    assert response.status_code == 302
    redirected_page = client.get(response.headers["Location"]).get_data(
        as_text=True
    )
    assert "Yêu cầu này đã được xử lý trước đó." in redirected_page
    with app.app_context():
        application = db.session.get(
            OwnerApplication,
            applications["approved"],
        )
        applicant = db.session.get(User, application.user_id)
        assert application.status == OwnerApplicationStatus.APPROVED.value
        assert application.rejection_reason is None
        assert applicant.role == UserRole.OWNER.value


def test_admin_approves_application_and_promotes_user(app, client):
    player = create_user(app, email="player@example.com")
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)
    login(client, email=player.email)
    assert submit_application(client).status_code == 302
    client.post("/auth/logout")

    with app.app_context():
        application_id = db.session.scalar(
            db.select(OwnerApplication.id)
        )

    login(client, email=admin.email)
    response = review_application(
        client,
        application_id=application_id,
        decision=OwnerApplicationStatus.APPROVED,
    )

    assert response.status_code == 302
    with app.app_context():
        application = db.session.get(OwnerApplication, application_id)
        promoted_user = db.session.get(User, player.id)
        assert application.status == OwnerApplicationStatus.APPROVED.value
        assert application.reviewed_by == admin.id
        assert application.reviewed_at is not None
        assert application.rejection_reason is None
        assert promoted_user.role == UserRole.OWNER.value


def test_admin_cannot_approve_when_applicant_role_has_changed(app, client):
    player = create_user(app, email="role-changed-player@example.com")
    admin = create_user(
        app,
        email="role-changed-admin@example.com",
        role=UserRole.ADMIN,
    )
    login(client, email=player.email)
    assert submit_application(client).status_code == 302
    client.post("/auth/logout")

    with app.app_context():
        application_id = db.session.scalar(
            db.select(OwnerApplication.id)
        )
        applicant = db.session.get(User, player.id)
        applicant.role = UserRole.OWNER.value
        db.session.commit()

    login(client, email=admin.email)
    response = review_application(
        client,
        application_id=application_id,
        decision=OwnerApplicationStatus.APPROVED,
    )

    assert response.status_code == 302
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Không thể chấp thuận vì vai trò tài khoản đã thay đổi." in page
    with app.app_context():
        application = db.session.get(OwnerApplication, application_id)
        applicant = db.session.get(User, player.id)
        assert application.status == OwnerApplicationStatus.PENDING.value
        assert application.reviewed_by is None
        assert application.reviewed_at is None
        assert applicant.role == UserRole.OWNER.value


def test_admin_rejection_requires_reason_and_does_not_promote(app, client):
    player = create_user(app, email="player@example.com")
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)
    login(client, email=player.email)
    assert submit_application(client).status_code == 302
    client.post("/auth/logout")

    with app.app_context():
        application_id = db.session.scalar(
            db.select(OwnerApplication.id)
        )

    login(client, email=admin.email)
    missing_reason_response = review_application(
        client,
        application_id=application_id,
        decision=OwnerApplicationStatus.REJECTED,
    )
    assert missing_reason_response.status_code == 302

    with app.app_context():
        application = db.session.get(OwnerApplication, application_id)
        assert application.status == OwnerApplicationStatus.PENDING.value

    response = review_application(
        client,
        application_id=application_id,
        decision=OwnerApplicationStatus.REJECTED,
        rejection_reason="Không xác minh được thông tin liên hệ.",
    )

    assert response.status_code == 302
    with app.app_context():
        application = db.session.get(OwnerApplication, application_id)
        unchanged_user = db.session.get(User, player.id)
        assert application.status == OwnerApplicationStatus.REJECTED.value
        assert application.rejection_reason == (
            "Không xác minh được thông tin liên hệ."
        )
        assert unchanged_user.role == UserRole.USER.value


def test_rejected_user_can_submit_a_new_application(app, client):
    player = create_user(app, email="player@example.com")
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)
    login(client, email=player.email)
    assert submit_application(client).status_code == 302
    client.post("/auth/logout")

    with app.app_context():
        application_id = db.session.scalar(
            db.select(OwnerApplication.id)
        )

    login(client, email=admin.email)
    review_application(
        client,
        application_id=application_id,
        decision=OwnerApplicationStatus.REJECTED,
        rejection_reason="Cần bổ sung thông tin.",
    )
    client.post("/auth/logout")

    login(client, email=player.email)
    response = submit_application(client, business_name="Sân bóng bổ sung")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(OwnerApplication.id))
        ) == 2
        assert db.session.scalar(
            db.select(db.func.count(OwnerApplication.id)).where(
                OwnerApplication.status
                == OwnerApplicationStatus.PENDING.value
            )
        ) == 1


def test_create_admin_cli_creates_hashed_admin(app):
    runner = app.test_cli_runner()

    result = runner.invoke(
        args=[
            "users",
            "create-admin",
            "--name",
            "Quản trị viên",
            "--email",
            "ADMIN@example.com",
            "--password",
            PASSWORD,
        ]
    )

    assert result.exit_code == 0
    assert "Đã tạo tài khoản ADMIN" in result.output
    with app.app_context():
        admin = db.session.scalar(
            db.select(User).where(User.email == "admin@example.com")
        )
        assert admin is not None
        assert admin.role == UserRole.ADMIN.value
        assert admin.password_hash != PASSWORD
        assert admin.check_password(PASSWORD)


def test_review_rolls_back_application_and_role_when_commit_fails(
    app,
    monkeypatch,
):
    player = create_user(app, email="player@example.com")
    admin = create_user(app, email="admin@example.com", role=UserRole.ADMIN)

    with app.app_context():
        player_model = db.session.get(User, player.id)
        application = submit_owner_application(
            user=player_model,
            business_name="Sân bóng Minh Anh",
            contact_phone="0901234567",
            note=None,
        )
        application_id = application.id
        admin_model = db.session.get(User, admin.id)
        original_rollback = db.session.rollback
        rollback_called = False

        def fail_commit():
            raise SQLAlchemyError("simulated commit failure")

        def track_rollback():
            nonlocal rollback_called
            rollback_called = True
            original_rollback()

        monkeypatch.setattr(db.session, "commit", fail_commit)
        monkeypatch.setattr(db.session, "rollback", track_rollback)

        with pytest.raises(OwnerApplicationError):
            review_owner_application(
                application_id=application_id,
                reviewer=admin_model,
                decision=OwnerApplicationStatus.APPROVED.value,
                rejection_reason=None,
            )

        assert rollback_called is True
        refreshed_application = db.session.get(
            OwnerApplication,
            application_id,
        )
        refreshed_player = db.session.get(User, player.id)
        assert (
            refreshed_application.status
            == OwnerApplicationStatus.PENDING.value
        )
        assert refreshed_player.role == UserRole.USER.value
