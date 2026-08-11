from flask import Flask

from app.decorators import roles_required
from app.extensions import db
from app.models import User, UserRole, UserStatus
from app.services import register_user


DEFAULT_PASSWORD = "MatKhauAnToan123"


def register(client, *, email="player@example.com", password=DEFAULT_PASSWORD):
    return client.post(
        "/auth/register",
        data={
            "full_name": "  Nguyễn   Văn A  ",
            "email": email,
            "phone": " 0901234567 ",
            "password": password,
            "confirm_password": password,
        },
    )


def login(client, *, email="player@example.com", password=DEFAULT_PASSWORD):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
    )


def test_auth_pages_render(client):
    assert client.get("/auth/register").status_code == 200
    assert client.get("/auth/login").status_code == 200


def test_registration_creates_normalized_user(app, client):
    response = register(client, email="Player@Example.COM")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "player@example.com")
        )
        assert user is not None
        assert user.full_name == "Nguyễn Văn A"
        assert user.phone == "0901234567"
        assert user.role == UserRole.USER.value
        assert user.status == UserStatus.ACTIVE.value
        assert user.password_hash != DEFAULT_PASSWORD
        assert user.check_password(DEFAULT_PASSWORD) is True


def test_registration_rejects_duplicate_email(app, client):
    assert register(client).status_code == 302

    response = register(client, email="PLAYER@example.com")

    assert response.status_code == 200
    assert "Email đã được sử dụng." in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id))) == 1


def test_registration_rejects_mismatched_password(app, client):
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Nguyễn Văn A",
            "email": "player@example.com",
            "phone": "",
            "password": DEFAULT_PASSWORD,
            "confirm_password": "KhongTrungKhop123",
        },
    )

    assert response.status_code == 200
    assert "Mật khẩu nhập lại không khớp." in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id))) == 0


def test_login_and_logout_complete_session_flow(app, client):
    with app.app_context():
        register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )

    login_response = login(client)
    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/")

    home_response = client.get("/")
    assert "Nguyễn Văn A" in home_response.get_data(as_text=True)
    assert "Đăng xuất" in home_response.get_data(as_text=True)
    assert "Mở menu tài khoản" in home_response.get_data(as_text=True)
    assert "Yêu cầu trở thành chủ sân" in home_response.get_data(as_text=True)
    assert home_response.content_type == "text/html; charset=utf-8"
    assert home_response.headers["Content-Language"] == "vi"

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 302

    anonymous_home = client.get("/")
    assert "Tạo tài khoản" in anonymous_home.get_data(as_text=True)


def test_login_rejects_wrong_password(app, client):
    with app.app_context():
        register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )

    response = login(client, password="SaiMatKhau")

    assert response.status_code == 200
    assert "Email hoặc mật khẩu không đúng." in response.get_data(as_text=True)


def test_locked_user_cannot_login(app, client):
    with app.app_context():
        user = register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )
        user.status = UserStatus.LOCKED.value
        db.session.commit()

    response = login(client)

    assert response.status_code == 200
    assert "Tài khoản hiện không thể đăng nhập." in response.get_data(as_text=True)


def test_login_does_not_redirect_to_external_url(app, client):
    with app.app_context():
        register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )

    response = client.post(
        "/auth/login?next=https://malicious.example",
        data={"email": "player@example.com", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert "malicious.example" not in response.headers["Location"]


def test_roles_required_rejects_user_without_permission(app: Flask, client):
    @app.get("/owner-only")
    @roles_required(UserRole.OWNER)
    def owner_only():
        return "owner"

    with app.app_context():
        register_user(
            full_name="Nguyễn Văn A",
            email="player@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )

    assert login(client).status_code == 302
    response = client.get("/owner-only")

    assert response.status_code == 403
    assert "Bạn không có quyền truy cập trang này" in response.get_data(as_text=True)
    assert response.content_type == "text/html; charset=utf-8"


def test_unicode_account_name_is_preserved_in_rendered_html(app, client):
    with app.app_context():
        register_user(
            full_name="Tài khoản kiểm thử Refund",
            email="refund@example.com",
            phone=None,
            password=DEFAULT_PASSWORD,
        )

    assert login(client, email="refund@example.com").status_code == 302

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tài khoản kiểm thử Refund" in html
    assert "T?i kho?n ki?m th? Refund" not in html


def test_unknown_route_uses_friendly_vietnamese_404_page(client):
    response = client.get("/duong-dan-khong-ton-tai")

    assert response.status_code == 404
    assert "Không tìm thấy trang bạn cần" in response.get_data(as_text=True)
    assert response.headers["Content-Language"] == "vi"
