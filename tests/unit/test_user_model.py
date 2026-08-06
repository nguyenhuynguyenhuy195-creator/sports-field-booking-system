from app.models import User, UserRole, UserStatus


def test_user_password_is_hashed_and_verifiable():
    user = User(
        full_name="Nguyễn Văn A",
        email="player@example.com",
        role=UserRole.USER.value,
        status=UserStatus.ACTIVE.value,
    )

    user.set_password("MatKhauAnToan123")

    assert user.password_hash != "MatKhauAnToan123"
    assert user.check_password("MatKhauAnToan123") is True
    assert user.check_password("SaiMatKhau") is False


def test_locked_user_is_not_active():
    user = User(
        full_name="Nguyễn Văn A",
        email="locked@example.com",
        password_hash="not-used",
        role=UserRole.USER.value,
        status=UserStatus.LOCKED.value,
    )

    assert user.is_active is False


def test_role_helpers_reflect_stored_role():
    owner = User(
        full_name="Chủ sân",
        email="owner@example.com",
        password_hash="not-used",
        role=UserRole.OWNER.value,
        status=UserStatus.ACTIVE.value,
    )

    assert owner.is_owner is True
    assert owner.is_admin is False
