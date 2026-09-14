"""Booking pages must describe terminal states truthfully.

Two failure shapes are covered here, both found by rendering the real pages
rather than by reading the template.

1. A cancelled booking with no Refund row at all was headed "Đã hoàn tiền · 0 đ"
   in the owner card. Zero refunds is not a completed refund: either nothing was
   ever collected, or what was paid was forfeited under the self-cancel policy.
   The template's own comment already required this -- "never say a refund is
   done unless every one of them is RefundStatus.SUCCESS" -- but the empty case
   fell through to the "already refunded" wording.

2. Terminal bookings must not invite further payment. The status banners and the
   pay-at-venue call to action are asserted per status, so a future edit cannot
   quietly start asking a user to pay for a booking that no longer exists.
"""

from __future__ import annotations

import re
from datetime import time

import pytest

from app.extensions import db
from app.models import Booking, BookingMode, BookingStatus, User, UserRole
from app.services import (
    cancel_user_booking,
    create_booking,
    pay_contribution_with_mock,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)


OWNER_EMAIL = "wording-owner@example.com"
USER_EMAIL = "wording-user@example.com"


@pytest.fixture()
def paid_booking(app):
    """A DIRECT_BOOKING with its full deposit paid, ready to be put in any state."""
    owner = create_user(app, email=OWNER_EMAIL, role=UserRole.OWNER)
    user = create_user(app, email=USER_EMAIL)
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, user.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        code, booking_id = booking.booking_code, booking.id
        own = next(i for i in booking.contributions if i.user_id == user.id)
        pay_contribution_with_mock(
            booking_code=code, contribution_id=own.id,
            payer=db.session.get(User, user.id),
        )
    return {"owner": owner, "user": user, "code": code, "booking_id": booking_id}


def text_of(client, url) -> str:
    response = client.get(url)
    assert response.status_code == 200, f"{url} -> {response.status_code}"
    html = response.get_data(as_text=True)
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def force_status(app, booking_id, status):
    with app.app_context():
        db.session.get(Booking, booking_id).status = status
        db.session.commit()


# --- 5. a refund that does not exist is never announced ----------------------


def test_owner_card_does_not_claim_a_refund_that_never_happened(
    app, client, paid_booking
):
    with app.app_context():
        cancel_user_booking(
            booking_code=paid_booking["code"],
            user=db.session.get(User, paid_booking["user"].id),
        )
        booking = db.session.get(Booking, paid_booking["booking_id"])
        # The premise: money was taken, and none of it is being refunded.
        assert booking.refunds == []
        assert booking.cancellation_fee_amount > 0

    login(client, email=OWNER_EMAIL)
    text = text_of(client, f"/owner/bookings/{paid_booking['code']}")

    assert "Không phát sinh hoàn tiền" in text
    assert "Đã hoàn tiền" not in text
    assert "Đã hoàn cho người thanh toán" not in text
    # The forfeiture is still explained rather than hidden.
    assert "Phí giữ sân" in text


def test_user_page_does_not_claim_a_refund_that_never_happened(
    app, client, paid_booking
):
    with app.app_context():
        cancel_user_booking(
            booking_code=paid_booking["code"],
            user=db.session.get(User, paid_booking["user"].id),
        )

    login(client, email=USER_EMAIL)
    text = text_of(client, f"/bookings/{paid_booking['code']}")

    assert "Đã hoàn cho người thanh toán" not in text
    assert "Phần tiền cọc không được hoàn" in text


def test_a_cancelled_booking_with_no_payment_says_nothing_was_collected(
    app, client
):
    owner = create_user(app, email="wording-owner2@example.com", role=UserRole.OWNER)
    user = create_user(app, email="wording-user2@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, user.id), field_id=field_id,
            booking_date=booking_day(), start_time=time(8, 0), end_time=time(10, 0),
            booking_mode=BookingMode.DIRECT_BOOKING.value,
        )
        code = booking.booking_code
        cancel_user_booking(
            booking_code=code, user=db.session.get(User, user.id)
        )
        assert db.session.get(Booking, booking.id).refunds == []

    login(client, email="wording-user2@example.com")
    text = text_of(client, f"/bookings/{code}")

    # Nothing was collected, so nothing may hint at money coming back.
    assert "Lịch đặt sân đã được hủy." in text
    for refund_claim in ("Đã hoàn cho người thanh toán", "Khoản tiền đã được hoàn",
                         "Yêu cầu hoàn tiền đang chờ xử lý",
                         "Khoản hoàn tiền đang được xử lý",
                         "Phí giữ sân"):
        assert refund_claim not in text, refund_claim


def test_a_real_refund_is_still_announced(app, client, paid_booking):
    """The guard must not suppress a refund that genuinely exists."""
    from decimal import Decimal

    from app.models import Payment, Refund, RefundStatus

    with app.app_context():
        payment = db.session.scalar(
            db.select(Payment).where(
                Payment.booking_id == paid_booking["booking_id"]
            )
        )
        db.session.add(
            Refund(
                booking_id=paid_booking["booking_id"], payment_id=payment.id,
                recipient_id=paid_booking["user"].id, amount=Decimal("10000"),
                reason="Kiem thu.", order_id="WORDING-REFUND-1",
                request_id="wording-req-1", status=RefundStatus.SUCCESS.value,
            )
        )
        db.session.get(Booking, paid_booking["booking_id"]).status = (
            BookingStatus.CANCELLED.value
        )
        db.session.commit()

    login(client, email=OWNER_EMAIL)
    text = text_of(client, f"/owner/bookings/{paid_booking['code']}")

    assert "Không phát sinh hoàn tiền" not in text
    assert "Đã hoàn tiền" in text


# --- 4. terminal bookings do not ask for more money --------------------------


@pytest.mark.parametrize(
    "status,banner",
    [
        (BookingStatus.CANCELLED.value, "Lịch đặt sân đã được hủy."),
        (BookingStatus.EXPIRED.value, "Khoảng giờ không còn được giữ"),
        (BookingStatus.COMPLETED.value, "Lịch đặt sân đã hoàn thành."),
        (BookingStatus.REFUND_PENDING.value, "Khoản hoàn đang được xử lý"),
    ],
)
def test_closed_bookings_show_their_own_banner(app, client, paid_booking,
                                               status, banner):
    force_status(app, paid_booking["booking_id"], status)
    login(client, email=USER_EMAIL)
    text = text_of(client, f"/bookings/{paid_booking['code']}")

    assert banner in text


VENUE_NOTE = "Bạn sẽ thanh toán phần còn lại trực tiếp tại sân khi đến chơi."
VENUE_ROW = "Còn lại trả tại sân sau khi cọc đủ"


@pytest.mark.parametrize(
    "status",
    [
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
        BookingStatus.REFUND_PENDING.value,
        # COMPLETED was missing from the guard: a booking that had already been
        # played still said "you will pay the rest at the venue when you come
        # to play", in the future tense, beside "đã hoàn thành".
        BookingStatus.COMPLETED.value,
    ],
)
def test_no_pay_at_venue_prompt_on_a_booking_that_is_over(app, client,
                                                          paid_booking, status):
    """balance_due_at_venue stays positive; the page must not act on it."""
    force_status(app, paid_booking["booking_id"], status)
    with app.app_context():
        booking = db.session.get(Booking, paid_booking["booking_id"])
        assert booking.balance_due_at_venue > 0

    login(client, email=USER_EMAIL)
    text = text_of(client, f"/bookings/{paid_booking['code']}")

    assert VENUE_NOTE not in text
    assert VENUE_ROW not in text
    assert "data-payment-submit" not in text


def test_a_live_paid_booking_does_prompt_for_the_venue_balance(app, client,
                                                               paid_booking):
    """The counter-case: a booking that really is upcoming still says so."""
    login(client, email=USER_EMAIL)
    text = text_of(client, f"/bookings/{paid_booking['code']}")

    assert VENUE_NOTE in text
    assert VENUE_ROW in text


@pytest.mark.parametrize(
    "status",
    [
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
        BookingStatus.REFUND_PENDING.value,
        BookingStatus.COMPLETED.value,
    ],
)
def test_a_booking_that_is_over_offers_no_cancel_action(app, client,
                                                        paid_booking, status):
    force_status(app, paid_booking["booking_id"], status)
    login(client, email=USER_EMAIL)
    text = text_of(client, f"/bookings/{paid_booking['code']}")

    assert "Hủy lịch đặt sân" not in text


# --- 8. the legacy policies stay unreachable for new bookings ----------------
#
# The 80/20 split and the funding deadline still exist in the services, because
# bookings created under the old policy have to keep settling correctly. What
# must not happen is a NEW booking wandering into them. These assert the gate
# rather than the arithmetic.


def test_a_new_booking_carries_no_legacy_deadlines(app, paid_booking):
    from app.models import BookingPaymentPolicy

    with app.app_context():
        booking = db.session.get(Booking, paid_booking["booking_id"])

        assert booking.payment_policy == BookingPaymentPolicy.DEPOSIT_30.value
        assert booking.matchmaking_deadline is None
        assert booking.funding_deadline is None


def test_self_cancel_forfeits_rather_than_refunding_eighty_percent(
    app, paid_booking
):
    """DEPOSIT_30: the canceller loses their own deposit, in full.

    The legacy rule refunded the creator 80% and kept 20% as a fee. If a new
    booking ever reached that path, cancellation_fee_amount would be a fifth of
    what was paid instead of all of it, and a Refund row would exist.
    """
    from decimal import Decimal

    with app.app_context():
        before = db.session.get(Booking, paid_booking["booking_id"]).paid_amount
        cancel_user_booking(
            booking_code=paid_booking["code"],
            user=db.session.get(User, paid_booking["user"].id),
        )
        booking = db.session.get(Booking, paid_booking["booking_id"])

        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.cancellation_fee_amount == Decimal(before)
        assert booking.refunds == []
        # Not the 80/20 outcome.
        assert booking.cancellation_fee_amount != (Decimal(before) * Decimal("0.20"))


def test_the_legacy_shortfall_path_requires_a_funding_deadline(app, paid_booking):
    """The query that drives 80/20 cannot select a current booking."""
    from app.services.refund import process_overdue_funding_refunds

    with app.app_context():
        booking = db.session.get(Booking, paid_booking["booking_id"])
        booking.status = BookingStatus.PARTIALLY_PAID.value
        db.session.commit()

        # Deliberately runs the real sweeper: a DEPOSIT_30 booking has no
        # funding_deadline, so it is not eligible and nothing is refunded.
        assert process_overdue_funding_refunds() == 0
        assert db.session.get(Booking, paid_booking["booking_id"]).refunds == []
