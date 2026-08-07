from datetime import time

from flask_wtf import FlaskForm
from wtforms import DateField, RadioField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, ValidationError

from app.models import BookingPaymentMode


BOOKING_HOUR_CHOICES = [(f"{hour:02d}", f"{hour:02d}") for hour in range(24)]
BOOKING_MINUTE_CHOICES = [("00", "00"), ("30", "30")]
PAYMENT_MODE_CHOICES = [
    (
        BookingPaymentMode.FULL_PAYMENT.value,
        "Thanh toán toàn bộ tiền sân",
    ),
    (
        BookingPaymentMode.SPLIT_OPPONENT.value,
        "Tìm đối thủ và chia tiền 50/50",
    ),
    (
        BookingPaymentMode.SPLIT_PLAYERS.value,
        "Tìm thêm người và chia theo đầu người",
    ),
]


class BookingForm(FlaskForm):
    booking_date = DateField(
        "Ngày đặt sân",
        format="%Y-%m-%d",
        validators=[InputRequired(message="Vui lòng chọn ngày đặt sân.")],
    )
    start_hour = SelectField(
        "Giờ bắt đầu",
        choices=BOOKING_HOUR_CHOICES,
        default="18",
        validators=[DataRequired(message="Vui lòng chọn giờ bắt đầu.")],
    )
    start_minute = SelectField(
        "Phút bắt đầu",
        choices=BOOKING_MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút bắt đầu.")],
    )
    end_hour = SelectField(
        "Giờ kết thúc",
        choices=BOOKING_HOUR_CHOICES,
        default="19",
        validators=[DataRequired(message="Vui lòng chọn giờ kết thúc.")],
    )
    end_minute = SelectField(
        "Phút kết thúc",
        choices=BOOKING_MINUTE_CHOICES,
        default="00",
        validators=[DataRequired(message="Vui lòng chọn phút kết thúc.")],
    )
    payment_mode = RadioField(
        "Hình thức thanh toán",
        choices=PAYMENT_MODE_CHOICES,
        default=BookingPaymentMode.FULL_PAYMENT.value,
        validators=[DataRequired(message="Vui lòng chọn hình thức thanh toán.")],
    )
    note = TextAreaField(
        "Ghi chú cho chủ sân",
        validators=[Length(max=500, message="Ghi chú tối đa 500 ký tự.")],
    )
    submit = SubmitField("Giữ chỗ và tiếp tục thanh toán")

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


class BookingActionForm(FlaskForm):
    submit = SubmitField("Xác nhận")


class BookingReasonForm(FlaskForm):
    reason = TextAreaField(
        "Lý do",
        validators=[
            DataRequired(message="Vui lòng nhập lý do."),
            Length(max=500, message="Lý do tối đa 500 ký tự."),
        ],
    )
    submit = SubmitField("Xác nhận")
