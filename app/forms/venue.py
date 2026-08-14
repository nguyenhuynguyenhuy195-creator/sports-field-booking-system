from datetime import time

from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    HiddenField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.widgets import HiddenInput
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from app.models import VenueStatus


HOUR_CHOICES = [(f"{hour:02d}", f"{hour:02d}") for hour in range(24)]
MINUTE_CHOICES = [(f"{minute:02d}", f"{minute:02d}") for minute in range(60)]
class VenueSearchForm(FlaskForm):
    """Validate public venue filters submitted through the query string."""

    class Meta:
        csrf = False

    q = StringField(
        "Tên sân hoặc khu vực",
        validators=[
            Optional(),
            Length(max=150, message="Nội dung tìm kiếm tối đa 150 ký tự."),
        ],
    )
    sport = SelectField(
        "Bộ môn",
        choices=[("", "Tất cả bộ môn")],
        validators=[Optional()],
    )
    field_type = SelectField(
        "Loại sân",
        choices=[("", "Không giới hạn loại sân")],
        validators=[Optional()],
    )
    min_price = DecimalField(
        "Giá từ",
        places=0,
        validators=[
            Optional(),
            NumberRange(
                min=0,
                max=10_000_000,
                message="Giá phải từ 0 đến 10.000.000 đồng/giờ.",
            ),
        ],
    )
    max_price = DecimalField(
        "Giá đến",
        places=0,
        validators=[
            Optional(),
            NumberRange(
                min=0,
                max=10_000_000,
                message="Giá phải từ 0 đến 10.000.000 đồng/giờ.",
            ),
        ],
    )
    latitude = DecimalField(
        "Vĩ độ hiện tại",
        places=6,
        widget=HiddenInput(),
        validators=[
            Optional(),
            NumberRange(min=-90, max=90, message="Vĩ độ không hợp lệ."),
        ],
    )
    longitude = DecimalField(
        "Kinh độ hiện tại",
        places=6,
        widget=HiddenInput(),
        validators=[
            Optional(),
            NumberRange(min=-180, max=180, message="Kinh độ không hợp lệ."),
        ],
    )
    radius_km = SelectField(
        "Bán kính",
        choices=[
            ("", "Không giới hạn khoảng cách"),
            ("3", "Trong 3 km"),
            ("5", "Trong 5 km"),
            ("10", "Trong 10 km"),
        ],
        validators=[Optional()],
    )

    def validate_max_price(self, field) -> None:
        if (
            self.min_price.data is not None
            and field.data is not None
            and self.min_price.data > field.data
        ):
            raise ValidationError(
                "Giá tối thiểu không được lớn hơn giá tối đa."
            )

    def validate_radius_km(self, field) -> None:
        has_coordinates = (
            self.latitude.data is not None and self.longitude.data is not None
        )
        has_partial_coordinates = (
            self.latitude.data is not None or self.longitude.data is not None
        )
        if has_partial_coordinates and not has_coordinates:
            raise ValidationError("Vị trí hiện tại chưa đầy đủ.")
        if field.data and not has_coordinates:
            raise ValidationError(
                "Hãy bấm “Dùng vị trí của tôi” trước khi tìm theo bán kính."
            )


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
    google_place_id = HiddenField(
        "Google Place ID",
        validators=[Optional(), Length(max=255)],
    )
    latitude = DecimalField(
        "Vĩ độ",
        places=6,
        widget=HiddenInput(),
        validators=[
            Optional(),
            NumberRange(min=-90, max=90, message="Vĩ độ không hợp lệ."),
        ],
    )
    longitude = DecimalField(
        "Kinh độ",
        places=6,
        widget=HiddenInput(),
        validators=[
            Optional(),
            NumberRange(min=-180, max=180, message="Kinh độ không hợp lệ."),
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

    def validate_google_place_id(self, field) -> None:
        has_place_id = bool((field.data or "").strip())
        has_latitude = self.latitude.data is not None
        has_longitude = self.longitude.data is not None
        if any((has_place_id, has_latitude, has_longitude)) and not all(
            (has_place_id, has_latitude, has_longitude)
        ):
            raise ValidationError(
                "Vị trí Google chưa đầy đủ. Hãy chọn lại một gợi ý địa chỉ."
            )


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
