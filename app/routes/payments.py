from flask import Blueprint, abort, flash, redirect, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import BookingActionForm
from app.models import UserRole
from app.services import (
    PaymentError,
    PaymentNotFoundError,
    PaymentPermissionError,
    pay_contribution_with_mock,
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
        return _booking_redirect(booking_code)

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
    return _booking_redirect(booking_code)


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


def _booking_redirect(booking_code: str):
    return redirect(url_for("bookings.detail", booking_code=booking_code))
