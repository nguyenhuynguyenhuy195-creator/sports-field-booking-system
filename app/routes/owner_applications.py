from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.decorators import roles_required
from app.forms import OwnerApplicationForm, ReviewOwnerApplicationForm
from app.models import OwnerApplicationStatus, UserRole
from app.services import (
    OwnerApplicationError,
    find_pending_application,
    list_pending_applications,
    list_user_applications,
    review_owner_application,
    submit_owner_application,
)


owner_applications_bp = Blueprint(
    "owner_applications",
    __name__,
    url_prefix="/owner-applications",
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@owner_applications_bp.route("/new", methods=["GET", "POST"])
@roles_required(UserRole.USER)
def create():
    pending_application = find_pending_application(current_user.id)
    form = OwnerApplicationForm()

    if form.validate_on_submit():
        try:
            submit_owner_application(
                user=current_user,
                business_name=form.business_name.data,
                contact_phone=form.contact_phone.data,
                note=form.note.data,
            )
        except OwnerApplicationError as exc:
            flash(str(exc), "warning")
        else:
            flash(
                "Đã gửi yêu cầu trở thành chủ sân. "
                "Quản trị viên sẽ xét duyệt trong thời gian sớm nhất.",
                "success",
            )
            return redirect(url_for("owner_applications.mine"))

    return render_template(
        "owner_applications/new.html",
        form=form,
        pending_application=pending_application,
    )


@owner_applications_bp.get("/mine")
@login_required
def mine():
    applications = list_user_applications(current_user.id)
    return render_template(
        "owner_applications/mine.html",
        applications=applications,
        status_labels={
            OwnerApplicationStatus.PENDING.value: "Đang chờ",
            OwnerApplicationStatus.APPROVED.value: "Đã chấp nhận",
            OwnerApplicationStatus.REJECTED.value: "Đã từ chối",
            OwnerApplicationStatus.CANCELLED.value: "Đã hủy",
        },
    )


@admin_bp.get("/owner-applications")
@roles_required(UserRole.ADMIN)
def owner_applications():
    applications = list_pending_applications()
    return render_template(
        "admin/owner_applications.html",
        applications=applications,
        review_forms={
            application.id: ReviewOwnerApplicationForm(
                prefix=f"application-{application.id}"
            )
            for application in applications
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
                "Đã chấp nhận yêu cầu và chuyển tài khoản thành OWNER."
                if form.decision.data
                == OwnerApplicationStatus.APPROVED.value
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
