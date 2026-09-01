from flask import Blueprint, abort, flash, redirect, send_file, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import MediaActionForm, MediaUploadForm
from app.models import UserRole
from app.services import (
    MediaError,
    MediaNotFoundError,
    MediaPermissionError,
    delete_field_image,
    delete_venue_image,
    get_visible_image,
    resolve_media_path,
    set_field_cover,
    set_venue_cover,
    upload_field_image,
    upload_venue_image,
)


media_bp = Blueprint("media", __name__)


@media_bp.get("/media/<int:media_id>")
def image(media_id: int):
    viewer_owner_id = (
        current_user.id
        if current_user.is_authenticated
        and current_user.role == UserRole.OWNER.value
        else None
    )
    try:
        media = get_visible_image(
            media_id=media_id,
            viewer_owner_id=viewer_owner_id,
        )
        path = resolve_media_path(media)
    except MediaNotFoundError:
        abort(404)
    if not path.is_file():
        abort(404)
    response = send_file(
        path,
        mimetype=media.content_type,
        conditional=True,
        etag=True,
        max_age=86400,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@media_bp.post("/owner/venues/<int:venue_id>/media")
@roles_required(UserRole.OWNER)
def venue_upload(venue_id: int):
    form = MediaUploadForm()
    if not form.validate_on_submit():
        _flash_first_form_error(form)
        return redirect(url_for("venues.owner_edit", venue_id=venue_id))
    try:
        upload_venue_image(
            owner_id=current_user.id,
            venue_id=venue_id,
            file=form.image.data,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã tải ảnh cơ sở lên.", "success")
    return redirect(url_for("venues.owner_edit", venue_id=venue_id))


@media_bp.post(
    "/owner/venues/<int:venue_id>/media/<int:media_id>/cover"
)
@roles_required(UserRole.OWNER)
def venue_cover(venue_id: int, media_id: int):
    _validate_action_form()
    try:
        set_venue_cover(
            owner_id=current_user.id,
            venue_id=venue_id,
            media_id=media_id,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã đổi ảnh đại diện của cơ sở.", "success")
    return redirect(url_for("venues.owner_edit", venue_id=venue_id))


@media_bp.post(
    "/owner/venues/<int:venue_id>/media/<int:media_id>/delete"
)
@roles_required(UserRole.OWNER)
def venue_delete(venue_id: int, media_id: int):
    _validate_action_form()
    try:
        delete_venue_image(
            owner_id=current_user.id,
            venue_id=venue_id,
            media_id=media_id,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã xóa ảnh cơ sở.", "success")
    return redirect(url_for("venues.owner_edit", venue_id=venue_id))


@media_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/media"
)
@roles_required(UserRole.OWNER)
def field_upload(venue_id: int, field_id: int):
    form = MediaUploadForm()
    if not form.validate_on_submit():
        _flash_first_form_error(form)
        return redirect(
            url_for(
                "fields.owner_edit",
                venue_id=venue_id,
                field_id=field_id,
            )
        )
    try:
        upload_field_image(
            owner_id=current_user.id,
            venue_id=venue_id,
            field_id=field_id,
            file=form.image.data,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã tải ảnh sân lên.", "success")
    return redirect(
        url_for(
            "fields.owner_edit",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


@media_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/media/"
    "<int:media_id>/cover"
)
@roles_required(UserRole.OWNER)
def field_cover(venue_id: int, field_id: int, media_id: int):
    _validate_action_form()
    try:
        set_field_cover(
            owner_id=current_user.id,
            venue_id=venue_id,
            field_id=field_id,
            media_id=media_id,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã đổi ảnh đại diện của sân.", "success")
    return redirect(
        url_for(
            "fields.owner_edit",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


@media_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/media/"
    "<int:media_id>/delete"
)
@roles_required(UserRole.OWNER)
def field_delete(venue_id: int, field_id: int, media_id: int):
    _validate_action_form()
    try:
        delete_field_image(
            owner_id=current_user.id,
            venue_id=venue_id,
            field_id=field_id,
            media_id=media_id,
        )
    except MediaNotFoundError:
        abort(404)
    except MediaPermissionError:
        abort(403)
    except MediaError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã xóa ảnh sân.", "success")
    return redirect(
        url_for(
            "fields.owner_edit",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


def _validate_action_form() -> None:
    if not MediaActionForm().validate_on_submit():
        abort(400)


def _flash_first_form_error(form: MediaUploadForm) -> None:
    message = next(
        (
            error
            for errors in form.errors.values()
            for error in errors
        ),
        "Dữ liệu ảnh không hợp lệ.",
    )
    flash(message, "warning")
