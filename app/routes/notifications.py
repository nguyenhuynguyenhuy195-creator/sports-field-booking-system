from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.models import UserRole
from app.services.notification import (
    count_unread_notifications, list_recent_notifications, list_user_notifications,
    mark_all_notifications_read, mark_notification_read,
)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@notifications_bp.get("")
@roles_required(UserRole.USER)
def index():
    pagination, notifications = list_user_notifications(current_user.id, page=request.args.get("page", 1, type=int))
    return render_template("notifications/index.html", notifications=notifications, pagination=pagination)


@notifications_bp.get("/recent")
@roles_required(UserRole.USER)
def recent():
    return jsonify(unread_count=count_unread_notifications(current_user.id),
                   notifications=list_recent_notifications(current_user.id))


@notifications_bp.post("/<int:notification_id>/read")
@roles_required(UserRole.USER)
def read(notification_id):
    if not mark_notification_read(current_user.id, notification_id):
        abort(404)
    if request.is_json:
        return jsonify(ok=True)
    return redirect(url_for("notifications.index"))


@notifications_bp.post("/read-all")
@roles_required(UserRole.USER)
def read_all():
    mark_all_notifications_read(current_user.id)
    if request.is_json:
        return jsonify(ok=True)
    return redirect(url_for("notifications.index"))
