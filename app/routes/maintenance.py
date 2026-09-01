from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import MaintenanceActionForm, MaintenanceForm
from app.models import FieldMaintenanceStatus, UserRole
from app.services import (
    MaintenanceError,
    MaintenanceNotFoundError,
    MaintenancePermissionError,
    cancel_maintenance,
    create_maintenance,
    current_vietnam_datetime,
    get_effective_maintenance_status,
    get_owner_maintenance,
    list_owner_maintenances,
)


maintenance_bp = Blueprint("maintenance", __name__)

MAINTENANCE_STATUS_LABELS = {
    FieldMaintenanceStatus.ACTIVE.value: "Đang hoạt động",
    FieldMaintenanceStatus.CANCELLED.value: "Đã hủy",
    FieldMaintenanceStatus.COMPLETED.value: "Đã hoàn thành",
}


@maintenance_bp.get(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/maintenances"
)
@roles_required(UserRole.OWNER)
def owner_index(venue_id: int, field_id: int):
    field, maintenances = _load_field_for_path(
        venue_id=venue_id,
        field_id=field_id,
    )
    now = current_vietnam_datetime()
    effective_statuses = {
        maintenance.id: get_effective_maintenance_status(
            maintenance,
            now=now,
        )
        for maintenance in maintenances
    }
    current_or_upcoming = [
        maintenance
        for maintenance in maintenances
        if effective_statuses[maintenance.id]
        == FieldMaintenanceStatus.ACTIVE.value
    ]
    history = sorted(
        (
            maintenance
            for maintenance in maintenances
            if effective_statuses[maintenance.id]
            != FieldMaintenanceStatus.ACTIVE.value
        ),
        key=lambda maintenance: (
            maintenance.maintenance_date,
            maintenance.start_time,
            maintenance.id,
        ),
        reverse=True,
    )
    current_ids = {
        maintenance.id
        for maintenance in current_or_upcoming
        if datetime.combine(
            maintenance.maintenance_date,
            maintenance.start_time,
        )
        <= now
    }
    return render_template(
        "owner/maintenance/index.html",
        field=field,
        maintenances=maintenances,
        effective_statuses=effective_statuses,
        current_or_upcoming=current_or_upcoming,
        history=history,
        current_ids=current_ids,
        status_labels=MAINTENANCE_STATUS_LABELS,
        action_form=MaintenanceActionForm(),
    )


@maintenance_bp.route(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/maintenances/new",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_create(venue_id: int, field_id: int):
    field, _ = _load_field_for_path(venue_id=venue_id, field_id=field_id)
    form = MaintenanceForm()
    if not form.is_submitted():
        form.maintenance_date.data = current_vietnam_datetime().date()
    if form.validate_on_submit():
        try:
            create_maintenance(
                owner=current_user,
                field_id=field_id,
                maintenance_date=form.maintenance_date.data,
                start_time=form.start_time_value,
                end_time=form.end_time_value,
                reason=form.reason.data,
            )
        except MaintenancePermissionError:
            abort(403)
        except MaintenanceNotFoundError:
            abort(404)
        except MaintenanceError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã tạo lịch bảo trì cho sân.", "success")
            return redirect(
                url_for(
                    "maintenance.owner_index",
                    venue_id=venue_id,
                    field_id=field_id,
                )
            )

    return render_template(
        "owner/maintenance/form.html",
        form=form,
        field=field,
    )


@maintenance_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>"
    "/maintenances/<int:maintenance_id>/cancel"
)
@roles_required(UserRole.OWNER)
def owner_cancel(
    venue_id: int,
    field_id: int,
    maintenance_id: int,
):
    _load_maintenance_for_path(
        venue_id=venue_id,
        field_id=field_id,
        maintenance_id=maintenance_id,
    )
    form = MaintenanceActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu hủy lịch bảo trì không hợp lệ.", "danger")
        return redirect(
            url_for(
                "maintenance.owner_index",
                venue_id=venue_id,
                field_id=field_id,
            )
        )
    try:
        cancel_maintenance(
            maintenance_id=maintenance_id,
            owner=current_user,
        )
    except MaintenancePermissionError:
        abort(403)
    except MaintenanceNotFoundError:
        abort(404)
    except MaintenanceError as exc:
        flash(str(exc), "warning")
    else:
        flash("Đã hủy lịch bảo trì.", "success")
    return redirect(
        url_for(
            "maintenance.owner_index",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


def _load_field_for_path(*, venue_id: int, field_id: int):
    try:
        field, maintenances = list_owner_maintenances(
            field_id=field_id,
            owner_id=current_user.id,
        )
    except MaintenanceNotFoundError:
        abort(404)
    except MaintenancePermissionError:
        abort(403)
    if field.venue_id != venue_id:
        abort(404)
    return field, maintenances


def _load_maintenance_for_path(
    *,
    venue_id: int,
    field_id: int,
    maintenance_id: int,
):
    try:
        maintenance = get_owner_maintenance(
            maintenance_id=maintenance_id,
            owner_id=current_user.id,
        )
    except MaintenanceNotFoundError:
        abort(404)
    except MaintenancePermissionError:
        abort(403)
    if (
        maintenance.field_id != field_id
        or maintenance.field.venue_id != venue_id
    ):
        abort(404)
    return maintenance
