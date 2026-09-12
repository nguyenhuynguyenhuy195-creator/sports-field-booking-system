from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)
from flask_login import current_user

from app.decorators import roles_required
from app.forms import BookingActionForm
from app.extensions import csrf, db
from app.models import (
    ContributionType,
    Match,
    MatchParticipant,
    Payment,
    PaymentProvider,
    PaymentStatus,
    UserRole,
)
from app.services import (
    PaymentError,
    PaymentNotFoundError,
    PaymentPermissionError,
    inspect_momo_return,
    inspect_vnpay_return,
    pay_contribution_with_mock,
    process_momo_payment_notification,
    process_vnpay_ipn,
    start_momo_payment,
    start_momo_top_up,
    start_vnpay_payment,
    start_vnpay_top_up,
    top_up_booking_with_mock,
)


payments_bp = Blueprint("payments", __name__)


@payments_bp.before_request
def reject_disabled_momo():
    # Keep legacy URLs, but reject them before route code can touch DB/network.
    if request.endpoint in {
        "payments.pay_momo", "payments.top_up_momo",
        "payments.momo_return", "payments.momo_ipn",
    } and not current_app.config.get("MOMO_ENABLED"):
        abort(404)


@payments_bp.before_request
def reject_disabled_vnpay():
    # Fail closed when disabled so no Payment row or VnpayClient call can
    # happen, on either the checkout-initiation or the return/IPN routes.
    if request.endpoint in {
        "payments.pay_vnpay", "payments.top_up_vnpay",
        "payments.vnpay_return", "payments.vnpay_ipn",
        "payments.vnpay_payment_status",
    } and not current_app.config.get("VNPAY_ENABLED"):
        abort(404)



@payments_bp.post(
    "/bookings/<string:booking_code>/contributions/"
    "<int:contribution_id>/payments/mock"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def pay_mock(booking_code: str, contribution_id: int):
    form = BookingActionForm(prefix="payment")
    if not form.validate_on_submit():
        flash("Yêu cầu thanh toán không hợp lệ. Vui lòng thử lại.", "danger")
        return _payment_redirect(booking_code)

    try:
        payment = pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=contribution_id,
            payer=current_user,
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
    else:
        flash(
            f"Thanh toán thử nghiệm {payment.amount:,.0f} đ thành công.",
            "success",
        )
    return _payment_redirect(booking_code)


@payments_bp.post("/bookings/<string:booking_code>/payments/mock/top-up")
@roles_required(UserRole.USER, UserRole.OWNER)
def top_up_mock(booking_code: str):
    form = BookingActionForm(prefix="top-up")
    if not form.validate_on_submit():
        flash("Yêu cầu trả phần còn thiếu không hợp lệ.", "danger")
        return _booking_redirect(booking_code)

    try:
        payment = top_up_booking_with_mock(
            booking_code=booking_code,
            payer=current_user,
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
    else:
        flash(
            f"Đã thanh toán thử nghiệm phần còn thiếu {payment.amount:,.0f} đ.",
            "success",
        )
    return _booking_redirect(booking_code)


@payments_bp.post(
    "/bookings/<string:booking_code>/contributions/"
    "<int:contribution_id>/payments/momo"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def pay_momo(booking_code: str, contribution_id: int):
    form = BookingActionForm(prefix="payment")
    if not form.validate_on_submit():
        flash("Yêu cầu thanh toán MoMo không hợp lệ.", "danger")
        return _payment_redirect(booking_code)
    try:
        checkout = start_momo_payment(
            booking_code=booking_code,
            contribution_id=contribution_id,
            payer=current_user,
            redirect_url=current_app.config["MOMO_REDIRECT_URL"],
            ipn_url=current_app.config["MOMO_IPN_URL"],
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
        return _payment_redirect(booking_code)
    return redirect(checkout.pay_url)


@payments_bp.post("/bookings/<string:booking_code>/payments/momo/top-up")
@roles_required(UserRole.USER, UserRole.OWNER)
def top_up_momo(booking_code: str):
    form = BookingActionForm(prefix="top-up")
    if not form.validate_on_submit():
        flash("Yêu cầu trả phần cọc còn thiếu không hợp lệ.", "danger")
        return _booking_redirect(booking_code)
    try:
        checkout = start_momo_top_up(
            booking_code=booking_code,
            payer=current_user,
            redirect_url=current_app.config["MOMO_REDIRECT_URL"],
            ipn_url=current_app.config["MOMO_IPN_URL"],
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
        return _booking_redirect(booking_code)
    return redirect(checkout.pay_url)


@payments_bp.post(
    "/bookings/<string:booking_code>/contributions/"
    "<int:contribution_id>/payments/vnpay"
)
@roles_required(UserRole.USER, UserRole.OWNER)
def pay_vnpay(booking_code: str, contribution_id: int):
    form = BookingActionForm(prefix="payment")
    if not form.validate_on_submit():
        flash("Yêu cầu thanh toán VNPAY không hợp lệ. Vui lòng thử lại.", "danger")
        return _payment_redirect(booking_code)
    try:
        checkout = start_vnpay_payment(
            booking_code=booking_code,
            contribution_id=contribution_id,
            payer=current_user,
            return_url=current_app.config["VNPAY_RETURN_URL"],
            ip_addr=request.remote_addr or "127.0.0.1",
            bank_code=request.form.get("bank_code") or None,
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
        return _payment_redirect(booking_code)
    return redirect(checkout.pay_url)


@payments_bp.post("/bookings/<string:booking_code>/payments/vnpay/top-up")
@roles_required(UserRole.USER, UserRole.OWNER)
def top_up_vnpay(booking_code: str):
    form = BookingActionForm(prefix="top-up")
    if not form.validate_on_submit():
        flash("Yêu cầu trả phần cọc còn thiếu qua VNPAY không hợp lệ.", "danger")
        return _booking_redirect(booking_code)
    try:
        checkout = start_vnpay_top_up(
            booking_code=booking_code,
            payer=current_user,
            return_url=current_app.config["VNPAY_RETURN_URL"],
            ip_addr=request.remote_addr or "127.0.0.1",
            bank_code=request.form.get("bank_code") or None,
        )
    except PaymentNotFoundError:
        abort(404)
    except PaymentPermissionError:
        abort(403)
    except PaymentError as exc:
        flash(str(exc), "warning")
        return _booking_redirect(booking_code)
    return redirect(checkout.pay_url)


@payments_bp.get("/payments/momo/return")
def momo_return():
    try:
        payment = inspect_momo_return(request.args.to_dict())
    except PaymentError as exc:
        flash(f"MoMo chưa xác nhận thanh toán: {exc}", "warning")
        return _safe_booking_return()
    if payment.status == "SUCCESS":
        flash("MoMo đã xác nhận khoản cọc thành công.", "success")
    elif payment.status == "PENDING":
        flash(
            "Đang chờ MoMo xác nhận. Vui lòng tải lại trang sau ít phút.",
            "info",
        )
    else:
        flash("Giao dịch MoMo chưa thành công hoặc đã bị hủy.", "warning")
    return _payment_return_redirect(payment)


@payments_bp.get("/payments/vnpay/return")
def vnpay_return():
    try:
        payment = inspect_vnpay_return(request.args.to_dict())
    except PaymentError as exc:
        flash(f"VNPAY chưa xác nhận thanh toán: {exc}", "warning")
        return _safe_booking_return()
    if payment.status == "SUCCESS":
        flash("VNPAY đã xác nhận khoản cọc thành công.", "success")
    elif payment.status == "PENDING":
        flash(
            "Đang chờ VNPAY xác nhận. Vui lòng tải lại trang sau ít phút.",
            "info",
        )
        # IPN remains the only path that may set SUCCESS (never this route).
        # Attach a verified payment id so the page can watch it client-side
        # and refresh itself once IPN lands, instead of staying stale.
        return _payment_return_redirect(payment, watch=True)
    else:
        flash("Giao dịch VNPAY chưa thành công hoặc đã bị hủy.", "warning")
    return _payment_return_redirect(payment)


@payments_bp.get("/payments/vnpay/ipn")
def vnpay_ipn():
    try:
        result = process_vnpay_ipn(request.args.to_dict())
    except PaymentError as exc:
        return jsonify(RspCode="99", Message=str(exc))
    return jsonify(RspCode=result.rsp_code, Message=result.message)


@payments_bp.get("/payments/vnpay/<int:payment_id>/status")
@roles_required(UserRole.USER, UserRole.OWNER)
def vnpay_payment_status(payment_id: int):
    """Read-only status poll for a browser watching its own VNPAY payment.

    Returns only {"status": ...}. No hash, gateway payload, secret or other
    transaction detail. IPN is still the only path that can ever change
    this status — this endpoint never mutates anything.
    """
    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.provider != PaymentProvider.VNPAY.value:
        abort(404)
    if payment.payer_id != current_user.id:
        abort(403)
    return jsonify(status=payment.status)


def resolve_watchable_vnpay_payment_id(*, user) -> int | None:
    """Read ?payment_watch=<id> from the current request and return it only
    if it names a VNPAY Payment the given user actually paid and that is
    still PENDING. Used by bookings/matches detail routes to decide whether
    to render the client-side status-watch marker — server-side authorized,
    never trusts the query string on its own.
    """
    raw_id = request.args.get("payment_watch", "")
    if not raw_id.isdigit():
        return None
    payment = db.session.get(Payment, int(raw_id))
    if (
        payment is None
        or payment.provider != PaymentProvider.VNPAY.value
        or payment.payer_id != user.id
        or payment.status != PaymentStatus.PENDING.value
    ):
        return None
    return payment.id


def _payment_return_redirect(payment, *, watch: bool = False):
    """Choose a view from verified payment relationships, never callback URLs."""
    watch_args = {"payment_watch": payment.id} if watch else {}
    contribution = payment.contribution
    if (
        contribution.booking_id == payment.booking_id
        and contribution.contribution_type in {
            ContributionType.OPPONENT.value,
            ContributionType.PLAYER.value,
        }
    ):
        match_id = db.session.scalar(
            db.select(Match.id)
            .join(MatchParticipant, MatchParticipant.match_id == Match.id)
            .where(
                Match.booking_id == payment.booking_id,
                MatchParticipant.contribution_id == payment.contribution_id,
                MatchParticipant.user_id == payment.payer_id,
            )
            .order_by(Match.id)
        )
        if match_id is not None:
            return redirect(
                url_for("matches.detail", match_id=match_id, **watch_args)
            )

    if (
        current_user.is_authenticated
        and current_user.role in {UserRole.USER.value, UserRole.OWNER.value}
        and current_user.id == payment.booking.user_id
    ):
        return _booking_redirect(payment.booking.booking_code, **watch_args)
    return _safe_booking_return()


def _safe_booking_return():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("bookings.index")))
    if current_user.role in {UserRole.USER.value, UserRole.OWNER.value}:
        return redirect(url_for("bookings.index"))
    return redirect(url_for("main.home"))


@payments_bp.post("/payments/momo/ipn")
@csrf.exempt
def momo_ipn():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(resultCode=1, message="Invalid JSON"), 400
    try:
        process_momo_payment_notification(payload)
    except PaymentNotFoundError:
        return jsonify(resultCode=1, message="Order not found"), 404
    except PaymentError:
        return jsonify(resultCode=1, message="Invalid notification"), 400
    return jsonify(resultCode=0, message="Success")


def _booking_redirect(booking_code: str, **extra_args):
    return redirect(url_for("bookings.detail", booking_code=booking_code, **extra_args))


def _payment_redirect(booking_code: str):
    raw_match_id = request.args.get("return_to_match", "")
    if raw_match_id.isdigit():
        return redirect(url_for("matches.detail", match_id=int(raw_match_id)))
    return _booking_redirect(booking_code)
