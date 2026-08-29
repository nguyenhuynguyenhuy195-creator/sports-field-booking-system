from datetime import time

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    IntegerField,
    RadioField,
    SelectField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    ValidationError,
)

from app.models import BookingMode


BOOKING_HOUR_CHOICES = [(f"{hour:02d}", f"{hour:02d}") for hour in range(24)]
BOOKING_MINUTE_CHOICES = [("00", "00"), ("30", "30")]
BOOKING_MODE_CHOICES = [
    (
        BookingMode.DIRECT_BOOKING.value,
        "Đặt sân cho nhóm của tôi",
    ),
    (
        BookingMode.FIND_OPPONENT.value,
        "Tìm đối thủ — hai phía chia đôi khoản cọc",
    ),
    (
        BookingMode.FIND_PLAYERS.value,
        "Tìm thêm người — người ghép trả tại sân",
    ),
]


class BookingTimeQuoteForm(FlaskForm):
    """Validate only the date and interval used by booking Step 2."""

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


class BookingForm(BookingTimeQuoteForm):
    booking_mode = RadioField(
        "Mục đích đặt sân",
        choices=BOOKING_MODE_CHOICES,
        default=BookingMode.DIRECT_BOOKING.value,
        validators=[DataRequired(message="Vui lòng chọn mục đích đặt sân.")],
    )
    requested_players = IntegerField(
        "Số người muốn tìm thêm",
    )
    note = TextAreaField(
        "Ghi chú cho chủ sân",
        validators=[Length(max=500, message="Ghi chú tối đa 500 ký tự.")],
    )
    submit = SubmitField("Giữ chỗ và tiếp tục thanh toán")

    def validate_requested_players(self, field) -> None:
        if self.booking_mode.data == BookingMode.FIND_PLAYERS.value:
            if field.data is None:
                raise ValidationError(
                    "Vui lòng nhập số người bạn muốn tìm thêm."
                )
            if field.data < 1:
                raise ValidationError("Số người muốn tìm phải từ 1 trở lên.")
        elif field.data is not None:
            raise ValidationError(
                "Số người muốn tìm chỉ dùng cho hình thức tìm thêm người."
            )


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
