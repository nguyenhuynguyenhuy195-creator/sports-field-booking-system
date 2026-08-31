from datetime import date, timedelta

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.models import BookingMode, BookingStatus, UserRole
from app.services import (
    OwnerScheduleNotFoundError,
    OwnerSchedulePermissionError,
    current_vietnam_datetime,
    get_owner_dashboard_summary,
    get_owner_schedule_summary,
)


owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


BOOKING_STATUS_LABELS = {
    BookingStatus.PENDING.value: "Đang xử lý",
    BookingStatus.CONFIRMED.value: "Chờ thanh toán",
    BookingStatus.PARTIALLY_PAID.value: "Đã thanh toán một phần",
    BookingStatus.PAID.value: "Đã thanh toán cọc",
    BookingStatus.REFUND_PENDING.value: "Đang hoàn tiền",
    BookingStatus.COMPLETED.value: "Đã hoàn thành",
}

BOOKING_MODE_LABELS = {
    BookingMode.DIRECT_BOOKING.value: "Đặt trực tiếp",
    BookingMode.FIND_OPPONENT.value: "Tìm đối thủ",
    BookingMode.FIND_PLAYERS.value: "Tìm thêm người",
}


@owner_bp.get("")
@roles_required(UserRole.OWNER)
def dashboard():
    return render_template(
        "owner/dashboard.html",
        summary=get_owner_dashboard_summary(current_user.id),
        booking_status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
    )


@owner_bp.get("/schedule")
@roles_required(UserRole.OWNER)
def schedule():
    current_local = current_vietnam_datetime()
    today = current_local.date()
    schedule_date = _parse_schedule_date(
        request.args.get("date"),
        default_date=today,
    )
    venue_id = _parse_positive_id(request.args.get("venue_id"), "venue_id")
    field_id = _parse_positive_id(request.args.get("field_id"), "field_id")
    view = request.args.get("view", "matrix")
    if view not in {"matrix", "list"}:
        abort(400, description="Chế độ xem lịch không hợp lệ.")

    try:
        summary = get_owner_schedule_summary(
            current_user.id,
            schedule_date=schedule_date,
            venue_id=venue_id,
            field_id=field_id,
            now=current_local,
        )
    except OwnerSchedulePermissionError:
        abort(403)
    except OwnerScheduleNotFoundError:
        abort(404)

    if venue_id is None and summary.venues:
        return redirect(
            url_for(
                "owner.schedule",
                date=schedule_date.isoformat(),
                venue_id=summary.venues[0].id,
                view=view,
            )
        )

    return render_template(
        "owner/schedule.html",
        summary=summary,
        schedule_view=view,
        previous_date=schedule_date - timedelta(days=1),
        next_date=schedule_date + timedelta(days=1),
        today=today,
        booking_status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
    )


def _parse_schedule_date(raw_value: str | None, *, default_date: date) -> date:
    if raw_value is None:
        return default_date
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        abort(400, description="Ngày xem lịch không hợp lệ.")


def _parse_positive_id(raw_value: str | None, parameter_name: str) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        value = int(raw_value)
    except ValueError:
        abort(400, description=f"Tham số {parameter_name} không hợp lệ.")
    if value <= 0:
        abort(400, description=f"Tham số {parameter_name} không hợp lệ.")
    return value
