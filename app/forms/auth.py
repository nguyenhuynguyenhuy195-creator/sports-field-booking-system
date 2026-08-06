from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp


class RegistrationForm(FlaskForm):
    full_name = StringField(
        "Họ và tên",
        validators=[
            DataRequired(message="Vui lòng nhập họ và tên."),
            Length(min=2, max=100, message="Họ và tên phải từ 2 đến 100 ký tự."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Vui lòng nhập email."),
            Email(message="Email không đúng định dạng."),
            Length(max=255, message="Email không được vượt quá 255 ký tự."),
        ],
    )
    phone = StringField(
        "Số điện thoại (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=20, message="Số điện thoại không được vượt quá 20 ký tự."),
            Regexp(
                r"^[0-9+().\s-]+$",
                message="Số điện thoại chứa ký tự không hợp lệ.",
            ),
        ],
    )
    password = PasswordField(
        "Mật khẩu",
        validators=[
            DataRequired(message="Vui lòng nhập mật khẩu."),
            Length(min=8, max=128, message="Mật khẩu phải từ 8 đến 128 ký tự."),
        ],
    )
    confirm_password = PasswordField(
        "Nhập lại mật khẩu",
        validators=[
            DataRequired(message="Vui lòng nhập lại mật khẩu."),
            EqualTo("password", message="Mật khẩu nhập lại không khớp."),
        ],
    )
    submit = SubmitField("Tạo tài khoản")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Vui lòng nhập email."),
            Email(message="Email không đúng định dạng."),
            Length(max=255, message="Email không được vượt quá 255 ký tự."),
        ],
    )
    password = PasswordField(
        "Mật khẩu",
        validators=[DataRequired(message="Vui lòng nhập mật khẩu.")],
    )
    remember = BooleanField("Ghi nhớ đăng nhập")
    submit = SubmitField("Đăng nhập")
