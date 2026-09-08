"""Focused presentation checks for Phase 4.1C responsive and accessibility fixes."""

from pathlib import Path

from app.models import UserRole
from tests.integration.test_bookings import create_bookable_field, create_user, login


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_find_venue_price_inputs_have_explicit_associated_labels(client):
    html = client.get("/venues").get_data(as_text=True)

    assert '<label class="visually-hidden" for="min_price">Giá từ</label>' in html
    assert '<label class="visually-hidden" for="max_price">Giá đến</label>' in html


def test_booking_wizard_has_programmatic_focus_targets_and_native_slot_buttons(app, client):
    owner = create_user(app, email="a11y-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="a11y-player@example.com")
    venue_id, field_id = create_bookable_field(app, owner_id=owner.id)
    login(client, email=player.email)

    html = client.get(
        f"/venues/{venue_id}/fields/{field_id}/bookings/new"
    ).get_data(as_text=True)
    script = (REPOSITORY_ROOT / "app/static/js/booking-flow.js").read_text(
        encoding="utf-8"
    )

    assert html.count('data-step-focus tabindex="-1"') == 3
    assert 'data-availability-grid role="group"' in html
    assert 'role="grid"' not in html
    assert 'role", "gridcell"' not in script
    assert "button.disabled = !actionable;" in script
    assert "focusTarget?.focus({ preventScroll: true });" in script
    assert "box.focus({ preventScroll: true });" in script


def test_confirmation_modal_restores_visible_opener_focus():
    script = (REPOSITORY_ROOT / "app/static/js/confirm-actions.js").read_text(
        encoding="utf-8"
    )

    assert 'modalElement.addEventListener("hidden.bs.modal"' in script
    assert "restoreOpenerFocus = true;" in script
    assert "focusTarget?.isConnected && focusTarget.checkVisibility()" in script
    assert "window.requestAnimationFrame(() => focusTarget.focus());" in script


def test_owner_table_scrolling_stays_in_the_table_wrapper():
    stylesheet = (REPOSITORY_ROOT / "app/static/css/owner.css").read_text(
        encoding="utf-8"
    )

    assert ".owner-dashboard-card .table-responsive," in stylesheet
    assert "max-width: 100%;" in stylesheet
    assert "overflow-x: auto;" in stylesheet


def test_owner_and_admin_consoles_keep_secondary_text_at_accessible_size():
    owner_stylesheet = (REPOSITORY_ROOT / "app/static/css/owner.css").read_text(
        encoding="utf-8"
    )
    admin_stylesheet = (REPOSITORY_ROOT / "app/static/css/admin.css").read_text(
        encoding="utf-8"
    )

    assert "--owner-font-xs: 0.8125rem;" in owner_stylesheet
    assert "--owner-font-sm: 0.8125rem;" in owner_stylesheet
    assert "Accessibility floor: secondary information and controls" in owner_stylesheet
    assert "font-size: 0.8125rem !important;" in owner_stylesheet
    assert "--admin-muted: #526174;" in admin_stylesheet
    assert "Accessibility floor: secondary information and controls" in admin_stylesheet
    assert "font-size: 0.8125rem !important;" in admin_stylesheet


def test_login_register_link_has_explicit_high_contrast_and_focus_style(client):
    html = client.get("/auth/login").get_data(as_text=True)
    stylesheet = (REPOSITORY_ROOT / "app/static/css/app.css").read_text(
        encoding="utf-8"
    )

    assert 'class="auth-register-link"' in html
    assert ".auth-register-link {" in stylesheet
    assert "color: #0f5736;" in stylesheet
    assert ".auth-register-link:focus-visible" in stylesheet
