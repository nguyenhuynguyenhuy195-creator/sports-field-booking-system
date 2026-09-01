from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import SubmitField


class MediaUploadForm(FlaskForm):
    image = FileField(
        "Chọn ảnh",
        validators=[FileRequired(message="Vui lòng chọn một tệp ảnh.")],
    )
    submit = SubmitField("Tải ảnh lên")


class MediaActionForm(FlaskForm):
    submit = SubmitField("Xác nhận")
