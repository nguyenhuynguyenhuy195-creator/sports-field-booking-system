"""Where a payer lands after a gateway/mock payment returns."""

import pytest

from app.extensions import db
from app.models import (
    BookingMode,
    ContributionStatus,
    ContributionType,
    Match,
    MatchMessage,
    MatchParticipant,
    MatchParticipantStatus,
    Payment,
    PaymentStatus,
    User,
    UserRole,
)
from app.services import (
    pay_contribution_with_mock,
    process_vnpay_ipn,
    request_to_join_match,
    start_vnpay_payment,
)
from tests.integration.test_bookings import (
    create_bookable_field,
    create_user,
    login,
)
from tests.integration.test_matchmaking import _create_match, _create_split_booking
from tests.integration.test_vnpay_payments import (
    VNPAY_API_URL,
    VNPAY_HASH_SECRET,
    VNPAY_PAYMENT_URL,
    VNPAY_TMN_CODE,
    build_vnpay_client,
    vnpay_callback_payload,
)


RETURN_URL = "https://example.test/payments/vnpay/return"


@pytest.fixture()
def vnpay_enabled(app):
    app.config.update(
        VNPAY_ENABLED=True,
        VNPAY_TMN_CODE=VNPAY_TMN_CODE,
        VNPAY_HASH_SECRET=VNPAY_HASH_SECRET,
        VNPAY_PAYMENT_URL=VNPAY_PAYMENT_URL,
        VNPAY_API_URL=VNPAY_API_URL,
        VNPAY_TIMEOUT_SECONDS=30,
        VNPAY_RETURN_URL=RETURN_URL,
    )
    return app


def _prepare_match(app, *, mode=BookingMode.FIND_OPPONENT.value, suffix=""):
    owner = create_user(
        app, email=f"return-owner{suffix}@example.com", role=UserRole.OWNER
    )
    creator = create_user(app, email=f"return-creator{suffix}@example.com")
    player = create_user(app, email=f"return-player{suffix}@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=mode,
        requested_players=2 if mode == BookingMode.FIND_PLAYERS.value else None,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)
    return owner, creator, player, booking_code, match_id


def _join(app, *, match_id, user_id, phone="0901000002"):
    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, user_id),
            contact_phone=phone,
            share_contact=True,
        )
        return participant.id


def _vnpay_pay(app, *, booking_code, contribution_id, payer_id, succeed=True):
    """Run a full VNPAY checkout + IPN and return the callback payload."""
    vnpay = build_vnpay_client()
    with app.app_context():
        checkout = start_vnpay_payment(
            booking_code=booking_code,
            contribution_id=contribution_id,
            payer=db.session.get(User, payer_id),
            return_url=RETURN_URL,
            ip_addr="203.0.113.9",
            client=vnpay,
        )
        payload = vnpay_callback_payload(checkout.payment, vnpay)
        if succeed:
            result = process_vnpay_ipn(payload, client=vnpay)
            assert result.rsp_code == "00"
        return payload


def _return_location(client, payload):
    response = client.get("/payments/vnpay/return", query_string=payload)
    assert response.status_code == 302
    return response.headers["Location"]


# --- The bug: an opponent who paid lands on /bookings ------------------------


def test_vnpay_opponent_success_returns_to_its_match(app, client, vnpay_enabled):
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        payment = db.session.scalar(
            db.select(Payment).where(Payment.contribution_id == contribution_id)
        )
        assert payment.status == PaymentStatus.SUCCESS.value
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert participant.contribution.status == ContributionStatus.PAID.value
        assert participant.contribution.contribution_type == (
            ContributionType.OPPONENT.value
        )

    login(client, email=player.email)
    assert _return_location(client, payload).endswith(f"/matches/{match_id}")


def test_mock_opponent_success_still_reaches_its_match(app, client):
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, player.id),
        )
        assert (
            db.session.get(MatchParticipant, participant_id).status
            == MatchParticipantStatus.JOINED.value
        )

    login(client, email=player.email)
    response = client.get(f"/matches/{match_id}")
    assert response.status_code == 200


def test_vnpay_pending_opponent_return_also_reaches_its_match(app, client, vnpay_enabled):
    """A PENDING return must land on the match too, carrying the watch marker
    so the page can refresh itself once the IPN arrives."""
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
        succeed=False,
    )

    login(client, email=player.email)
    location = _return_location(client, payload)
    assert f"/matches/{match_id}" in location
    assert "payment_watch=" in location


def test_vnpay_creator_success_keeps_its_booking_destination(app, client, vnpay_enabled):
    """The creator deposit is a CREATOR contribution, not a participant one —
    it must keep landing on the booking, not be swept into the match."""
    owner = create_user(app, email="creator-return-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator-return@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)

    from datetime import time

    from app.services import create_booking
    from tests.integration.test_bookings import booking_day

    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        booking_code = booking.booking_code
        contribution_id = next(
            item.id
            for item in booking.contributions
            if item.contribution_type == ContributionType.CREATOR.value
        )

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=creator.id,
    )

    login(client, email=creator.email)
    assert _return_location(client, payload).endswith(f"/bookings/{booking_code}")


def test_unresolvable_relationship_falls_back_safely(app, client, vnpay_enabled):
    """Payment verified, but its booking has no match at all: fall back rather
    than guessing a destination."""
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )

    with app.app_context():
        for message in db.session.scalars(
            db.select(MatchMessage).where(MatchMessage.match_id == match_id)
        ):
            db.session.delete(message)
        db.session.delete(db.session.get(MatchParticipant, participant_id))
        db.session.delete(db.session.get(Match, match_id))
        db.session.commit()

    login(client, email=player.email)
    location = _return_location(client, payload)
    assert f"/matches/{match_id}" not in location
    assert location.endswith("/bookings")


def test_anonymous_return_stays_on_a_first_party_page(app, client, vnpay_enabled):
    """matches.detail is public, so an anonymous return may land there. What
    matters is that the destination is still derived from the verified payment
    and never leaves the site."""
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )

    location = _return_location(client, payload)
    assert location.startswith("/")
    assert "//" not in location
    assert location.endswith(f"/matches/{match_id}")


def test_return_never_leaks_into_another_match(app, client, vnpay_enabled):
    """Same payer, a second booking and match: the destination must follow the
    paid contribution, never merely the user."""
    _, _, player, booking_code, match_id = _prepare_match(app, suffix="-a")
    other_owner = create_user(
        app, email="return-owner-b@example.com", role=UserRole.OWNER
    )
    _, other_field_id = create_bookable_field(app, owner_id=other_owner.id)
    other_booking = _create_split_booking(
        app,
        creator_id=player.id,
        field_id=other_field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    other_match_id = _create_match(
        app, booking_code=other_booking, creator_id=player.id
    )

    participant_id = _join(app, match_id=match_id, user_id=player.id)
    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )

    login(client, email=player.email)
    location = _return_location(client, payload)
    assert location.endswith(f"/matches/{match_id}")
    assert f"/matches/{other_match_id}" not in location


def test_tampered_callback_cannot_steer_the_redirect(app, client, vnpay_enabled):
    """Injecting a destination into the callback both fails the signature check
    and is ignored as a destination: the payer falls back safely instead."""
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )
    payload["next"] = "https://evil.test/steal"
    payload["vnp_ReturnUrl"] = "https://evil.test/steal"

    login(client, email=player.email)
    location = _return_location(client, payload)
    assert "evil.test" not in location
    assert location.startswith("/")
    assert location.endswith("/bookings")
def test_return_survives_a_drifted_participant_row(app, client, vnpay_enabled):
    """The exact behaviour the patch changes.

    The destination used to be keyed on a MatchParticipant row matching
    (contribution_id, payer_id). That row adds no authorization — the payment
    is already verified and matches.booking_id is unique — but it can drift
    away from the payment, and when it did the payer silently fell through to
    /bookings. Resolving from the payment's own booking keeps them on the match
    that payment actually belongs to.
    """
    _, _, player, booking_code, match_id = _prepare_match(app)
    participant_id = _join(app, match_id=match_id, user_id=player.id)

    with app.app_context():
        contribution_id = db.session.get(
            MatchParticipant, participant_id
        ).contribution_id

    payload = _vnpay_pay(
        app,
        booking_code=booking_code,
        contribution_id=contribution_id,
        payer_id=player.id,
    )

    with app.app_context():
        db.session.delete(db.session.get(MatchParticipant, participant_id))
        db.session.commit()
        assert db.session.get(Match, match_id) is not None

    login(client, email=player.email)
    assert _return_location(client, payload).endswith(f"/matches/{match_id}")
