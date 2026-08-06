from datetime import time

from flask_wtf import FlaskForm
from wtforms import RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from app.models import VenueStatus


HOUR_CHOICES = [(f"{hour:02d}", f"{hour:02d}") for hour in range(24)]
MINUTE_CHOICES = [(f"{minute:02d}", f"{minute:02d}") for minute in range(60)]


class VenueForm(FlaskForm):
    name = StringField(
        "Tên cơ sở thể thao",
        validators=[
            DataRequired(message="Vui lòng nhập tên cơ sở."),
            Length(min=2, max=150, message="Tên phải từ 2 đến 150 ký tự."),
        ],
    )
    address = StringField(
        "Địa chỉ",
        validators=[
            DataRequired(message="Vui lòng nhập địa chỉ."),
            Length(min=5, max=255, message="Địa chỉ phải từ 5 đến 255 ký tự."),
        ],
    )
    district = StringField(
        "Quận, huyện (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=100, message="Quận, huyện tối đa 100 ký tự."),
        ],
    )
    city = StringField(
        "Tỉnh, thành phố",
        validators=[
            DataRequired(message="Vui lòng nhập tỉnh hoặc thành phố."),
            Length(min=2, max=100, message="Tỉnh, thành phố tối đa 100 ký tự."),
        ],
    )
    phone = StringField(
        "Số điện thoại cơ sở (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=20, message="Số điện thoại tối đa 20 ký tự."),
            Regexp(
                r"^[0-9+().\s-]+$",
                message="Số điện thoại chứa ký tự không hợp lệ.",
            ),
        ],
    )
    description = TextAreaField(
        "Mô tả (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=2000, message="Mô tả tối đa 2.000 ký tự."),
        ],
    )
    opening_hour = SelectField(
        "Giờ mở cửa",
        choices=HOUR_CHOICES,
        default="06",
        validators=[DataRequired(message="Vui lòng chọn giờ mở cửa.")],
    )
    opening_minute = SelectField(
        "Phút mở cửa",
        choices=MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút mở cửa.")],
    )
    closing_hour = SelectField(
        "Giờ đóng cửa",
        choices=HOUR_CHOICES,
        default="23",
        validators=[DataRequired(message="Vui lòng chọn giờ đóng cửa.")],
    )
    closing_minute = SelectField(
        "Phút đóng cửa",
        choices=MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút đóng cửa.")],
    )
    submit = SubmitField("Lưu cơ sở")

    @property
    def opening_time_value(self) -> time:
        return self._combine_time(
            self.opening_hour.data,
            self.opening_minute.data,
        )

    @property
    def closing_time_value(self) -> time:
        return self._combine_time(
            self.closing_hour.data,
            self.closing_minute.data,
        )

    @staticmethod
    def _combine_time(hour: str, minute: str) -> time:
        return time(int(hour), int(minute))

    def set_operating_hours(self, opening_time: time, closing_time: time) -> None:
        """Populate the split controls when an owner edits an existing venue."""
        self.opening_hour.data = f"{opening_time.hour:02d}"
        self.opening_minute.data = f"{opening_time.minute:02d}"
        self.closing_hour.data = f"{closing_time.hour:02d}"
        self.closing_minute.data = f"{closing_time.minute:02d}"

    def validate_closing_hour(self, field) -> None:
        try:
            opening_time = self.opening_time_value
            closing_time = self.closing_time_value
        except (TypeError, ValueError):
            return
        if opening_time >= closing_time:
            raise ValidationError("Giờ đóng cửa phải sau giờ mở cửa.")


class ModerateVenueForm(FlaskForm):
    decision = RadioField(
        "Trạng thái kiểm duyệt",
        choices=[
            (VenueStatus.ACTIVE.value, "Duyệt và hiển thị"),
            (VenueStatus.HIDDEN.value, "Ẩn cơ sở"),
        ],
        validators=[DataRequired(message="Vui lòng chọn trạng thái.")],
    )
    moderation_note = TextAreaField(
        "Ghi chú kiểm duyệt (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=500, message="Ghi chú tối đa 500 ký tự."),
        ],
    )
    submit = SubmitField("Lưu kết quả")
