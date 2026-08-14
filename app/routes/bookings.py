from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.decorators import roles_required
from app.forms import BookingActionForm, BookingForm, BookingReasonForm
from app.models import (
    Booking,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    PaymentProvider,
    PaymentStatus,
    PlayFormat,
    RefundStatus,
    UserRole,
)
from app.services import (
    AVAILABILITY_STEP_MINUTES,
    MINIMUM_BOOKING_MINUTES,
    BookingError,
    BookingNotFoundError,
    BookingPermissionError,
    build_field_availability,
    build_contribution_plan,
    calculate_deposit_amount,
    cancel_owner_booking,
    cancel_user_booking,
    create_booking,
    current_vietnam_datetime,
    get_booking_field,
    get_effective_booking_status,
    get_owner_booking,
    get_user_booking,
    list_owner_bookings,
    list_user_bookings,
    quote_booking,
)


bookings_bp = Blueprint("bookings", __name__)

BOOKING_STATUS_LABELS = {
    BookingStatus.PENDING.value: "Đang xử lý",
    BookingStatus.CONFIRMED.value: "Đang giữ chỗ, chờ thanh toán",
    BookingStatus.PARTIALLY_PAID.value: "Đã thanh toán một phần",
    BookingStatus.PAID.value: "Đã thanh toán đủ",
    BookingStatus.REFUND_PENDING.value: "Đang hoàn tiền",
    BookingStatus.COMPLETED.value: "Đã hoàn thành",
    BookingStatus.REJECTED.value: "Đã từ chối",
    BookingStatus.CANCELLED.value: "Đã hủy",
    BookingStatus.EXPIRED.value: "Đã hết hạn",
}

BOOKING_MODE_LABELS = {
    BookingMode.DIRECT_BOOKING.value: "Đặt sân cho nhóm",
    BookingMode.FIND_OPPONENT.value: "Tìm đối thủ",
    BookingMode.FIND_PLAYERS.value: "Tìm thêm người",
}

PLAY_FORMAT_LABELS = {
    PlayFormat.SINGLES.value: "Đánh đơn",
    PlayFormat.DOUBLES.value: "Đánh đôi",
}

CONTRIBUTION_TYPE_LABELS = {
    ContributionType.CREATOR.value: "Nhóm người đặt",
    ContributionType.OPPONENT.value: "Đội đối thủ",
    ContributionType.PLAYER.value: "Người chơi ghép",
    ContributionType.TOP_UP.value: "Người đặt trả phần còn thiếu",
}

CONTRIBUTION_STATUS_LABELS = {
    ContributionStatus.PENDING.value: "Chờ thanh toán",
    ContributionStatus.PAID.value: "Đã thanh toán",
    ContributionStatus.EXPIRED.value: "Đã hết hạn",
    ContributionStatus.WAIVED.value: "Đã được trả thay",
    ContributionStatus.REFUND_PENDING.value: "Đang hoàn tiền",
    ContributionStatus.PARTIALLY_REFUNDED.value: "Đã hoàn một phần",
    ContributionStatus.REFUNDED.value: "Đã hoàn tiền",
    ContributionStatus.FORFEITED.value: "Không hoàn tiền",
}

PAYMENT_STATUS_LABELS = {
    PaymentStatus.PENDING.value: "Đang xử lý",
    PaymentStatus.SUCCESS.value: "Thành công",
    PaymentStatus.FAILED.value: "Thất bại",
    PaymentStatus.CANCELLED.value: "Đã hủy",
    PaymentStatus.EXPIRED.value: "Đã hết hạn",
}

PAYMENT_PROVIDER_LABELS = {
    PaymentProvider.MOCK.value: "Mô phỏng nội bộ",
    PaymentProvider.MOMO.value: "MoMo",
}

REFUND_STATUS_LABELS = {
    RefundStatus.PENDING.value: "Đang chờ xử lý",
    RefundStatus.PROCESSING.value: "Đang xử lý",
    RefundStatus.SUCCESS.value: "Đã hoàn thành",
    RefundStatus.FAILED.value: "Thất bại",
}

BOOKING_LIST_GROUPS = (
    {
        "key": "upcoming",
        "title": "Sắp diễn ra",
        "description": "Các lịch đã hoàn tất bước xác nhận và chưa diễn ra.",
    },
    {
        "key": "processing",
        "title": "Đang xử lý",
        "description": "Các lịch vẫn còn bước cần xử lý trước khi diễn ra.",
    },
    {
        "key": "completed",
        "title": "Đã hoàn thành",
        "description": "Các lịch đã kết thúc để bạn tiện xem lại.",
    },
    {
        "key": "closed",
        "title": "Đã hủy hoặc hết hạn",
        "description": "Các lịch không còn hiệu lực và không chiếm chỗ.",
    },
)


@bookings_bp.route(
    "/venues/<int:venue_id>/fields/<int:field_id>/bookings/new",
    methods=["GET", "POST"],
)
@roles_required(UserRole.USER, UserRole.OWNER)
def create(venue_id: int, field_id: int):
    try:
        field = get_booking_field(venue_id=venue_id, field_id=field_id)
    except BookingNotFoundError:
        abort(404)
    except BookingError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("venues.detail", venue_id=venue_id))

    today = current_vietnam_datetime().date()
    form = BookingForm()
    if not form.is_submitted():
        form.booking_date.data = today + timedelta(days=1)
    if form.validate_on_submit():
        try:
            booking = create_booking(
                user=current_user,
                field_id=field.id,
                booking_date=form.booking_date.data,
                start_time=form.start_time_value,
                end_time=form.end_time_value,
                booking_mode=form.booking_mode.data,
                play_format=form.play_format.data,
                requested_players=form.requested_players.data,
                note=form.note.data,
            )
        except BookingPermissionError:
            abort(403)
        except BookingNotFoundError:
            abort(404)
        except BookingError as exc:
            flash(str(exc), "warning")
        else:
            flash(
                "Đã giữ chỗ trong 15 phút. Hãy hoàn tất khoản thanh toán đầu tiên.",
                "success",
            )
            return redirect(
                url_for("bookings.detail", booking_code=booking.booking_code)
            )

    return render_template(
        "bookings/form.html",
        form=form,
        field=field,
        today=today,
        maximum_booking_date=today + timedelta(days=30),
    )


@bookings_bp.post(
    "/venues/<int:venue_id>/fields/<int:field_id>/bookings/quote"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def quote(venue_id: int, field_id: int):
    try:
        field = get_booking_field(venue_id=venue_id, field_id=field_id)
    except BookingNotFoundError:
        abort(404)
    except BookingError as exc:
        return jsonify(ok=False, message=str(exc)), 422

    form = BookingForm()
    if not form.validate_on_submit():
        return jsonify(ok=False, message=_first_form_error(form)), 422

    try:
        price_quote = quote_booking(
            user=current_user,
            field_id=field.id,
            booking_date=form.booking_date.data,
            start_time=form.start_time_value,
            end_time=form.end_time_value,
            booking_mode=form.booking_mode.data,
            play_format=form.play_format.data,
            requested_players=form.requested_players.data,
        )
    except BookingPermissionError:
        abort(403)
    except BookingNotFoundError:
        abort(404)
    except BookingError as exc:
        return jsonify(ok=False, message=str(exc)), 422

    deposit_amount = calculate_deposit_amount(price_quote.total)
    contribution_plan = build_contribution_plan(
        booking_mode=form.booking_mode.data,
        deposit_amount=deposit_amount,
        requested_players=form.requested_players.data,
    )

    return jsonify(
        ok=True,
        total=str(price_quote.total),
        deposit_amount=str(deposit_amount),
        venue_balance=str(price_quote.total - deposit_amount),
        contribution_plan={
            "creator_amount": str(contribution_plan.creator_amount),
            "external_amount": str(contribution_plan.external_amount),
            "requested_players": contribution_plan.requested_players,
            "external_contributions": [
                {
                    "type": contribution.contribution_type,
                    "slot_number": contribution.slot_number,
                    "amount_due": str(contribution.amount_due),
                }
                for contribution in contribution_plan.external_contributions
            ],
        },
        segments=[
            {
                "start_time": segment.start_time.strftime("%H:%M"),
                "end_time": segment.end_time.strftime("%H:%M"),
                "duration_minutes": segment.duration_minutes,
                "hourly_price": str(segment.hourly_price),
                "subtotal": str(segment.subtotal),
            }
            for segment in price_quote.segments
        ],
    )


@bookings_bp.get(
    "/venues/<int:venue_id>/fields/<int:field_id>/bookings/availability"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def availability(venue_id: int, field_id: int):
    try:
        field = get_booking_field(venue_id=venue_id, field_id=field_id)
    except BookingNotFoundError:
        abort(404)
    except BookingError as exc:
        return jsonify(ok=False, message=str(exc)), 422

    raw_date = request.args.get("date", "")
    try:
        booking_date = date.fromisoformat(raw_date)
    except ValueError:
        return jsonify(ok=False, message="Ngày đặt sân không hợp lệ."), 422

    today = current_vietnam_datetime().date()
    if booking_date < today or booking_date > today + timedelta(days=30):
        return jsonify(
            ok=False,
            message="Ngày đặt sân phải từ hôm nay đến tối đa 30 ngày tới.",
        ), 422

    result = build_field_availability(field=field, booking_date=booking_date)
    return jsonify(
        ok=True,
        date=result.booking_date.isoformat(),
        opening_time=result.opening_time.strftime("%H:%M"),
        closing_time=result.closing_time.strftime("%H:%M"),
        step_minutes=AVAILABILITY_STEP_MINUTES,
        minimum_duration_minutes=MINIMUM_BOOKING_MINUTES,
        slots=[
            {
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "status": slot.status.value,
            }
            for slot in result.slots
        ],
    )


@bookings_bp.get("/bookings")
@roles_required(UserRole.USER, UserRole.OWNER)
def index():
    bookings = list_user_bookings(current_user.id)
    return render_template(
        "bookings/index.html",
        bookings=bookings,
        booking_groups=_group_bookings_for_display(bookings),
        status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        play_format_labels=PLAY_FORMAT_LABELS,
    )


@bookings_bp.get("/bookings/<string:booking_code>")
@roles_required(UserRole.USER, UserRole.OWNER)
def detail(booking_code: str):
    try:
        booking = get_user_booking(
            booking_code=booking_code,
            user_id=current_user.id,
        )
    except BookingNotFoundError:
        abort(404)
    except BookingPermissionError:
        abort(403)
    return render_template(
        "bookings/detail.html",
        booking=booking,
        effective_status=get_effective_booking_status(booking),
        status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        play_format_labels=PLAY_FORMAT_LABELS,
        contribution_type_labels=CONTRIBUTION_TYPE_LABELS,
        contribution_status_labels=CONTRIBUTION_STATUS_LABELS,
        payment_status_labels=PAYMENT_STATUS_LABELS,
        payment_provider_labels=PAYMENT_PROVIDER_LABELS,
        refund_status_labels=REFUND_STATUS_LABELS,
        successful_refund_total=_successful_refund_total(booking),
        top_up_window_open=_top_up_window_open(booking),
        payment_form=BookingActionForm(prefix="payment"),
        top_up_form=BookingActionForm(prefix="top-up"),
        cancel_form=BookingActionForm(),
        owner_view=False,
        momo_enabled=current_app.config.get("MOMO_ENABLED", False),
    )


@bookings_bp.post("/bookings/<string:booking_code>/cancel")
@roles_required(UserRole.USER, UserRole.OWNER)
def cancel(booking_code: str):
    form = BookingActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu hủy booking không hợp lệ.", "danger")
        return redirect(url_for("bookings.detail", booking_code=booking_code))
    try:
        cancel_user_booking(
            booking_code=booking_code,
            user=current_user,
        )
    except BookingNotFoundError:
        abort(404)
    except BookingPermissionError:
        abort(403)
    except BookingError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã hủy booking và hoàn tiền theo chính sách áp dụng.", "success")
    return redirect(url_for("bookings.detail", booking_code=booking_code))


@bookings_bp.get("/owner/bookings")
@roles_required(UserRole.OWNER)
def owner_index():
    bookings = list_owner_bookings(current_user.id)
    return render_template(
        "owner/bookings/index.html",
        bookings=bookings,
        booking_groups=_group_bookings_for_display(bookings),
        status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
    )


@bookings_bp.get("/owner/bookings/<string:booking_code>")
@roles_required(UserRole.OWNER)
def owner_detail(booking_code: str):
    booking = _load_owner_booking(booking_code)
    return render_template(
        "bookings/detail.html",
        booking=booking,
        effective_status=get_effective_booking_status(booking),
        status_labels=BOOKING_STATUS_LABELS,
        booking_mode_labels=BOOKING_MODE_LABELS,
        play_format_labels=PLAY_FORMAT_LABELS,
        contribution_type_labels=CONTRIBUTION_TYPE_LABELS,
        contribution_status_labels=CONTRIBUTION_STATUS_LABELS,
        payment_status_labels=PAYMENT_STATUS_LABELS,
        payment_provider_labels=PAYMENT_PROVIDER_LABELS,
        refund_status_labels=REFUND_STATUS_LABELS,
        successful_refund_total=_successful_refund_total(booking),
        top_up_window_open=_top_up_window_open(booking),
        owner_cancel_form=BookingReasonForm(prefix="owner-cancel"),
        owner_view=True,
        momo_enabled=current_app.config.get("MOMO_ENABLED", False),
    )


@bookings_bp.post("/owner/bookings/<string:booking_code>/cancel")
@roles_required(UserRole.OWNER)
def owner_cancel(booking_code: str):
    _load_owner_booking(booking_code)
    form = BookingReasonForm(prefix="owner-cancel")
    if form.validate_on_submit():
        try:
            cancel_owner_booking(
                booking_code=booking_code,
                owner=current_user,
                reason=form.reason.data,
            )
        except BookingPermissionError:
            abort(403)
        except BookingNotFoundError:
            abort(404)
        except BookingError as exc:
            flash(str(exc), "warning")
        else:
            flash(
                "Đã hủy booking; các khoản đã thu (nếu có) đã được hoàn 100%.",
                "success",
            )
    else:
        flash("Vui lòng nhập lý do hủy hợp lệ.", "danger")
    return redirect(url_for("bookings.owner_detail", booking_code=booking_code))


def _load_owner_booking(booking_code: str):
    try:
        return get_owner_booking(
            booking_code=booking_code,
            owner_id=current_user.id,
        )
    except BookingNotFoundError:
        abort(404)
    except BookingPermissionError:
        abort(403)


def _effective_statuses(bookings, *, now: datetime | None = None):
    current_local = now or current_vietnam_datetime()
    return {
        booking.id: get_effective_booking_status(booking, now=current_local)
        for booking in bookings
    }


def _group_bookings_for_display(bookings: list[Booking]) -> list[dict]:
    now = current_vietnam_datetime()
    effective_statuses = _effective_statuses(bookings, now=now)
    grouped_entries = {group["key"]: [] for group in BOOKING_LIST_GROUPS}

    for booking in bookings:
        status = effective_statuses[booking.id]
        group_key = _booking_group_key(booking=booking, status=status, now=now)
        grouped_entries[group_key].append(
            {
                "booking": booking,
                "status": status,
            }
        )

    for group_key in ("upcoming", "processing"):
        grouped_entries[group_key].sort(key=_booking_entry_start)
    for group_key in ("completed", "closed"):
        grouped_entries[group_key].sort(key=_booking_entry_start, reverse=True)

    return [
        {
            **group,
            "entries": grouped_entries[group["key"]],
        }
        for group in BOOKING_LIST_GROUPS
    ]


def _booking_group_key(*, booking: Booking, status: str, now: datetime) -> str:
    if status in {
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    }:
        return "closed"
    if status == BookingStatus.COMPLETED.value:
        return "completed"
    if status == BookingStatus.PAID.value:
        booking_end = datetime.combine(booking.booking_date, booking.end_time)
        return "completed" if booking_end <= now else "upcoming"
    return "processing"


def _booking_entry_start(entry: dict) -> datetime:
    booking = entry["booking"]
    return datetime.combine(booking.booking_date, booking.start_time)


def _successful_refund_total(booking) -> Decimal:
    return sum(
        (
            Decimal(refund.amount)
            for refund in booking.refunds
            if refund.status == RefundStatus.SUCCESS.value
        ),
        Decimal("0.00"),
    )


def _top_up_window_open(booking: Booking) -> bool:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return bool(
        booking.booking_mode == BookingMode.FIND_OPPONENT.value
        and booking.status == BookingStatus.PARTIALLY_PAID.value
        and booking.matchmaking_deadline is not None
        and booking.funding_deadline is not None
        and booking.matchmaking_deadline <= now_utc < booking.funding_deadline
    )


def _first_form_error(form) -> str:
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return "Thông tin đặt sân chưa hợp lệ."
    AVAILABILITY_STEP_MINUTES,
    MINIMUM_BOOKING_MINUTES,
    build_field_availability,
