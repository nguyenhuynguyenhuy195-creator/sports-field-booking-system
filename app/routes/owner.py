from flask import Blueprint, render_template
from flask_login import current_user

from app.decorators import roles_required
from app.models import BookingMode, BookingStatus, UserRole
from app.services import get_owner_dashboard_summary


owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


BOOKING_STATUS_LABELS = {
    BookingStatus.PENDING.value: "Đang xử lý",
    BookingStatus.CONFIRMED.value: "Chờ thanh toán",
    BookingStatus.PARTIALLY_PAID.value: "Đã thanh toán một phần",
    BookingStatus.PAID.value: "Đã thanh toán",
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
