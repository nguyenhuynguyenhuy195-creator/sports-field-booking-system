"""User-facing Vietnamese names for the status codes the chatbot reports.

Presentation only. Nothing here changes a database value, an enum or a rule:
the resolved DTO in :mod:`.context` keeps the raw code in ``data`` for support
questions, and these labels are used solely when rendering ``prompt_lines`` so
the model is handed "Đang mở" rather than "OPEN" and stops reading a backend
code aloud to a player.

Every entry is copied from the label maps the web pages already show for the
same value (``app.routes.matches``, ``app.routes.bookings``), so the assistant
and the page a user is looking at cannot describe the same record differently.
Keys are written as plain strings rather than imported from ``app.models``:
this module is pure presentation data and must not pull the data layer into the
chatbot package (see ``test_only_the_context_resolver_may_touch_the_data_layer``).
Two tests keep that honest -- one asserts these maps cover every enum value,
another asserts the wording matches the route maps -- and ``label_for`` falls
back to the raw code rather than inventing a meaning for an unknown value.
"""

from __future__ import annotations


BOOKING_STATUS_LABELS = {
    "PENDING": "Đang xử lý",
    "CONFIRMED": "Đang giữ chỗ, chờ thanh toán",
    "PARTIALLY_PAID": "Đã cọc giữ sân, chờ đối thủ",
    "PAID": "Đã thanh toán cọc",
    "REFUND_PENDING": "Đang hoàn tiền",
    "COMPLETED": "Đã hoàn thành",
    "REJECTED": "Đã từ chối",
    "CANCELLED": "Đã hủy",
    "EXPIRED": "Đã hết hạn",
}

BOOKING_MODE_LABELS = {
    "DIRECT_BOOKING": "Đặt sân cho nhóm",
    "FIND_OPPONENT": "Tìm đối thủ",
    "FIND_PLAYERS": "Tìm thêm người",
}

# The derived lifecycle a user is shown, not the raw Match.status column: PAST,
# CLOSED_LISTING and INACTIVE only ever exist as view states.
MATCH_VIEW_STATUS_LABELS = {
    "OPEN": "Đang mở",
    "FULL": "Đã đủ người",
    "CONFIRMED": "Đã có đối thủ",
    "CANCELLED": "Đã hủy",
    "COMPLETED": "Đã hoàn thành",
    "PAST": "Đã diễn ra",
    "CLOSED_LISTING": "Đã đóng bài tìm đối thủ",
    "INACTIVE": "Không còn hiệu lực",
}

MATCH_TYPE_LABELS = {
    "FIND_OPPONENT": "Tìm đội đối thủ",
    "FIND_PLAYERS": "Tìm thêm người chơi",
}

PARTICIPANT_STATUS_LABELS = {
    "PENDING": "Chờ người tạo xác nhận",
    "ACCEPTED_AWAITING_PAYMENT": "Đang giữ suất, chờ thanh toán",
    "JOINED": "Đã tham gia",
    "REJECTED": "Đã từ chối",
    # Neutral on purpose: EXPIRED does not imply a missed payment.
    # effective_participant_status() also returns it for a PENDING request
    # whose booking simply reached kick-off, and a FIND_PLAYERS joiner never
    # owes anything online (no contribution, no payment_due_at). Telling that
    # user their payment deadline passed would name an obligation they never
    # had. app.routes.matches and matches/detail.html use the same wording.
    "EXPIRED": "Yêu cầu tham gia đã hết hạn",
    "WITHDRAWN": "Đã rút yêu cầu",
}

CONTRIBUTION_TYPE_LABELS = {
    "CREATOR": "Nhóm người đặt",
    "OPPONENT": "Đội đối thủ",
    "PLAYER": "Người chơi ghép",
    "TOP_UP": "Người đặt trả phần còn thiếu",
}

CONTRIBUTION_STATUS_LABELS = {
    "PENDING": "Chờ thanh toán",
    "PAID": "Đã thanh toán",
    "EXPIRED": "Đã hết hạn",
    "WAIVED": "Đã được trả thay",
    "REFUND_PENDING": "Đang hoàn tiền",
    "PARTIALLY_REFUNDED": "Đã hoàn một phần",
    "REFUNDED": "Đã hoàn tiền",
    "FORFEITED": "Không hoàn tiền",
}

PAYMENT_STATUS_LABELS = {
    "PENDING": "Đang xử lý",
    "SUCCESS": "Thành công",
    "FAILED": "Thất bại",
    "CANCELLED": "Đã hủy",
    "EXPIRED": "Đã hết hạn",
}

REFUND_STATUS_LABELS = {
    "PENDING": "Đang chờ xử lý",
    "PROCESSING": "Đang xử lý",
    "SUCCESS": "Đã hoàn tiền",
    "FAILED": "Hoàn tiền thất bại",
}

# The viewer's relationship to a match. Not a database enum -- context.py
# derives it -- but it reaches the prompt the same way, so it is named here too.
VIEWER_ROLE_LABELS = {
    "creator": "người tạo kèo",
    "participant": "người tham gia",
    "viewer": "người xem",
}


def label_for(mapping: dict[str, str], value: object) -> str:
    """The approved Vietnamese wording, or the raw value unchanged.

    Falling back to the raw code is deliberate. A status with no approved
    wording is a gap in this table, and showing the code is honest; guessing a
    translation would put an invented meaning in front of a user.
    """
    if not isinstance(value, str):
        return ""
    return mapping.get(value, value)


__all__ = [
    "BOOKING_MODE_LABELS",
    "BOOKING_STATUS_LABELS",
    "CONTRIBUTION_STATUS_LABELS",
    "CONTRIBUTION_TYPE_LABELS",
    "MATCH_TYPE_LABELS",
    "MATCH_VIEW_STATUS_LABELS",
    "PARTICIPANT_STATUS_LABELS",
    "PAYMENT_STATUS_LABELS",
    "REFUND_STATUS_LABELS",
    "VIEWER_ROLE_LABELS",
    "label_for",
]
