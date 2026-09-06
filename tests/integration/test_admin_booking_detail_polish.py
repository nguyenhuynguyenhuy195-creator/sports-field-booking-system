"""Focused presentation coverage for the Admin Booking Detail micro-fix."""

from app.models import UserRole
from tests.integration.test_admin import (
    create_user,
    login,
    seed_booking_detail_data,
)


def _detail_fixture(app, client):
    admin = create_user(app, email="polish-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="polish-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="polish-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)
    return data


def test_normal_booking_keeps_hero_status_without_investigation_sidebar(app, client):
    data = _detail_fixture(app, client)
    page = client.get(f"/admin/bookings/{data['normal']}").get_data(as_text=True)

    assert 'data-admin-booking-status="PAID"' in page
    assert 'data-current-booking-status=' not in page
    assert "TÓM TẮT KIỂM TRA" not in page
    assert "Điểm cần lưu ý" not in page
    assert "ĐIỀU TRA READ-ONLY" not in page
    assert "Trạng thái hiện tại không được dùng" not in page
    assert "Online ròng đang ghi nhận: <strong>" not in page


def test_payment_ids_are_preserved_inside_native_technical_disclosure(app, client):
    data = _detail_fixture(app, client)
    page = client.get(f"/admin/bookings/{data['normal']}").get_data(as_text=True)
    payment = page.split('data-payment-history-item=', 1)[1].split('admin-related-records', 1)[0]

    assert "54.000 đ" in payment
    assert "Ví MoMo" in payment
    assert "Thời điểm thanh toán" in payment
    assert '<details class="admin-transaction-technical">' in payment
    technical = payment.split('<details class="admin-transaction-technical">', 1)[1]
    assert "ORDER-DETAIL-NORMAL" in technical
    assert "REQUEST-DETAIL-NORMAL" in technical
    assert "TRANS-DETAIL-NORMAL" in technical


def test_refund_sections_use_actual_persisted_history_only(app, client):
    data = _detail_fixture(app, client)
    normal_page = client.get(f"/admin/bookings/{data['normal']}").get_data(as_text=True)
    attention_page = client.get(
        f"/admin/bookings/{data['refund_attention']}"
    ).get_data(as_text=True)

    assert 'data-refund-empty' in normal_page
    assert "Hoàn tiền: <strong>Không phát sinh</strong>" in normal_page
    assert 'aria-labelledby="booking-refund-title"' not in normal_page
    assert 'aria-labelledby="booking-refund-title"' in attention_page
    assert "Chờ xử lý" in attention_page
    assert "Hoàn tiền thất bại" in attention_page
    assert attention_page.count('<details class="admin-transaction-technical">') >= 4


def test_attention_and_reconciliation_warnings_remain_visible(app, client):
    admin = create_user(app, email="warning-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="warning-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="warning-player@example.com")
    detail_data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    payment_attention = client.get(
        f"/admin/bookings/{detail_data['payment_attention_codes']['PENDING']}"
    ).get_data(as_text=True)
    reconciliation = client.get(
        f"/admin/bookings/{detail_data['missing_payment']}"
    ).get_data(as_text=True)
    cancellation = client.get(
        f"/admin/bookings/{detail_data['full_refund']}"
    ).get_data(as_text=True)

    assert "thanh toán cần theo dõi" not in payment_attention
    assert 'data-financial-reconciliation-warning' in reconciliation
    assert "Lý do hủy" in cancellation


def test_match_link_and_event_history_use_progressive_disclosure(app, client):
    data = _detail_fixture(app, client)
    page = client.get(f"/admin/bookings/{data['completed_match']}").get_data(
        as_text=True
    )

    assert "Xem chi tiết kèo" in page
    assert 'data-event-type="booking_created"' in page
    assert 'data-event-type="payment_success"' in page
    assert 'data-event-type="match_created"' in page
    assert '<details class="admin-history-disclosure">' in page
    assert "Lịch sử sự kiện (4)" in page
