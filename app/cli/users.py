import click
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User, UserRole, UserStatus
from app.services.auth import (
    find_user_by_email,
    normalize_email,
    normalize_full_name,
)


users_cli = AppGroup("users", help="Quản lý tài khoản hệ thống.")


@users_cli.command("create-admin")
@click.option("--name", prompt="Họ và tên quản trị viên")
@click.option("--email", prompt="Email quản trị viên")
@click.password_option(
    prompt="Mật khẩu",
    confirmation_prompt="Nhập lại mật khẩu",
)
def create_admin(name: str, email: str, password: str) -> None:
    """Create the first admin without exposing public admin registration."""
    normalized_email = normalize_email(email)
    if find_user_by_email(normalized_email) is not None:
        raise click.ClickException("Email đã tồn tại trong hệ thống.")
    if len(password) < 8 or len(password) > 128:
        raise click.ClickException("Mật khẩu phải từ 8 đến 128 ký tự.")

    admin = User(
        full_name=normalize_full_name(name),
        email=normalized_email,
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    admin.set_password(password)
    db.session.add(admin)

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise click.ClickException("Không thể tạo tài khoản quản trị viên.") from exc

    click.echo(f"Đã tạo tài khoản ADMIN: {admin.email}")
