from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.decorators import roles_required
from app.forms import ModerateVenueForm, VenueForm, VenueSearchForm
from app.models import DAY_OF_WEEK_LABELS, UserRole, VenueStatus
from app.services import (
    VenueError,
    VenueNotFoundError,
    VenuePermissionError,
    build_google_maps_directions_url,
    create_venue,
    get_owner_venue,
    get_public_venue,
    list_admin_venues,
    list_owner_venues,
    list_active_field_types,
    list_active_sports,
    list_public_fields,
    moderate_venue,
    search_public_venues,
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
    form = VenueSearchForm(request.args)
    sports, field_types = _configure_catalog_choices(form)
    venue_results = []
    search_page = None
    search_is_valid = form.validate()
    if search_is_valid:
        try:
            search_page = search_public_venues(
                query=form.q.data,
                sport=form.sport.data,
                field_type=form.field_type.data,
                min_price=form.min_price.data,
                max_price=form.max_price.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
                radius_km=int(form.radius_km.data) if form.radius_km.data else None,
                page=request.args.get("page", 1, type=int) or 1,
            )
            venue_results = search_page.items
        except VenueError as exc:
            flash(str(exc), "danger")
            search_is_valid = False

    return render_template(
        "venues/index.html",
        form=form,
        venue_results=venue_results,
        sport_labels={item.code: item.name for item in sports},
        field_type_labels={item.code: item.name for item in field_types},
        search_page=search_page,
        pagination_params={
            "q": form.q.data or None,
            "sport": form.sport.data or None,
            "field_type": form.field_type.data or None,
            "min_price": form.min_price.data,
            "max_price": form.max_price.data,
            "latitude": form.latitude.data,
            "longitude": form.longitude.data,
            "radius_km": form.radius_km.data or None,
        },
        has_active_filters=any(
            request.args.get(name, "").strip()
            for name in (
                "q",
                "sport",
                "field_type",
                "min_price",
                "max_price",
                "radius_km",
            )
        ),
        search_is_valid=search_is_valid,
        google_maps_api_key=current_app.config.get(
            "GOOGLE_MAPS_BROWSER_API_KEY", ""
        ),
        map_markers=[
            {
                "name": result.venue.name,
                "latitude": float(result.venue.latitude),
                "longitude": float(result.venue.longitude),
                "detail_url": url_for(
                    "venues.detail", venue_id=result.venue.id
                ),
            }
            for result in venue_results
            if result.venue.has_coordinates
        ],
    )


@venues_bp.get("/venues/<int:venue_id>")
def detail(venue_id: int):
    try:
        venue = get_public_venue(venue_id)
    except VenueNotFoundError:
        abort(404)
    return render_template(
        "venues/detail.html",
        venue=venue,
        fields=list_public_fields(venue.id),
        day_labels=DAY_OF_WEEK_LABELS,
        directions_url=build_google_maps_directions_url(venue),
        google_maps_api_key=current_app.config.get(
            "GOOGLE_MAPS_BROWSER_API_KEY", ""
        ),
    )


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
                google_place_id=form.google_place_id.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
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
        google_maps_api_key=current_app.config.get(
            "GOOGLE_MAPS_BROWSER_API_KEY", ""
        ),
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
                google_place_id=form.google_place_id.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
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
        google_maps_api_key=current_app.config.get(
            "GOOGLE_MAPS_BROWSER_API_KEY", ""
        ),
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


def _configure_catalog_choices(form: VenueSearchForm):
    sports = list_active_sports()
    field_types = list_active_field_types()
    form.sport.choices = [("", "Tất cả bộ môn")] + [
        (sport.code, sport.name) for sport in sports
    ]
    form.field_type.choices = [
        ("", "Không giới hạn loại sân", {"data-sport": ""})
    ] + [
        (
            field_type.code,
            f"{field_type.sport.name} — {field_type.name}",
            {"data-sport": field_type.sport.code},
        )
        for field_type in field_types
    ]
    return sports, field_types
