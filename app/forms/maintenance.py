from datetime import time

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, ValidationError

from .pricing import HOUR_CHOICES, MINUTE_CHOICES


class MaintenanceForm(FlaskForm):
    maintenance_date = DateField(
        "Ngày bảo trì",
        format="%Y-%m-%d",
        validators=[InputRequired(message="Vui lòng chọn ngày bảo trì.")],
    )
    start_hour = SelectField(
        "Giờ bắt đầu",
        choices=HOUR_CHOICES,
        default="06",
        validators=[DataRequired(message="Vui lòng chọn giờ bắt đầu.")],
    )
    start_minute = SelectField(
        "Phút bắt đầu",
        choices=MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút bắt đầu.")],
    )
    end_hour = SelectField(
        "Giờ kết thúc",
        choices=HOUR_CHOICES,
        default="07",
        validators=[DataRequired(message="Vui lòng chọn giờ kết thúc.")],
    )
    end_minute = SelectField(
        "Phút kết thúc",
        choices=MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút kết thúc.")],
    )
    reason = TextAreaField(
        "Lý do bảo trì",
        validators=[
            DataRequired(message="Vui lòng nhập lý do bảo trì."),
            Length(max=500, message="Lý do bảo trì tối đa 500 ký tự."),
        ],
    )
    submit = SubmitField("Tạo lịch bảo trì")

    @property
    def start_time_value(self) -> time:
        return self._combine_time(self.start_hour.data, self.start_minute.data)

    @property
    def end_time_value(self) -> time:
        return self._combine_time(self.end_hour.data, self.end_minute.data)

    @staticmethod
    def _combine_time(hour: str, minute: str) -> time:
        return time(int(hour), int(minute))

    def validate_end_hour(self, field) -> None:
        try:
            start_time = self.start_time_value
            end_time = self.end_time_value
        except (TypeError, ValueError):
            return
        if start_time >= end_time:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")


class MaintenanceActionForm(FlaskForm):
    submit = SubmitField("Xác nhận")
