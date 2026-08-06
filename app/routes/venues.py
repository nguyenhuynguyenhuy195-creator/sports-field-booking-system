from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import ModerateVenueForm, VenueForm
from app.models import UserRole, VenueStatus
from app.services import (
    VenueError,
    VenueNotFoundError,
    VenuePermissionError,
    create_venue,
    get_owner_venue,
    get_public_venue,
    list_admin_venues,
    list_owner_venues,
    list_public_venues,
    moderate_venue,
    update_venue,
)


venues_bp = Blueprint("venues", __name__)

VENUE_STATUS_LABELS = {
    VenueStatus.PENDING.value: "Đang chờ duyệt",
    VenueStatus.ACTIVE.value: "Đang hoạt động",
    VenueStatus.HIDDEN.value: "Đã bị ẩn",
    VenueStatus.INACTIVE.value: "Ngừng hoạt động",
}


@venues_bp.get("/venues")
def index():
    return render_template(
        "venues/index.html",
        venues=list_public_venues(),
    )


@venues_bp.get("/venues/<int:venue_id>")
def detail(venue_id: int):
    try:
        venue = get_public_venue(venue_id)
    except VenueNotFoundError:
        abort(404)
    return render_template("venues/detail.html", venue=venue)


@venues_bp.get("/owner/venues")
@roles_required(UserRole.OWNER)
def owner_index():
    return render_template(
        "owner/venues/index.html",
        venues=list_owner_venues(current_user.id),
        status_labels=VENUE_STATUS_LABELS,
    )


@venues_bp.route("/owner/venues/new", methods=["GET", "POST"])
@roles_required(UserRole.OWNER)
def owner_create():
    form = VenueForm()
    if form.validate_on_submit():
        try:
            venue = create_venue(
                owner=current_user,
                name=form.name.data,
                address=form.address.data,
                district=form.district.data,
                city=form.city.data,
                phone=form.phone.data,
                description=form.description.data,
                opening_time=form.opening_time_value,
                closing_time=form.closing_time_value,
            )
        except VenueError as exc:
            flash(str(exc), "warning")
        else:
            flash(
                "Đã tạo cơ sở. Cơ sở đang chờ quản trị viên xét duyệt.",
                "success",
            )
            return redirect(url_for("venues.owner_index"))

    return render_template(
        "owner/venues/form.html",
        form=form,
        page_title="Thêm cơ sở",
        submit_label="Tạo cơ sở",
    )


@venues_bp.route(
    "/owner/venues/<int:venue_id>/edit",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_edit(venue_id: int):
    try:
        venue = get_owner_venue(
            venue_id=venue_id,
            owner_id=current_user.id,
        )
    except VenueNotFoundError:
        abort(404)
    except VenuePermissionError:
        abort(403)

    form = VenueForm(obj=venue)
    if not form.is_submitted():
        form.set_operating_hours(venue.opening_time, venue.closing_time)
    if form.validate_on_submit():
        try:
            update_venue(
                venue_id=venue_id,
                owner=current_user,
                name=form.name.data,
                address=form.address.data,
                district=form.district.data,
                city=form.city.data,
                phone=form.phone.data,
                description=form.description.data,
                opening_time=form.opening_time_value,
                closing_time=form.closing_time_value,
            )
        except VenuePermissionError:
            abort(403)
        except VenueNotFoundError:
            abort(404)
        except VenueError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã cập nhật thông tin cơ sở.", "success")
            return redirect(url_for("venues.owner_index"))

    return render_template(
        "owner/venues/form.html",
        form=form,
        page_title="Chỉnh sửa cơ sở",
        submit_label="Lưu thay đổi",
        venue=venue,
    )


@venues_bp.get("/admin/venues")
@roles_required(UserRole.ADMIN)
def admin_index():
    venues = list_admin_venues()
    moderation_forms = {}
    for venue in venues:
        form = ModerateVenueForm(prefix=f"venue-{venue.id}")
        form.decision.data = (
            VenueStatus.HIDDEN.value
            if venue.status == VenueStatus.ACTIVE.value
            else VenueStatus.ACTIVE.value
        )
        moderation_forms[venue.id] = form

    return render_template(
        "admin/venues.html",
        venues=venues,
        moderation_forms=moderation_forms,
        status_labels=VENUE_STATUS_LABELS,
    )


@venues_bp.post("/admin/venues/<int:venue_id>/moderate")
@roles_required(UserRole.ADMIN)
def admin_moderate(venue_id: int):
    form = ModerateVenueForm(prefix=f"venue-{venue_id}")
    if form.validate_on_submit():
        try:
            moderate_venue(
                venue_id=venue_id,
                reviewer=current_user,
                decision=form.decision.data,
                moderation_note=form.moderation_note.data,
            )
        except VenueNotFoundError:
            abort(404)
        except VenueError as exc:
            flash(str(exc), "warning")
        else:
            message = (
                "Đã duyệt và công khai cơ sở."
                if form.decision.data == VenueStatus.ACTIVE.value
                else "Đã ẩn cơ sở khỏi danh sách công khai."
            )
            flash(message, "success")
    else:
        first_error = next(
            (
                error
                for field_errors in form.errors.values()
                for error in field_errors
            ),
            "Dữ liệu kiểm duyệt không hợp lệ.",
        )
        flash(first_error, "danger")

    return redirect(url_for("venues.admin_index"))
