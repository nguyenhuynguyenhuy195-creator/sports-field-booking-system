from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from app.decorators import roles_required
from app.forms import PriceSlotForm, PricingActionForm
from app.models import (
    DAY_OF_WEEK_LABELS,
    FieldStatus,
    PriceSlotStatus,
    UserRole,
)
from app.services import (
    PricingError,
    PricingNotFoundError,
    PricingPermissionError,
    create_price_slot,
    get_owner_price_slot,
    list_owner_price_slots,
    set_field_activation,
    set_price_slot_status,
    update_price_slot,
)


pricing_bp = Blueprint("pricing", __name__)

PRICE_SLOT_STATUS_LABELS = {
    PriceSlotStatus.ACTIVE.value: "Đang áp dụng",
    PriceSlotStatus.INACTIVE.value: "Tạm ngưng",
}


@pricing_bp.get(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/prices"
)
@roles_required(UserRole.OWNER)
def owner_index(venue_id: int, field_id: int):
    field, slots = _load_field_for_path(venue_id=venue_id, field_id=field_id)
    return render_template(
        "owner/pricing/index.html",
        field=field,
        slots=slots,
        day_labels=DAY_OF_WEEK_LABELS,
        status_labels=PRICE_SLOT_STATUS_LABELS,
        action_form=PricingActionForm(),
    )


@pricing_bp.route(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>/prices/new",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_create(venue_id: int, field_id: int):
    field, _ = _load_field_for_path(venue_id=venue_id, field_id=field_id)
    form = PriceSlotForm()
    if form.validate_on_submit():
        try:
            create_price_slot(
                owner=current_user,
                field_id=field_id,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time_value,
                end_time=form.end_time_value,
                hourly_price=form.hourly_price.data,
            )
        except PricingPermissionError:
            abort(403)
        except PricingNotFoundError:
            abort(404)
        except PricingError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã thêm khung giá đang áp dụng.", "success")
            return redirect(
                url_for(
                    "pricing.owner_index",
                    venue_id=venue_id,
                    field_id=field_id,
                )
            )

    return render_template(
        "owner/pricing/form.html",
        form=form,
        field=field,
        page_title="Thêm khung giá",
        submit_label="Tạo khung giá",
    )


@pricing_bp.route(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>"
    "/prices/<int:slot_id>/edit",
    methods=["GET", "POST"],
)
@roles_required(UserRole.OWNER)
def owner_edit(venue_id: int, field_id: int, slot_id: int):
    slot = _load_slot_for_path(
        venue_id=venue_id,
        field_id=field_id,
        slot_id=slot_id,
    )
    form = PriceSlotForm(obj=slot)
    if not form.is_submitted():
        form.set_times(slot.start_time, slot.end_time)
    if form.validate_on_submit():
        try:
            update_price_slot(
                slot_id=slot_id,
                owner=current_user,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time_value,
                end_time=form.end_time_value,
                hourly_price=form.hourly_price.data,
            )
        except PricingPermissionError:
            abort(403)
        except PricingNotFoundError:
            abort(404)
        except PricingError as exc:
            flash(str(exc), "warning")
        else:
            flash("Đã cập nhật khung giá.", "success")
            return redirect(
                url_for(
                    "pricing.owner_index",
                    venue_id=venue_id,
                    field_id=field_id,
                )
            )

    return render_template(
        "owner/pricing/form.html",
        form=form,
        field=slot.field,
        slot=slot,
        page_title="Chỉnh sửa khung giá",
        submit_label="Lưu thay đổi",
    )


@pricing_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>"
    "/prices/<int:slot_id>/status/<string:status>"
)
@roles_required(UserRole.OWNER)
def owner_set_slot_status(
    venue_id: int,
    field_id: int,
    slot_id: int,
    status: str,
):
    _load_slot_for_path(
        venue_id=venue_id,
        field_id=field_id,
        slot_id=slot_id,
    )
    form = PricingActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu đổi trạng thái không hợp lệ.", "danger")
        return redirect(
            url_for(
                "pricing.owner_index",
                venue_id=venue_id,
                field_id=field_id,
            )
        )
    try:
        set_price_slot_status(
            slot_id=slot_id,
            owner=current_user,
            status=status,
        )
    except PricingPermissionError:
        abort(403)
    except PricingNotFoundError:
        abort(404)
    except PricingError as exc:
        flash(str(exc), "warning")
    else:
        message = (
            "Đã bật lại khung giá."
            if status == PriceSlotStatus.ACTIVE.value
            else "Đã tạm ngưng khung giá."
        )
        flash(message, "success")
    return redirect(
        url_for(
            "pricing.owner_index",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


@pricing_bp.post(
    "/owner/venues/<int:venue_id>/fields/<int:field_id>"
    "/status/<string:status>"
)
@roles_required(UserRole.OWNER)
def owner_set_field_status(venue_id: int, field_id: int, status: str):
    _load_field_for_path(venue_id=venue_id, field_id=field_id)
    form = PricingActionForm()
    if not form.validate_on_submit():
        flash("Yêu cầu đổi trạng thái không hợp lệ.", "danger")
        return redirect(
            url_for(
                "pricing.owner_index",
                venue_id=venue_id,
                field_id=field_id,
            )
        )
    try:
        set_field_activation(
            field_id=field_id,
            owner=current_user,
            status=status,
        )
    except PricingPermissionError:
        abort(403)
    except PricingNotFoundError:
        abort(404)
    except PricingError as exc:
        flash(str(exc), "warning")
    else:
        message = (
            "Sân đã được bật và có thể hiển thị công khai khi cơ sở hoạt động."
            if status == FieldStatus.ACTIVE.value
            else "Sân đã được tạm ngưng."
        )
        flash(message, "success")
    return redirect(
        url_for(
            "pricing.owner_index",
            venue_id=venue_id,
            field_id=field_id,
        )
    )


def _load_field_for_path(*, venue_id: int, field_id: int):
    try:
        field, slots = list_owner_price_slots(
            field_id=field_id,
            owner_id=current_user.id,
        )
    except PricingNotFoundError:
        abort(404)
    except PricingPermissionError:
        abort(403)
    if field.venue_id != venue_id:
        abort(404)
    return field, slots


def _load_slot_for_path(*, venue_id: int, field_id: int, slot_id: int):
    try:
        slot = get_owner_price_slot(slot_id=slot_id, owner_id=current_user.id)
    except PricingNotFoundError:
        abort(404)
    except PricingPermissionError:
        abort(403)
    if slot.field_id != field_id or slot.field.venue_id != venue_id:
        abort(404)
    return slot
