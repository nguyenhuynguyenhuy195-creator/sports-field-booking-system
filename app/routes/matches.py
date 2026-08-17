from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user

from app.decorators import roles_required
from app.forms import (
    BookingActionForm,
    MatchActionForm,
    MatchContactForm,
    MatchForm,
    MatchJoinForm,
)
from app.models import (
    BookingMode,
    BookingStatus,
    MatchParticipantStatus,
    MatchStatus,
    MatchType,
    UserRole,
)
from app.services import (
    BookingNotFoundError,
    BookingPermissionError,
    DuplicateMatchRequestError,
    MatchmakingError,
    MatchNotFoundError,
    MatchPermissionError,
    create_match,
    current_vietnam_datetime,
    decide_match_request,
    expire_stale_match_participants,
    get_match,
    get_user_booking,
    list_created_matches,
    list_open_matches,
    list_user_match_requests,
    opponent_join_is_automatic,
    participant_withdrawal_gets_refund,
    request_to_join_match,
    update_match_contact,
    validate_match_creation,
    withdraw_match_request,
)


matches_bp = Blueprint("matches", __name__)

MATCH_TYPE_LABELS = {
    MatchType.FIND_OPPONENT.value: "Tìm đội đối thủ",
    MatchType.FIND_PLAYERS.value: "Tìm thêm người chơi",
}
MATCH_STATUS_LABELS = {
    MatchStatus.OPEN.value: "Đang mở",
    MatchStatus.FULL.value: "Đã đủ người",
    MatchStatus.CONFIRMED.value: "Đã có đối thủ",
    MatchStatus.CANCELLED.value: "Đã hủy",
    MatchStatus.COMPLETED.value: "Đã hoàn thành",
}
PARTICIPANT_STATUS_LABELS = {
    MatchParticipantStatus.PENDING.value: "Chờ người tạo xác nhận",
    MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value: "Đang giữ suất, chờ thanh toán",
    MatchParticipantStatus.JOINED.value: "Đã tham gia",
    MatchParticipantStatus.REJECTED.value: "Đã từ chối",
    MatchParticipantStatus.EXPIRED.value: "Đã hết hạn thanh toán",
    MatchParticipantStatus.WITHDRAWN.value: "Đã rút yêu cầu",
}
SKILL_LEVEL_LABELS = {
    None: "Không yêu cầu",
    "": "Không yêu cầu",
    "BEGINNER": "Mới chơi",
    "INTERMEDIATE": "Trung bình",
    "ADVANCED": "Khá/Tốt",
}


@matches_bp.get("/matches")
def index():
    matches = list_open_matches()
    return render_template(
        "matches/index.html",
        matches=matches,
        match_type_labels=MATCH_TYPE_LABELS,
        skill_level_labels=SKILL_LEVEL_LABELS,
    )


@matches_bp.get("/matches/mine")
@roles_required(UserRole.USER, UserRole.OWNER)
def mine():
    expire_stale_match_participants()
    return render_template(
        "matches/mine.html",
        created_matches=list_created_matches(current_user.id),
        requests=list_user_match_requests(current_user.id),
        match_type_labels=MATCH_TYPE_LABELS,
        match_status_labels=MATCH_STATUS_LABELS,
        participant_status_labels=PARTICIPANT_STATUS_LABELS,
    )


@matches_bp.route(
    "/bookings/<string:booking_code>/matches/new",
    methods=["GET", "POST"],
)
@roles_required(UserRole.USER, UserRole.OWNER)
def create(booking_code: str):
    try:
        booking = get_user_booking(
            booking_code=booking_code,
            user_id=current_user.id,
        )
    except BookingPermissionError:
        abort(403)
    except BookingNotFoundError:
        abort(404)
    if booking.match is not None:
        flash("Lịch đặt sân này đã có kèo.", "info")
        return redirect(url_for("matches.detail", match_id=booking.match.id))
    try:
        validate_match_creation(booking=booking, creator=current_user)
    except MatchPermissionError:
        abort(403)
    except MatchmakingError as exc:
        flash(str(exc), "warning")
        return redirect(
            url_for("bookings.detail", booking_code=booking.booking_code)
        )

    locked_type = _locked_match_type(booking.booking_mode)
    locked_required_players = (
        booking.requested_players
        if booking.booking_mode == BookingMode.FIND_PLAYERS.value
        else None
    )
    form = MatchForm(contact_phone=current_user.phone)
    if not form.is_submitted():
        form.match_type.data = locked_type or MatchType.FIND_OPPONENT.value
        form.required_players.data = locked_required_players
        form.title.data = _default_match_title(booking, form.match_type.data)

    if form.validate_on_submit():
        requested_type = locked_type or form.match_type.data
        requested_players = (
            locked_required_players
            if locked_required_players is not None
            else form.required_players.data
        )
        try:
            match = create_match(
                booking_code=booking.booking_code,
                creator=current_user,
                title=form.title.data,
                description=form.description.data,
                skill_level=form.skill_level.data,
                match_type=requested_type,
                required_players=requested_players,
                contact_phone=form.contact_phone.data,
                share_contact=form.share_contact.data,
            )
        except MatchPermissionError:
            abort(403)
        except MatchNotFoundError:
            abort(404)
        except MatchmakingError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã đăng kèo. Người chơi khác có thể nhận kèo hoặc xin ghép.", "success")
            return redirect(url_for("matches.detail", match_id=match.id))

    return render_template(
        "matches/form.html",
        form=form,
        booking=booking,
        locked_type=locked_type,
        locked_required_players=locked_required_players,
        match_type_labels=MATCH_TYPE_LABELS,
    )


@matches_bp.get("/matches/<int:match_id>")
def detail(match_id: int):
    expire_stale_match_participants(match_id=match_id)
    try:
        match = get_match(match_id)
    except MatchNotFoundError:
        abort(404)
    current_request = None
    if current_user.is_authenticated:
        current_request = next(
            (
                participant
                for participant in reversed(match.participants)
                if participant.user_id == current_user.id
            ),
            None,
        )
    joined_count = sum(
        participant.status == MatchParticipantStatus.JOINED.value
        for participant in match.participants
    )
    current_contact_phone = current_user.phone if current_user.is_authenticated else None
    if current_user.is_authenticated and current_user.id == match.creator_id:
        current_contact_phone = match.creator_contact_phone
    elif current_request is not None:
        current_contact_phone = current_request.contact_phone
    return render_template(
        "matches/detail.html",
        match=match,
        current_request=current_request,
        joined_count=joined_count,
        match_type_labels=MATCH_TYPE_LABELS,
        match_status_labels=MATCH_STATUS_LABELS,
        participant_status_labels=PARTICIPANT_STATUS_LABELS,
        skill_level_labels=SKILL_LEVEL_LABELS,
        join_form=MatchJoinForm(contact_phone=current_contact_phone),
        action_form=MatchActionForm(),
        payment_form=BookingActionForm(prefix="payment"),
        contact_form=MatchContactForm(
            prefix="contact",
            contact_phone=current_contact_phone,
        ),
        withdrawal_gets_refund=(
            participant_withdrawal_gets_refund(match.booking)
            if current_request
            and current_request.status == MatchParticipantStatus.JOINED.value
            else False
        ),
        contact_visible=_contact_visible(match.booking),
        opponent_auto_join=opponent_join_is_automatic(match),
        momo_enabled=current_app.config.get("MOMO_ENABLED", False),
    )


@matches_bp.post("/matches/<int:match_id>/requests")
@roles_required(UserRole.USER, UserRole.OWNER)
def join(match_id: int):
    form = MatchJoinForm()
    if not form.validate_on_submit():
        flash("Thông tin tham gia không hợp lệ.", "danger")
        return redirect(url_for("matches.detail", match_id=match_id))
    try:
        participant = request_to_join_match(
            match_id=match_id,
            user=current_user,
            message=form.message.data,
            contact_phone=form.contact_phone.data,
            share_contact=form.share_contact.data,
        )
    except MatchNotFoundError:
        abort(404)
    except MatchPermissionError:
        abort(403)
    except (DuplicateMatchRequestError, MatchmakingError) as exc:
        flash(str(exc), "warning")
    else:
        if participant.status == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value:
            flash(
                "Đã giữ suất đối thủ trong 15 phút. Hãy hoàn tất tiền cọc để tham gia kèo.",
                "success",
            )
        elif participant.status == MatchParticipantStatus.JOINED.value:
            flash("Bạn đã tham gia kèo; không cần thanh toán lại khoản cọc này.", "success")
        else:
            flash("Đã gửi yêu cầu. Hãy chờ người tạo kèo xác nhận.", "success")
    return redirect(url_for("matches.detail", match_id=match_id))


@matches_bp.post("/matches/<int:match_id>/contact")
@roles_required(UserRole.USER, UserRole.OWNER)
def update_contact(match_id: int):
    form = MatchContactForm(prefix="contact")
    if not form.validate_on_submit():
        flash("Số liên hệ không hợp lệ hoặc chưa được đồng ý chia sẻ.", "danger")
        return redirect(url_for("matches.detail", match_id=match_id))
    try:
        update_match_contact(
            match_id=match_id,
            user=current_user,
            contact_phone=form.contact_phone.data,
            share_contact=form.share_contact.data,
        )
    except MatchNotFoundError:
        abort(404)
    except MatchPermissionError:
        abort(403)
    except MatchmakingError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã lưu số Zalo. Số chỉ hiển thị cho bên còn lại của kèo.", "success")
    return redirect(url_for("matches.detail", match_id=match_id))


@matches_bp.post(
    "/matches/<int:match_id>/requests/<int:participant_id>/accept"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def accept(match_id: int, participant_id: int):
    return _decide_request(match_id, participant_id, accept_request=True)


@matches_bp.post(
    "/matches/<int:match_id>/requests/<int:participant_id>/reject"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def reject(match_id: int, participant_id: int):
    return _decide_request(match_id, participant_id, accept_request=False)


@matches_bp.post("/matches/<int:match_id>/requests/withdraw")
@roles_required(UserRole.USER, UserRole.OWNER)
def withdraw(match_id: int):
    form = MatchActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu rút không hợp lệ.", "danger")
        return redirect(url_for("matches.detail", match_id=match_id))
    try:
        withdraw_match_request(match_id=match_id, user=current_user)
    except MatchNotFoundError:
        abort(404)
    except MatchPermissionError:
        abort(403)
    except MatchmakingError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã rút khỏi kèo và áp dụng chính sách hoàn tiền tương ứng.", "success")
    return redirect(url_for("matches.detail", match_id=match_id))


def _decide_request(match_id: int, participant_id: int, *, accept_request: bool):
    form = MatchActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu xử lý không hợp lệ.", "danger")
        return redirect(url_for("matches.detail", match_id=match_id))
    try:
        decide_match_request(
            match_id=match_id,
            participant_id=participant_id,
            creator=current_user,
            accept=accept_request,
        )
    except MatchNotFoundError:
        abort(404)
    except MatchPermissionError:
        abort(403)
    except MatchmakingError as exc:
        flash(str(exc), "warning")
    else:
        flash(
            "Đã chấp nhận yêu cầu." if accept_request else "Đã từ chối yêu cầu.",
            "success",
        )
    return redirect(url_for("matches.detail", match_id=match_id))


def _locked_match_type(booking_mode: str) -> str | None:
    if booking_mode == BookingMode.FIND_OPPONENT.value:
        return MatchType.FIND_OPPONENT.value
    if booking_mode == BookingMode.FIND_PLAYERS.value:
        return MatchType.FIND_PLAYERS.value
    return None


def _default_match_title(booking, match_type: str) -> str:
    action = "Tìm đối thủ" if match_type == MatchType.FIND_OPPONENT.value else "Tìm thêm người"
    return f"{action} đá tại {booking.field.venue.name}"


def _contact_visible(booking) -> bool:
    if booking.status not in {
        BookingStatus.PARTIALLY_PAID.value,
        BookingStatus.PAID.value,
    }:
        return False
    end_at = datetime.combine(booking.booking_date, booking.end_time)
    return end_at > current_vietnam_datetime()
