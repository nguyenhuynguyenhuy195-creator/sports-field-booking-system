from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import FieldForm
from app.models import FieldStatus, UserRole
from app.services import (
    FieldError,
    FieldNotFoundError,
    FieldPermissionError,
    create_field,
    get_owner_field,
    list_owner_fields,
    list_active_field_types,
    update_field,
)


fields_bp = Blueprint("fields", __name__)

FIELD_STATUS_LABELS = {
    FieldStatus.ACTIVE.value: "Đang hoạt động",
    FieldStatus.INACTIVE.value: "Chưa hoạt động",
}


@fields_bp.get("/owner/venues/<int:venue_id>/fields")
@roles_required(UserRole.OWNER)
def owner_index(venue_id: int):
    try:
        venue, fields = list_owner_fields(
            venue_id=venue_id,
            owner_id=current_user.id,
        )
    except FieldNotFoundError:
        abort(404)
    except FieldPermissionError:
        abort(403)

    return render_template(
        "owner/fields/index.html",
        venue=venue,
        fields=fields,
        field_status_labels=FIELD_STATUS_LABELS,
    )


@fields_bp.route(
    "/owner/venues/<int:venue_id>/fields/new",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_create(venue_id: int):
    try:
        venue, _ = list_owner_fields(
            venue_id=venue_id,
            owner_id=current_user.id,
        )
    except FieldNotFoundError:
        abort(404)
    except FieldPermissionError:
        abort(403)

    form = FieldForm()
    _configure_field_type_choices(form)
    if form.validate_on_submit():
        try:
            create_field(
                owner=current_user,
                venue_id=venue_id,
                name=form.name.data,
                field_type=form.field_type.data,
                surface_type=form.surface_type.data,
                capacity=form.capacity.data,
            )
        except FieldPermissionError:
            abort(403)
        except FieldNotFoundError:
            abort(404)
        except FieldError as exc:
            flash(str(exc), "warning")
        else:
            flash(
                "Đã thêm sân. Hãy cấu hình khung giá trước khi nhận đặt lịch.",
                "success",
            )
            return redirect(url_for("fields.owner_index", venue_id=venue_id))

    return render_template(
        "owner/fields/form.html",
        form=form,
        venue=venue,
        page_title="Thêm sân",
        submit_label="Tạo sân",
    )


@fields_bp.route(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/edit",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_edit(venue_id: int, field_id: int):
    try:
        field = get_owner_field(field_id=field_id, owner_id=current_user.id)
    except FieldNotFoundError:
        abort(404)
    except FieldPermissionError:
        abort(403)
    if field.venue_id != venue_id:
        abort(404)

    form = FieldForm(obj=field)
    _configure_field_type_choices(form)
    if not form.is_submitted():
        form.field_type.data = field.field_type.code
    if form.validate_on_submit():
        try:
            update_field(
                field_id=field_id,
                owner=current_user,
                name=form.name.data,
                field_type=form.field_type.data,
                surface_type=form.surface_type.data,
                capacity=form.capacity.data,
            )
        except FieldPermissionError:
            abort(403)
        except FieldNotFoundError:
            abort(404)
        except FieldError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã cập nhật thông tin sân.", "success")
            return redirect(url_for("fields.owner_index", venue_id=venue_id))

    return render_template(
        "owner/fields/form.html",
        form=form,
        venue=field.venue,
        field=field,
        page_title="Chỉnh sửa sân",
        submit_label="Lưu thay đổi",
    )


def _configure_field_type_choices(form: FieldForm) -> None:
    form.field_type.choices = [
        (
            field_type.code,
            f"{field_type.sport.name} — {field_type.name}",
        )
        for field_type in list_active_field_types()
    ]
