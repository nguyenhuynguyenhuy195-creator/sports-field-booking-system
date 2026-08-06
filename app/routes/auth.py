from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms import LoginForm, RegistrationForm
from app.models import UserStatus
from app.services import DuplicateEmailError, find_user_by_email, register_user


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_safe_local_url(target: str | None) -> bool:
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            register_user(
                full_name=form.full_name.data,
                email=form.email.data,
                phone=form.phone.data,
                password=form.password.data,
            )
        except DuplicateEmailError as exc:
            form.email.errors.append(str(exc))
        else:
            flash("Tạo tài khoản thành công. Bạn có thể đăng nhập ngay.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = find_user_by_email(form.email.data)
        if user is None or not user.check_password(form.password.data):
            flash("Email hoặc mật khẩu không đúng.", "danger")
        elif user.status != UserStatus.ACTIVE.value:
            flash(
                "Tài khoản hiện không thể đăng nhập. Vui lòng liên hệ quản trị viên.",
                "warning",
            )
        else:
            login_user(user, remember=form.remember.data)
            flash(f"Chào mừng {user.full_name} quay lại!", "success")
            next_url = request.args.get("next")
            if _is_safe_local_url(next_url):
                return redirect(next_url)
            return redirect(url_for("main.home"))

    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("main.home"))
