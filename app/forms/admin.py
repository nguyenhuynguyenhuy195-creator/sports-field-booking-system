from flask_wtf import FlaskForm
from wtforms import HiddenField, SubmitField
from wtforms.validators import AnyOf, DataRequired

from app.models import UserStatus


class AdminAccountStatusForm(FlaskForm):
    status = HiddenField(
        validators=[
            DataRequired(message="Thiếu trạng thái tài khoản."),
            AnyOf(
                [UserStatus.ACTIVE.value, UserStatus.LOCKED.value],
                message="Trạng thái tài khoản không hợp lệ.",
            ),
        ]
    )
    submit = SubmitField("Cập nhật")
