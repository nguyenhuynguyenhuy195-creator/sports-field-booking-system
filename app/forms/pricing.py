from datetime import time

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange, ValidationError

from app.models import DAY_OF_WEEK_LABELS


HOUR_CHOICES = [(f"{hour:02d}", f"{hour:02d}") for hour in range(24)]
MINUTE_CHOICES = [(f"{minute:02d}", f"{minute:02d}") for minute in range(60)]
DAY_CHOICES = list(DAY_OF_WEEK_LABELS.items())


class PriceSlotForm(FlaskForm):
    day_of_week = SelectField(
        "Ngày áp dụng",
        choices=DAY_CHOICES,
        coerce=int,
        default=0,
        validators=[InputRequired(message="Vui lòng chọn ngày áp dụng.")],
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
    hourly_price = DecimalField(
        "Giá mỗi giờ (VNĐ)",
        places=2,
        validators=[
            InputRequired(message="Vui lòng nhập giá theo giờ."),
            NumberRange(min=1, message="Giá theo giờ phải lớn hơn 0."),
        ],
    )
    submit = SubmitField("Lưu khung giá")

    @property
    def start_time_value(self) -> time:
        return self._combine_time(self.start_hour.data, self.start_minute.data)

    @property
    def end_time_value(self) -> time:
        return self._combine_time(self.end_hour.data, self.end_minute.data)

    @staticmethod
    def _combine_time(hour: str, minute: str) -> time:
        return time(int(hour), int(minute))

    def set_times(self, start_time: time, end_time: time) -> None:
        self.start_hour.data = f"{start_time.hour:02d}"
        self.start_minute.data = f"{start_time.minute:02d}"
        self.end_hour.data = f"{end_time.hour:02d}"
        self.end_minute.data = f"{end_time.minute:02d}"

    def validate_end_hour(self, field) -> None:
        try:
            start_time = self.start_time_value
            end_time = self.end_time_value
        except (TypeError, ValueError):
            return
        if start_time >= end_time:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")


class PricingActionForm(FlaskForm):
    submit = SubmitField("Xác nhận")
