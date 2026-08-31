from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
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
    AdministrativeUnitError,
    VenueError,
    VenueNotFoundError,
    VenuePermissionError,
    build_google_maps_directions_url,
    create_venue,
    get_owner_venue,
    get_public_venue,
    list_admin_venues,
    list_owner_venue_summaries,
    list_active_field_types,
    list_active_sports,
    list_provinces,
    list_public_fields,
    list_wards,
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

ADMIN_VENUE_STATUS_LABELS = {
    VenueStatus.PENDING.value: "Chờ duyệt",
    VenueStatus.ACTIVE.value: "Đang hoạt động",
    VenueStatus.HIDDEN.value: "Đã ẩn",
    VenueStatus.INACTIVE.value: "Ngừng hoạt động",
}

ADMIN_VENUE_STATUS_FILTERS = {
    VenueStatus.PENDING.value: {
        "label": "Chờ duyệt",
        "list_heading": "Cơ sở cần kiểm duyệt",
        "sort_note": "Mới gửi gần đây ở trên cùng.",
        "empty_title": "Không còn cơ sở chờ duyệt",
        "empty_message": "Cơ sở mới do Chủ sân tạo sẽ xuất hiện tại đây.",
    },
    VenueStatus.ACTIVE.value: {
        "label": "Đang hoạt động",
        "list_heading": "Cơ sở đang công khai",
        "sort_note": "Hiển thị theo thời điểm tạo mới nhất.",
        "empty_title": "Chưa có cơ sở đang hoạt động",
        "empty_message": "Các cơ sở đã được duyệt sẽ xuất hiện tại đây.",
    },
    VenueStatus.HIDDEN.value: {
        "label": "Đã ẩn",
        "list_heading": "Cơ sở đang bị ẩn",
        "sort_note": "Có thể công khai lại khi dữ liệu vị trí đầy đủ.",
        "empty_title": "Chưa có cơ sở bị ẩn",
        "empty_message": "Cơ sở bị ẩn khỏi danh sách công khai sẽ xuất hiện tại đây.",
    },
}


@venues_bp.get("/venues")
def index():
    form = VenueSearchForm(request.args)
    sports, field_types, provinces, wards = _configure_catalog_choices(form)
    venue_results = []
    search_page = None
    search_is_valid = form.validate()
    if search_is_valid:
        try:
            search_page = search_public_venues(
                query=form.q.data,
                province_code=form.province_code.data,
                ward_code=form.ward_code.data,
                sport=form.sport.data,
                field_type=form.field_type.data,
                min_price=form.min_price.data,
                max_price=form.max_price.data,
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
        province_labels={item.code: item.name for item in provinces},
        ward_labels={item.code: item.full_name for item in wards},
        wards_api_url=url_for("venues.administrative_wards"),
        search_page=search_page,
        pagination_params={
            "q": form.q.data or None,
            "province_code": form.province_code.data or None,
            "ward_code": form.ward_code.data or None,
            "sport": form.sport.data or None,
            "field_type": form.field_type.data or None,
            "min_price": form.min_price.data,
            "max_price": form.max_price.data,
        },
        has_active_filters=any(
            request.args.get(name, "").strip()
            for name in (
                "q",
                "province_code",
                "ward_code",
                "sport",
                "field_type",
                "min_price",
                "max_price",
            )
        ),
        has_advanced_filters=any(
            request.args.get(name, "").strip()
            for name in (
                "field_type",
                "min_price",
                "max_price",
            )
        ),
        search_is_valid=search_is_valid,
    )


@venues_bp.get("/venues/<int:venue_id>")
def detail(venue_id: int):
    try:
        venue = get_public_venue(venue_id)
    except VenueNotFoundError:
        abort(404)
    directions_url = build_google_maps_directions_url(venue)
    return render_template(
        "venues/detail.html",
        venue=venue,
        fields=list_public_fields(venue.id),
        day_labels=DAY_OF_WEEK_LABELS,
        directions_url=directions_url,
    )


@venues_bp.get("/owner/venues")
@roles_required(UserRole.OWNER)
def owner_index():
    return render_template(
        "owner/venues/index.html",
        venue_summaries=list_owner_venue_summaries(current_user.id),
        status_labels=VENUE_STATUS_LABELS,
    )


@venues_bp.route("/owner/venues/new", methods=["GET", "POST"])
@roles_required(UserRole.OWNER)
def owner_create():
    form = VenueForm()
    _configure_administrative_choices(form)
    if form.validate_on_submit():
        try:
            venue = create_venue(
                owner=current_user,
                name=form.name.data,
                address=form.address.data,
                province_code=form.province_code.data,
                ward_code=form.ward_code.data,
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
        wards_api_url=url_for("venues.administrative_wards"),
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
    _configure_administrative_choices(form)
    if not form.is_submitted():
        form.set_operating_hours(venue.opening_time, venue.closing_time)
    if form.validate_on_submit():
        try:
            update_venue(
                venue_id=venue_id,
                owner=current_user,
                name=form.name.data,
                address=form.address.data,
                province_code=form.province_code.data,
                ward_code=form.ward_code.data,
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
        wards_api_url=url_for("venues.administrative_wards"),
    )


@venues_bp.get("/admin/venues")
@roles_required(UserRole.ADMIN)
def admin_index():
    selected_status = (
        request.args.get("status") or VenueStatus.PENDING.value
    ).strip().upper()
    if selected_status not in ADMIN_VENUE_STATUS_FILTERS:
        flash("Bộ lọc trạng thái cơ sở không hợp lệ.", "warning")
        return redirect(url_for("venues.admin_index"))

    venues = list_admin_venues(status=selected_status)
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
        status_labels=ADMIN_VENUE_STATUS_LABELS,
        status_filters=ADMIN_VENUE_STATUS_FILTERS,
        selected_status=selected_status,
        selected_filter=ADMIN_VENUE_STATUS_FILTERS[selected_status],
        directions_urls={
            venue.id: build_google_maps_directions_url(venue)
            for venue in venues
        },
    )


@venues_bp.get("/api/administrative-units/wards")
def administrative_wards():
    province_code = (request.args.get("province_code") or "").strip()
    try:
        wards = list_wards(province_code=province_code)
    except AdministrativeUnitError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "wards": [
                {
                    "code": ward.code,
                    "name": ward.full_name,
                    "type": ward.type,
                }
                for ward in wards
            ]
        }
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

    return_status = (request.form.get("return_status") or "").strip().upper()
    if return_status not in ADMIN_VENUE_STATUS_FILTERS:
        return_status = VenueStatus.PENDING.value
    return redirect(url_for("venues.admin_index", status=return_status))


def _configure_catalog_choices(form: VenueSearchForm):
    sports = list_active_sports()
    field_types = list_active_field_types()
    provinces = list_provinces()
    form.sport.choices = [("", "Bộ môn")] + [
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
    form.province_code.choices = [("", "Tỉnh / Thành phố")] + [
        (province.code, province.name) for province in provinces
    ]
    selected_province_code = (form.province_code.data or "").strip()
    wards = ()
    if selected_province_code:
        try:
            wards = list_wards(province_code=selected_province_code)
        except AdministrativeUnitError:
            wards = ()
    form.ward_code.choices = [("", "Phường / Xã")] + [
        (ward.code, ward.full_name) for ward in wards
    ]
    return sports, field_types, provinces, wards


def _configure_administrative_choices(form: VenueForm) -> None:
    form.province_code.choices = [("", "Chọn tỉnh hoặc thành phố")] + [
        (province.code, province.name) for province in list_provinces()
    ]
    selected_province_code = (form.province_code.data or "").strip()
    wards = ()
    if selected_province_code:
        try:
            wards = list_wards(province_code=selected_province_code)
        except AdministrativeUnitError:
            wards = ()
    form.ward_code.choices = [("", "Chọn phường, xã")] + [
        (ward.code, ward.full_name) for ward in wards
    ]
