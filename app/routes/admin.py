from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import AdminAccountStatusForm, ReviewOwnerApplicationForm
from app.models import (
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    MatchParticipantStatus,
    MatchParticipantType,
    MatchStatus,
    MatchType,
    OwnerApplicationStatus,
    PaymentProvider,
    PaymentStatus,
    RefundStatus,
    UserRole,
    UserStatus,
)
from app.services import (
    AdminError,
    get_admin_account_detail,
    get_admin_account_summary,
    get_admin_booking_filter_options,
    get_admin_booking,
    get_admin_dashboard_summary,
    get_admin_monitoring_location,
    list_admin_accounts,
    list_admin_booking_operations,
    list_admin_bookings,
    list_admin_catalog,
    list_admin_matches,
    list_admin_monitoring_provinces,
    list_admin_monitoring_wards,
    list_admin_monitoring_locations,
    list_owner_applications,
    review_owner_application,
    set_admin_account_status,
)
from app.services.owner_application import OwnerApplicationError


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


ROLE_LABELS = {
    UserRole.USER.value: "Người dùng",
    UserRole.OWNER.value: "Chủ sân",
    UserRole.ADMIN.value: "Quản trị viên",
}

ACCOUNT_STATUS_LABELS = {
    UserStatus.ACTIVE.value: "Đang hoạt động",
    UserStatus.LOCKED.value: "Đã khóa",
    UserStatus.INACTIVE.value: "Ngừng hoạt động",
}

BOOKING_STATUS_LABELS = {
    BookingStatus.PENDING.value: "Chờ xác nhận",
    BookingStatus.CONFIRMED.value: "Đang giữ chỗ",
    BookingStatus.PARTIALLY_PAID.value: "Đã cọc một phần",
    BookingStatus.PAID.value: "Đã thanh toán cọc",
    BookingStatus.REFUND_PENDING.value: "Đang hoàn tiền",
    BookingStatus.COMPLETED.value: "Đã hoàn thành",
    BookingStatus.REJECTED.value: "Đã từ chối",
    BookingStatus.CANCELLED.value: "Đã hủy",
    BookingStatus.EXPIRED.value: "Đã hết hạn",
}

CONTRIBUTION_STATUS_LABELS = {
    ContributionStatus.PENDING.value: "Chờ thanh toán cọc",
    ContributionStatus.PAID.value: "Đã thanh toán cọc",
    ContributionStatus.EXPIRED.value: "Đã hết hạn",
    ContributionStatus.WAIVED.value: "Không cần thu thêm",
    ContributionStatus.REFUND_PENDING.value: "Đang hoàn tiền",
    ContributionStatus.PARTIALLY_REFUNDED.value: "Hoàn một phần",
    ContributionStatus.REFUNDED.value: "Đã hoàn",
    ContributionStatus.FORFEITED.value: "Không hoàn tiền",
}

PAYMENT_STATUS_LABELS = {
    PaymentStatus.PENDING.value: "Đang chờ xác nhận",
    PaymentStatus.SUCCESS.value: "Thanh toán thành công",
    PaymentStatus.FAILED.value: "Thanh toán thất bại",
    PaymentStatus.CANCELLED.value: "Đã hủy",
    PaymentStatus.EXPIRED.value: "Đã hết hạn",
}

REFUND_STATUS_LABELS = {
    RefundStatus.PENDING.value: "Chờ xử lý",
    RefundStatus.PROCESSING.value: "Đang xử lý",
    RefundStatus.SUCCESS.value: "Đã hoàn tiền",
    RefundStatus.FAILED.value: "Hoàn tiền thất bại",
}

MATCH_STATUS_LABELS = {
    MatchStatus.OPEN.value: "Đang mở",
    MatchStatus.FULL.value: "Đã đủ người",
    MatchStatus.CONFIRMED.value: "Đã có đối thủ",
    MatchStatus.CANCELLED.value: "Đã hủy",
    MatchStatus.COMPLETED.value: "Đã hoàn thành",
}

MATCH_TYPE_LABELS = {
    MatchType.FIND_OPPONENT.value: "Tìm đối thủ",
    MatchType.FIND_PLAYERS.value: "Tìm thêm người",
}

CONTRIBUTION_TYPE_LABELS = {
    ContributionType.CREATOR.value: "Người đặt sân",
    ContributionType.OPPONENT.value: "Đội đối thủ",
    ContributionType.PLAYER.value: "Người chơi ghép",
    ContributionType.TOP_UP.value: "Đóng bổ sung",
}

PAYMENT_PROVIDER_LABELS = {
    PaymentProvider.MOCK.value: "Thanh toán thử nghiệm",
    PaymentProvider.MOMO.value: "Ví MoMo",
}

PARTICIPANT_TYPE_LABELS = {
    MatchParticipantType.PLAYER.value: "Người chơi ghép",
    MatchParticipantType.OPPONENT_REPRESENTATIVE.value: "Đại diện đội đối thủ",
}

PARTICIPANT_STATUS_LABELS = {
    MatchParticipantStatus.PENDING.value: "Đang chờ",
    MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value: "Chờ đặt cọc",
    MatchParticipantStatus.JOINED.value: "Đã tham gia",
    MatchParticipantStatus.REJECTED.value: "Đã từ chối",
    MatchParticipantStatus.EXPIRED.value: "Đã hết hạn",
    MatchParticipantStatus.WITHDRAWN.value: "Đã rút",
}

BOOKING_MODE_LABELS = {
    BookingMode.DIRECT_BOOKING.value: "Đặt sân cho nhóm",
    BookingMode.FIND_OPPONENT.value: "Tìm đối thủ",
    BookingMode.FIND_PLAYERS.value: "Tìm thêm người",
}

BOOKING_PAYMENT_POLICY_LABELS = {
    BookingPaymentPolicy.DEPOSIT_30.value: "Cọc online theo chính sách",
    BookingPaymentPolicy.LEGACY_FULL_ONLINE.value: "Online toàn phần (lịch sử)",
}

MONITORING_SECTIONS = (
    ("bookings", "Lịch đặt sân & dòng tiền"),
    ("matches", "Kèo chơi"),
    ("catalog", "Danh mục thể thao"),
)

MONITORING_SECTION_DESCRIPTIONS = {
    "bookings": "Mỗi lịch đặt gồm tiến độ tiền cọc, các khoản cần đóng, giao dịch và hoàn tiền liên quan.",
    "matches": "Kiểm tra bài tìm đối thủ, tìm người chơi và số người tham gia.",
    "catalog": "Xem các bộ môn và loại sân đang được hệ thống sử dụng.",
}

MONITORING_STATUS_OPTIONS = {
    "bookings": BOOKING_STATUS_LABELS,
    "matches": MATCH_STATUS_LABELS,
}

BOOKING_FOCUS_OPTIONS = (
    ("", "Tất cả"),
    ("incomplete_deposit", "Chưa đủ cọc"),
    ("payment_issue", "Lỗi thanh toán"),
    ("refund_pending", "Đang hoàn tiền"),
    ("completed", "Đã hoàn thành"),
)

LEGACY_MONITORING_FOCUS = {
    "contributions": "incomplete_deposit",
    "payments": "payment_issue",
    "refunds": "refund_pending",
}

OWNER_APPLICATION_FILTERS = {
    OwnerApplicationStatus.PENDING.value: {
        "label": "Chờ duyệt",
        "result_label": "hồ sơ chờ duyệt",
        "list_heading": "Hồ sơ chờ duyệt",
        "sort_note": "Hồ sơ gửi sớm được xếp trước",
        "empty_title": "Không có yêu cầu đang chờ",
        "empty_message": "Các yêu cầu mới sẽ xuất hiện tại đây.",
        "icon": "inbox",
    },
    OwnerApplicationStatus.APPROVED.value: {
        "label": "Đã chấp thuận",
        "result_label": "hồ sơ đã chấp thuận",
        "list_heading": "Hồ sơ đã chấp thuận",
        "sort_note": "Hồ sơ xử lý gần nhất được xếp trước",
        "empty_title": "Chưa có hồ sơ được chấp thuận",
        "empty_message": "Hồ sơ được chấp thuận sẽ xuất hiện tại đây.",
        "icon": "check2-circle",
    },
    OwnerApplicationStatus.REJECTED.value: {
        "label": "Đã từ chối",
        "result_label": "hồ sơ đã từ chối",
        "list_heading": "Hồ sơ đã từ chối",
        "sort_note": "Hồ sơ xử lý gần nhất được xếp trước",
        "empty_title": "Chưa có hồ sơ bị từ chối",
        "empty_message": "Hồ sơ bị từ chối sẽ xuất hiện tại đây.",
        "icon": "x-circle",
    },
}


@admin_bp.get("")
@roles_required(UserRole.ADMIN)
def dashboard():
    return render_template(
        "admin/dashboard.html",
        summary=get_admin_dashboard_summary(),
    )


@admin_bp.get("/accounts")
@admin_bp.get("/users")
@roles_required(UserRole.ADMIN)
def accounts():
    return _render_accounts()


@admin_bp.get("/users/<int:account_id>")
@roles_required(UserRole.ADMIN)
def account_detail(account_id: int):
    return _render_accounts(selected_account_id=account_id)


def _render_accounts(*, selected_account_id: int | None = None):
    query = (request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip()
    status = (request.args.get("status") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    try:
        account_page = list_admin_accounts(
            query=query,
            role=role,
            status=status,
            page=page,
        )
    except AdminError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("admin.accounts"))

    if selected_account_id is None and account_page.items:
        selected_account_id = account_page.items[0].id
    selected_account = None
    if selected_account_id is not None:
        try:
            selected_account = get_admin_account_detail(selected_account_id)
        except AdminError as exc:
            flash(str(exc), "warning")
            return redirect(
                url_for(
                    "admin.accounts",
                    q=query,
                    role=role,
                    status=status,
                    page=page,
                )
            )

    return render_template(
        "admin/accounts.html",
        account_summary=get_admin_account_summary(),
        account_page=account_page,
        selected_account=selected_account,
        query=query,
        selected_role=role,
        selected_status=status,
        role_labels=ROLE_LABELS,
        status_labels=ACCOUNT_STATUS_LABELS,
        action_form=AdminAccountStatusForm(),
    )


@admin_bp.post("/accounts/<int:account_id>/status")
@admin_bp.post("/users/<int:account_id>/status")
@roles_required(UserRole.ADMIN)
def update_account_status(account_id: int):
    form = AdminAccountStatusForm()
    if not form.validate_on_submit():
        first_error = next(
            (
                error
                for field_errors in form.errors.values()
                for error in field_errors
            ),
            "Dữ liệu tài khoản không hợp lệ.",
        )
        flash(first_error, "danger")
        return _redirect_to_accounts(account_id)

    try:
        account = set_admin_account_status(
            account_id=account_id,
            actor=current_user,
            new_status=form.status.data,
        )
    except AdminError as exc:
        flash(str(exc), "warning")
    else:
        message = (
            f"Đã mở khóa tài khoản {account.email}."
            if account.status == UserStatus.ACTIVE.value
            else f"Đã khóa tài khoản {account.email}."
        )
        flash(message, "success")
    return _redirect_to_accounts(account_id)


def _redirect_to_accounts(account_id: int):
    route_values = {
        "q": (request.form.get("q") or "").strip(),
        "role": (request.form.get("role") or "").strip(),
        "status": (request.form.get("filter_status") or "").strip(),
        "page": max(request.form.get("page", 1, type=int) or 1, 1),
    }
    selected_id = request.form.get("selected_id", type=int)
    if selected_id == account_id:
        return redirect(
            url_for("admin.account_detail", account_id=account_id, **route_values)
        )
    return redirect(url_for("admin.accounts", **route_values))


@admin_bp.get("/owner-applications")
@roles_required(UserRole.ADMIN)
def owner_applications():
    selected_status = (
        request.args.get("status") or OwnerApplicationStatus.PENDING.value
    ).strip().upper()
    if selected_status not in OWNER_APPLICATION_FILTERS:
        flash("Bộ lọc trạng thái hồ sơ không hợp lệ.", "warning")
        return redirect(url_for("admin.owner_applications"))

    applications = list_owner_applications(selected_status)
    return render_template(
        "admin/owner_applications.html",
        applications=applications,
        selected_status=selected_status,
        selected_filter=OWNER_APPLICATION_FILTERS[selected_status],
        status_filters=OWNER_APPLICATION_FILTERS,
        review_forms={
            application.id: ReviewOwnerApplicationForm(
                prefix=f"application-{application.id}"
            )
            for application in applications
            if application.status == OwnerApplicationStatus.PENDING.value
        },
    )


@admin_bp.post("/owner-applications/<int:application_id>/review")
@roles_required(UserRole.ADMIN)
def review_owner_application_route(application_id: int):
    form = ReviewOwnerApplicationForm(prefix=f"application-{application_id}")
    if form.validate_on_submit():
        try:
            review_owner_application(
                application_id=application_id,
                reviewer=current_user,
                decision=form.decision.data,
                rejection_reason=form.rejection_reason.data,
            )
        except OwnerApplicationError as exc:
            flash(str(exc), "warning")
        else:
            message = (
                "Đã chấp nhận yêu cầu và chuyển tài khoản thành chủ sân."
                if form.decision.data == OwnerApplicationStatus.APPROVED.value
                else "Đã từ chối yêu cầu."
            )
            flash(message, "success")
    else:
        first_error = next(
            (
                error
                for field_errors in form.errors.values()
                for error in field_errors
            ),
            "Dữ liệu xét duyệt không hợp lệ.",
        )
        flash(first_error, "danger")
    return redirect(url_for("admin.owner_applications"))


@admin_bp.get("/bookings")
@roles_required(UserRole.ADMIN)
def booking_operations():
    query = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    sport_code = (request.args.get("sport") or "").strip()
    booking_date_raw = (request.args.get("date") or "").strip()
    province_code = (request.args.get("province_code") or "").strip()
    ward_code = (request.args.get("ward_code") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)

    try:
        venue_id = _parse_booking_filter_id("venue", "Cơ sở")
        field_id = _parse_booking_filter_id("field", "Sân")
        booking_date = (
            date.fromisoformat(booking_date_raw) if booking_date_raw else None
        )
    except (AdminError, ValueError):
        flash("Bộ lọc lịch đặt không hợp lệ.", "warning")
        return redirect(url_for("admin.booking_operations"))

    try:
        filter_options = get_admin_booking_filter_options(
            province_code=province_code,
            ward_code=ward_code,
            venue_id=venue_id,
            field_id=field_id,
        )
        booking_page = list_admin_booking_operations(
            query=query,
            status=status,
            sport_code=sport_code,
            booking_date=booking_date,
            province_code=province_code,
            ward_code=ward_code,
            venue_id=venue_id,
            field_id=field_id,
            page=page,
        )
    except AdminError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("admin.booking_operations"))

    pagination_params = {
        "q": query or None,
        "status": status or None,
        "sport": sport_code or None,
        "date": booking_date_raw or None,
        "province_code": province_code or None,
        "ward_code": ward_code or None,
        "venue": venue_id,
        "field": field_id,
    }
    return render_template(
        "admin/bookings/index.html",
        booking_page=booking_page,
        catalog=list_admin_catalog(),
        filter_options=filter_options,
        query=query,
        selected_status=status,
        selected_sport=sport_code,
        selected_date=booking_date_raw,
        selected_province_code=province_code,
        selected_ward_code=ward_code,
        selected_venue_id=venue_id,
        selected_field_id=field_id,
        pagination_params=pagination_params,
        booking_status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        booking_payment_policy_labels=BOOKING_PAYMENT_POLICY_LABELS,
    )


@admin_bp.get("/monitoring")
@roles_required(UserRole.ADMIN)
def monitoring():
    section = (request.args.get("section") or "bookings").strip()
    if section in LEGACY_MONITORING_FOCUS:
        redirect_args = request.args.to_dict(flat=True)
        redirect_args.pop("status", None)
        redirect_args.pop("page", None)
        redirect_args["section"] = "bookings"
        redirect_args["focus"] = LEGACY_MONITORING_FOCUS[section]
        return redirect(url_for("admin.monitoring", **redirect_args))

    section_keys = {key for key, _ in MONITORING_SECTIONS}
    if section not in section_keys:
        flash("Nhóm dữ liệu giám sát không hợp lệ.", "warning")
        return redirect(url_for("admin.monitoring"))

    query = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    sport_code = (request.args.get("sport") or "").strip()
    booking_date_raw = (request.args.get("date") or "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    focus = (request.args.get("focus") or "").strip()
    allowed_focus = {value for value, _ in BOOKING_FOCUS_OPTIONS}
    if focus not in allowed_focus or (section != "bookings" and focus):
        flash("Bộ lọc xử lý lịch đặt không hợp lệ.", "warning")
        return redirect(url_for("admin.monitoring", section=section))
    location_query = (request.args.get("venue_q") or "").strip()
    location_province = (
        request.args.get("venue_province")
        or request.args.get("venue_city")
        or ""
    ).strip()
    location_ward = (
        request.args.get("venue_ward")
        or request.args.get("venue_district")
        or ""
    ).strip()
    venue_page_number = max(
        request.args.get("venue_page", 1, type=int) or 1,
        1,
    )
    catalog = list_admin_catalog()
    location_provinces = list_admin_monitoring_provinces()
    if location_province and location_province not in location_provinces:
        flash("Tỉnh hoặc thành phố được chọn không hợp lệ.", "warning")
        return redirect(url_for("admin.monitoring", section=section))
    location_wards = list_admin_monitoring_wards(
        province=location_province or None,
    )
    if location_ward and location_ward not in location_wards:
        flash("Phường, xã hoặc đặc khu được chọn không hợp lệ.", "warning")
        return redirect(
            url_for(
                "admin.monitoring",
                section=section,
                venue_q=location_query,
                venue_province=location_province,
            )
        )
    location_page = list_admin_monitoring_locations(
        query=location_query,
        province=location_province,
        ward=location_ward,
        page=venue_page_number,
    )

    venue_id, field_id, selected_location = _parse_monitoring_location(
        section=section,
    )
    if venue_id is False:
        return redirect(url_for("admin.monitoring", section=section))

    allowed_sports = {sport.code for sport in catalog}
    if sport_code and sport_code not in allowed_sports:
        flash("Bộ môn lọc không hợp lệ.", "warning")
        return redirect(url_for("admin.monitoring", section=section))

    booking_date = None
    if booking_date_raw:
        try:
            booking_date = date.fromisoformat(booking_date_raw)
        except ValueError:
            flash("Ngày lọc phải có định dạng hợp lệ.", "warning")
            return redirect(url_for("admin.monitoring", section=section))

    try:
        data_page = _load_monitoring_page(
            section=section,
            query=query,
            status=status,
            sport_code=sport_code,
            booking_date=booking_date,
            venue_id=venue_id,
            field_id=field_id,
            focus=focus,
            page=page,
        )
    except AdminError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("admin.monitoring", section=section))

    return render_template(
        "admin/monitoring.html",
        section=section,
        sections=MONITORING_SECTIONS,
        section_description=MONITORING_SECTION_DESCRIPTIONS[section],
        data_page=data_page,
        monitoring_groups=_group_monitoring_items(
            section,
            data_page.items if data_page else (),
        ),
        catalog=catalog,
        location_page=location_page,
        locations=location_page.items,
        location_provinces=location_provinces,
        location_wards=location_wards,
        location_query=location_query,
        selected_location_province=location_province,
        selected_location_ward=location_ward,
        selected_location=selected_location,
        selected_venue_id=venue_id,
        selected_field_id=field_id,
        query=query,
        selected_status=status,
        selected_sport=sport_code,
        selected_date=booking_date_raw,
        selected_focus=focus,
        booking_focus_options=BOOKING_FOCUS_OPTIONS,
        status_options=MONITORING_STATUS_OPTIONS.get(section, {}),
        booking_status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        contribution_status_labels=CONTRIBUTION_STATUS_LABELS,
        contribution_type_labels=CONTRIBUTION_TYPE_LABELS,
        payment_status_labels=PAYMENT_STATUS_LABELS,
        payment_provider_labels=PAYMENT_PROVIDER_LABELS,
        refund_status_labels=REFUND_STATUS_LABELS,
        match_status_labels=MATCH_STATUS_LABELS,
        match_type_labels=MATCH_TYPE_LABELS,
    )


@admin_bp.get("/monitoring/bookings/<string:booking_code>")
@roles_required(UserRole.ADMIN)
def booking_monitoring_detail(booking_code: str):
    try:
        booking = get_admin_booking(booking_code)
    except AdminError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("admin.monitoring", section="bookings"))

    return render_template(
        "admin/booking_detail.html",
        booking=booking,
        booking_status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        contribution_status_labels=CONTRIBUTION_STATUS_LABELS,
        contribution_type_labels=CONTRIBUTION_TYPE_LABELS,
        payment_status_labels=PAYMENT_STATUS_LABELS,
        payment_provider_labels=PAYMENT_PROVIDER_LABELS,
        refund_status_labels=REFUND_STATUS_LABELS,
        match_status_labels=MATCH_STATUS_LABELS,
        match_type_labels=MATCH_TYPE_LABELS,
        participant_type_labels=PARTICIPANT_TYPE_LABELS,
        participant_status_labels=PARTICIPANT_STATUS_LABELS,
    )


def _load_monitoring_page(
    *,
    section: str,
    query: str,
    status: str,
    sport_code: str,
    booking_date: date | None,
    venue_id: int | None,
    field_id: int | None,
    focus: str,
    page: int,
):
    common = {
        "query": query,
        "status": status,
        "venue_id": venue_id,
        "field_id": field_id,
        "page": page,
    }
    if section == "bookings":
        return list_admin_bookings(
            **common,
            sport_code=sport_code,
            booking_date=booking_date,
            focus=focus,
        )
    if section == "matches":
        return list_admin_matches(
            **common,
            sport_code=sport_code,
            booking_date=booking_date,
        )
    return None


def _parse_booking_filter_id(parameter: str, label: str) -> int | None:
    raw_value = (request.args.get(parameter) or "").strip()
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise AdminError(f"{label} được chọn không hợp lệ.") from exc
    if value <= 0:
        raise AdminError(f"{label} được chọn không hợp lệ.")
    return value


def _parse_monitoring_location(*, section: str):
    if section == "catalog":
        return None, None, None

    venue_raw = (request.args.get("venue") or "").strip()
    field_raw = (request.args.get("field") or "").strip()
    try:
        venue_id = int(venue_raw) if venue_raw else None
        field_id = int(field_raw) if field_raw else None
    except ValueError:
        flash("Cơ sở hoặc sân được chọn không hợp lệ.", "warning")
        return False, None, None

    if field_id is not None and venue_id is None:
        flash("Hãy chọn cơ sở trước khi chọn sân.", "warning")
        return False, None, None

    selected_location = (
        get_admin_monitoring_location(venue_id)
        if venue_id is not None
        else None
    )
    if venue_id is not None and selected_location is None:
        flash("Không tìm thấy cơ sở đã chọn.", "warning")
        return False, None, None
    if field_id is not None:
        fields = {
            field_summary.field.id: field_summary.field
            for field_summary in selected_location.fields
        }
        selected_field = fields.get(field_id)
        if selected_field is None:
            flash("Không tìm thấy sân đã chọn.", "warning")
            return False, None, None
    return venue_id, field_id, selected_location


def _group_monitoring_items(section: str, items):
    grouped = {}
    for item in items:
        if section == "bookings":
            field = item.field
        elif section == "matches":
            field = item.booking.field
        else:
            continue
        group = grouped.setdefault(
            field.id,
            SimpleNamespace(field=field, items=[]),
        )
        group.items.append(item)
    return tuple(grouped.values())


def _group_accounts(accounts):
    role_order = (UserRole.USER.value, UserRole.OWNER.value, UserRole.ADMIN.value)
    status_order = (
        UserStatus.ACTIVE.value,
        UserStatus.LOCKED.value,
        UserStatus.INACTIVE.value,
    )
    grouped = []
    for role in role_order:
        role_accounts = [account for account in accounts if account.role == role]
        if not role_accounts:
            continue
        status_groups = []
        for status in status_order:
            status_accounts = [
                account for account in role_accounts if account.status == status
            ]
            if status_accounts:
                status_groups.append(
                    SimpleNamespace(status=status, items=status_accounts)
                )
        grouped.append(SimpleNamespace(role=role, statuses=status_groups))
    return tuple(grouped)
