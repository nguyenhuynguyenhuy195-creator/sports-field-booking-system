from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.decorators import roles_required
from app.forms import OwnerApplicationForm
from app.models import OwnerApplicationStatus, UserRole
from app.services import (
    OwnerApplicationError,
    find_pending_application,
    list_user_applications,
    submit_owner_application,
)


owner_applications_bp = Blueprint(
    "owner_applications",
    __name__,
    url_prefix="/owner-applications",
)

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


__all__ = ["owner_applications_bp"]
