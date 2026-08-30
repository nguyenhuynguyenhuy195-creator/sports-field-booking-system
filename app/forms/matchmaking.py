from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from app.models import MatchType


MATCH_TYPE_CHOICES = [
    (MatchType.FIND_OPPONENT.value, "Tìm đội đối thủ"),
    (MatchType.FIND_PLAYERS.value, "Tìm thêm người chơi"),
]

MATCH_SEARCH_TYPE_CHOICES = [
    ("", "Tất cả loại kèo"),
    *MATCH_TYPE_CHOICES,
]

MATCH_SORT_CHOICES = [
    ("soonest", "Sắp diễn ra sớm nhất"),
    ("newest", "Mới đăng"),
]


class VietnameseSelectField(SelectField):
    def pre_validate(self, form) -> None:
        try:
            super().pre_validate(form)
        except ValidationError as exc:
            raise ValidationError("Lựa chọn không hợp lệ.") from exc


class VietnameseDateField(DateField):
    def process_formdata(self, valuelist) -> None:
        try:
            super().process_formdata(valuelist)
        except ValueError as exc:
            raise ValueError("Ngày chơi không hợp lệ.") from exc

SKILL_LEVEL_CHOICES = [
    ("", "Không yêu cầu"),
    ("BEGINNER", "Mới chơi"),
    ("INTERMEDIATE", "Trung bình"),
    ("ADVANCED", "Khá/Tốt"),
]


def _contact_phone_validators():
    return [
        DataRequired(message="Vui lòng nhập số điện thoại có Zalo."),
        Length(max=20, message="Số điện thoại tối đa 20 ký tự."),
        Regexp(
            r"^\+?[0-9][0-9 .-]{8,18}$",
            message="Số điện thoại không hợp lệ.",
        ),
    ]


class MatchSearchForm(FlaskForm):
    """Validate public matchmaking discovery filters from the query string."""

    class Meta:
        csrf = False

    province_code = VietnameseSelectField(
        "Tỉnh / Thành phố",
        choices=[("", "Tỉnh / Thành phố")],
        validators=[Optional()],
    )
    ward_code = VietnameseSelectField(
        "Phường / Xã",
        choices=[("", "Phường / Xã")],
        validators=[Optional()],
    )
    play_date = VietnameseDateField(
        "Ngày chơi",
        format="%Y-%m-%d",
        validators=[Optional()],
    )
    match_type = VietnameseSelectField(
        "Loại kèo",
        choices=MATCH_SEARCH_TYPE_CHOICES,
        validators=[Optional()],
    )
    sort = VietnameseSelectField(
        "Sắp xếp",
        choices=MATCH_SORT_CHOICES,
        default="soonest",
        validators=[DataRequired()],
    )

    def validate_ward_code(self, field) -> None:
        if field.data and not self.province_code.data:
            raise ValidationError(
                "Hãy chọn tỉnh hoặc thành phố trước khi chọn phường, xã."
            )


class MatchForm(FlaskForm):
    match_type = SelectField(
        "Loại kèo",
        choices=MATCH_TYPE_CHOICES,
        validators=[DataRequired(message="Vui lòng chọn loại kèo.")],
    )
    title = StringField(
        "Tiêu đề kèo",
        validators=[
            DataRequired(message="Vui lòng nhập tiêu đề kèo."),
            Length(max=200, message="Tiêu đề tối đa 200 ký tự."),
        ],
    )
    description = TextAreaField(
        "Mô tả",
        validators=[Length(max=2000, message="Mô tả tối đa 2.000 ký tự.")],
    )
    skill_level = SelectField(
        "Trình độ mong muốn",
        choices=SKILL_LEVEL_CHOICES,
        validators=[Optional()],
    )
    required_players = IntegerField(
        "Số người cần tìm",
        validators=[
            Optional(),
            NumberRange(min=1, message="Số người cần tìm phải từ 1 trở lên."),
        ],
    )
    contact_phone = StringField(
        "Số điện thoại có Zalo của người đăng kèo",
        validators=_contact_phone_validators(),
    )
    share_contact = BooleanField(
        "Tôi đồng ý chia sẻ số này cho người đã chính thức tham gia kèo.",
        validators=[
            DataRequired(message="Bạn cần đồng ý chia sẻ số liên hệ cho người tham gia.")
        ],
    )
    submit = SubmitField("Đăng kèo")


class MatchJoinForm(FlaskForm):
    contact_phone = StringField(
        "Số điện thoại có Zalo",
        validators=_contact_phone_validators(),
    )
    share_contact = BooleanField(
        "Tôi đồng ý chia sẻ số này cho người tạo kèo sau khi chính thức tham gia.",
        validators=[
            DataRequired(message="Bạn cần đồng ý chia sẻ số liên hệ cho người tạo kèo.")
        ],
    )
    message = TextAreaField(
        "Lời nhắn cho người tạo",
        validators=[Length(max=500, message="Lời nhắn tối đa 500 ký tự.")],
    )
    submit = SubmitField("Gửi yêu cầu tham gia")


class MatchActionForm(FlaskForm):
    submit = SubmitField("Xác nhận")


class MatchContactForm(FlaskForm):
    contact_phone = StringField(
        "Số điện thoại có Zalo",
        validators=_contact_phone_validators(),
    )
    share_contact = BooleanField(
        "Tôi đồng ý chia sẻ số này cho bên còn lại của kèo.",
        validators=[
            DataRequired(message="Bạn cần đồng ý chia sẻ số liên hệ.")
        ],
    )
    submit = SubmitField("Lưu số liên hệ")
