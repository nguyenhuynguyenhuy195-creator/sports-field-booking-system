from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from app.models import FieldType


FIELD_TYPE_CHOICES = [
    (FieldType.FIVE_A_SIDE.value, "Sân bóng 5 người"),
    (FieldType.SEVEN_A_SIDE.value, "Sân bóng 7 người"),
    (FieldType.ELEVEN_A_SIDE.value, "Sân bóng 11 người"),
]


class FieldForm(FlaskForm):
    name = StringField(
        "Tên sân",
        validators=[
            DataRequired(message="Vui lòng nhập tên sân."),
            Length(min=1, max=100, message="Tên sân tối đa 100 ký tự."),
        ],
    )
    field_type = SelectField(
        "Loại sân",
        choices=FIELD_TYPE_CHOICES,
        validators=[DataRequired(message="Vui lòng chọn loại sân.")],
    )
    surface_type = StringField(
        "Loại mặt sân (không bắt buộc)",
        validators=[
            Optional(),
            Length(max=50, message="Loại mặt sân tối đa 50 ký tự."),
        ],
    )
    capacity = IntegerField(
        "Sức chứa tối đa",
        validators=[
            InputRequired(message="Vui lòng nhập sức chứa."),
            NumberRange(min=1, message="Sức chứa phải lớn hơn 0."),
        ],
    )
    submit = SubmitField("Lưu sân")
