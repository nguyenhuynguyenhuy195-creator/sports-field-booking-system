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
from app.extensions import csrf
from app.models import UserRole
from app.services import (
    PaymentError,
    PaymentNotFoundError,
    PaymentPermissionError,
    inspect_momo_return,
    pay_contribution_with_mock,
    process_momo_payment_notification,
    start_momo_payment,
    start_momo_top_up,
    top_up_booking_with_mock,
)


payments_bp = Blueprint("payments", __name__)


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
            f"Thanh toán mô phỏng {payment.amount:,.0f} đ thành công.",
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
            f"Đã thanh toán mô phỏng phần còn thiếu {payment.amount:,.0f} đ.",
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


@payments_bp.get("/payments/momo/return")
def momo_return():
    try:
        payment = inspect_momo_return(request.args.to_dict())
    except PaymentError as exc:
        flash(f"MoMo chưa xác nhận thanh toán: {exc}", "warning")
        return redirect(url_for("bookings.index"))
    if payment.status == "SUCCESS":
        flash("MoMo Sandbox đã xác nhận khoản cọc thành công.", "success")
    elif payment.status == "PENDING":
        flash(
            "Đang chờ MoMo xác nhận qua IPN. Vui lòng tải lại trang sau ít phút.",
            "info",
        )
    else:
        flash("Giao dịch MoMo chưa thành công hoặc đã bị hủy.", "warning")
    return _booking_redirect(payment.booking.booking_code)


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


def _booking_redirect(booking_code: str):
    return redirect(url_for("bookings.detail", booking_code=booking_code))


def _payment_redirect(booking_code: str):
    raw_match_id = request.args.get("return_to_match", "")
    if raw_match_id.isdigit():
        return redirect(url_for("matches.detail", match_id=int(raw_match_id)))
    return _booking_redirect(booking_code)
