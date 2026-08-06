from flask_wtf import FlaskForm
from wtforms import RadioField, StringField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from app.models import OwnerApplicationStatus


class OwnerApplicationForm(FlaskForm):
    business_name = StringField(
        "Tên cơ sở hoặc hộ kinh doanh",
        validators=[
            DataRequired(message="Vui lòng nhập tên cơ sở hoặc hộ kinh doanh."),
            Length(min=2, max=150, message="Tên phải từ 2 đến 150 ký tự."),
        ],
    )
    contact_phone = StringField(
        "Số điện thoại liên hệ",
        validators=[
            DataRequired(message="Vui lòng nhập số điện thoại liên hệ."),
            Length(max=20, message="Số điện thoại không được vượt quá 20 ký tự."),
            Regexp(
                r"^[0-9+().\s-]+$",
                message="Số điện thoại chứa ký tự không hợp lệ.",
            ),
        ],
    )
    note = TextAreaField(
        "Thông tin bổ sung (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=500, message="Thông tin bổ sung tối đa 500 ký tự."),
        ],
    )
    submit = SubmitField("Gửi yêu cầu")


class ReviewOwnerApplicationForm(FlaskForm):
    decision = RadioField(
        "Kết quả xét duyệt",
        choices=[
            (OwnerApplicationStatus.APPROVED.value, "Chấp nhận"),
            (OwnerApplicationStatus.REJECTED.value, "Từ chối"),
        ],
        validators=[DataRequired(message="Vui lòng chọn kết quả xét duyệt.")],
    )
    rejection_reason = TextAreaField(
        "Lý do từ chối",
        validators=[
            Optional(),
            Length(max=500, message="Lý do từ chối tối đa 500 ký tự."),
        ],
    )
    submit = SubmitField("Lưu kết quả")

    def validate_rejection_reason(self, field) -> None:
        if (
            self.decision.data == OwnerApplicationStatus.REJECTED.value
            and not (field.data or "").strip()
        ):
            raise ValidationError("Phải nhập lý do khi từ chối yêu cầu.")
