from datetime import datetime, timedelta, timezone
import re

import pytest

from app.extensions import db
from app.models import (
    Booking, BookingContribution, Match,
    MatchParticipant, Payment, Refund, User, UserRole,
)
from app.services import (
    InvalidMatchStateError, MatchPermissionError, decide_match_request,
    list_open_matches, pay_contribution_with_mock, request_to_join_match,
    withdraw_match_request,
)
from app.services.matchmaking import close_opponent_listing
from tests.integration.test_bookings import create_bookable_field, create_user, login
from tests.integration.test_matchmaking import _create_match, _create_split_booking


def prepare(app, mode="FIND_OPPONENT", joined=False):
    owner = create_user(app, email="owner-fix@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator-fix@example.com")
    player = create_user(app, email="player-fix@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    code = _create_split_booking(
        app, creator_id=creator.id, field_id=field_id, booking_mode=mode,
        requested_players=1 if mode == "FIND_PLAYERS" else None,
    )
    match_id = _create_match(app, booking_code=code, creator_id=creator.id)
    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id, user=db.session.get(User, player.id),
            contact_phone="0901000002", share_contact=True,
        )
        if joined:
            if mode == "FIND_PLAYERS":
                decide_match_request(
                    match_id=match_id, participant_id=participant.id,
                    creator=db.session.get(User, creator.id), accept=True,
                )
            else:
                pay_contribution_with_mock(
                    booking_code=code, contribution_id=participant.contribution_id,
                    payer=db.session.get(User, player.id),
                )
        participant_id = participant.id
    return creator, player, match_id, participant_id


def snapshot(*models):
    return tuple(
        tuple(db.session.execute(db.select(*model.__table__.c).order_by(model.id)).all())
        for model in models
    )


def kickoff(match):
    return datetime.combine(match.booking.booking_date, match.booking.start_time) - timedelta(hours=7)


def test_close_listing_preserves_booking_money_and_expires_unpaid_hold(app, client):
    creator, player, match_id, participant_id = prepare(app)
    legacy_user = create_user(app, email="legacy-pending@example.com")
    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        match = db.session.get(Match, match_id)
        creator_part = next(c for c in match.booking.contributions if c.user_id == creator.id)
        creator_before = tuple(getattr(creator_part, c.name) for c in creator_part.__table__.c)
        financial_before = snapshot(Booking, Payment, Refund)
        # A historical pending request must also stop when the listing closes.
        legacy = MatchParticipant(
            match_id=match_id, user_id=legacy_user.id, participant_type="OPPONENT_REPRESENTATIVE",
            status="PENDING",
        )
        db.session.add(legacy)
        db.session.commit()
        close_opponent_listing(match_id=match_id, creator=db.session.get(User, creator.id))
        assert match.status == "CANCELLED"
        assert participant.status == legacy.status == "EXPIRED"
        assert participant.payment_due_at is None
        assert participant.contribution.status == "PENDING"
        assert participant.contribution.user_id is None
        assert participant.contribution.expires_at is None
        assert snapshot(Booking, Payment, Refund) == financial_before
        assert tuple(getattr(creator_part, c.name) for c in creator_part.__table__.c) == creator_before
        assert match_id not in {m.id for m in list_open_matches()}
        with pytest.raises(InvalidMatchStateError):
            close_opponent_listing(match_id=match_id, creator=db.session.get(User, creator.id))
        with pytest.raises(InvalidMatchStateError):
            request_to_join_match(
                match_id=match_id, user=db.session.get(User, player.id),
                contact_phone="0901000002", share_contact=True,
            )
    login(client, email=creator.email)
    html = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Đã đóng bài tìm đối thủ" in html
    assert "Lịch đặt sân và tiền cọc vẫn được giữ nguyên" in html
    assert f'action="/matches/{match_id}/close"' not in html


@pytest.mark.parametrize("reason", ["other_user", "start", "past", "joined", "players", "completed"])
def test_close_listing_rejects_invalid_actor_or_state(app, reason):
    creator, player, match_id, _ = prepare(
        app, mode="FIND_PLAYERS" if reason == "players" else "FIND_OPPONENT",
        joined=reason == "joined",
    )
    with app.app_context():
        match = db.session.get(Match, match_id)
        if reason == "completed":
            match.status = "COMPLETED"
            db.session.commit()
        before = snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund)
        now = kickoff(match) + timedelta(seconds=reason == "past") if reason in {"start", "past"} else None
        with pytest.raises(MatchPermissionError if reason == "other_user" else InvalidMatchStateError):
            close_opponent_listing(
                match_id=match_id,
                creator=db.session.get(User, player.id if reason == "other_user" else creator.id), now=now,
            )
        assert snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund) == before


def test_close_route_requires_creator_post_and_csrf(app, client):
    creator, player, match_id, _ = prepare(app)
    assert client.get(f"/matches/{match_id}/close").status_code == 405
    assert client.post(f"/matches/{match_id}/close").status_code == 302
    login(client, email=player.email)
    assert client.post(f"/matches/{match_id}/close").status_code == 403
    client.post("/auth/logout")
    login(client, email=creator.email)
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/matches/{match_id}/close").status_code == 400
    html = client.get(f"/matches/{match_id}").get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    result = client.post(f"/matches/{match_id}/close", data={"csrf_token": token}, follow_redirects=True)
    assert result.status_code == 200
    assert "Đã đóng bài tìm đối thủ" in result.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Match, match_id).status == "CANCELLED"


def test_admin_labels_creator_closed_listing_without_cancelling_booking(app, client):
    creator, _, match_id, _ = prepare(app)
    admin = create_user(app, email="admin-fix@example.com", role=UserRole.ADMIN)
    with app.app_context():
        match = db.session.get(Match, match_id)
        booking_code = match.booking.booking_code
        close_opponent_listing(
            match_id=match_id, creator=db.session.get(User, creator.id)
        )

    login(client, email=admin.email)
    list_page = client.get(f"/admin/matches?q={booking_code}").get_data(
        as_text=True
    )
    assert 'status-cancelled">Đã đóng bài tìm đối thủ' in list_page
    for url in (f"/admin/matches/{match_id}", f"/admin/bookings/{booking_code}"):
        page = client.get(url).get_data(as_text=True)
        assert 'status-cancelled">Đã đóng bài tìm đối thủ' in page
        assert "Đã cọc một phần" in page


def test_close_rechecks_payment_committed_by_another_session(app):
    creator, player, match_id, participant_id = prepare(app)
    with app.app_context():
        cached_match = db.session.get(Match, match_id)
        cached_participant = cached_match.participants[0]
        assert cached_participant.status == "ACCEPTED_AWAITING_PAYMENT"
        with app.app_context():
            participant = db.session.get(MatchParticipant, participant_id)
            pay_contribution_with_mock(
                booking_code=participant.match.booking.booking_code,
                contribution_id=participant.contribution_id,
                payer=db.session.get(User, player.id),
            )
        before = snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund)
        with pytest.raises(InvalidMatchStateError):
            close_opponent_listing(
                match_id=match_id, creator=db.session.get(User, creator.id),
            )
        assert cached_participant.status == "JOINED"
        assert cached_match.status == "CONFIRMED"
        assert snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund) == before


@pytest.mark.parametrize("mode", ["FIND_PLAYERS", "FIND_OPPONENT"])
@pytest.mark.parametrize("seconds", [0, 1])
def test_joined_withdrawal_rejected_at_and_after_start(app, mode, seconds):
    _, player, match_id, participant_id = prepare(app, mode=mode, joined=True)
    with app.app_context():
        match = db.session.get(Match, match_id)
        before = snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund)
        with pytest.raises(InvalidMatchStateError, match="đã bắt đầu"):
            withdraw_match_request(
                match_id=match_id, user=db.session.get(User, player.id),
                now=kickoff(match) + timedelta(seconds=seconds),
            )
        assert db.session.get(MatchParticipant, participant_id).status == "JOINED"
        assert snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund) == before


@pytest.mark.parametrize("mode", ["FIND_PLAYERS", "FIND_OPPONENT"])
@pytest.mark.parametrize("seconds", [0, 1])
def test_unresolved_withdrawal_at_start_persists_expiry_not_withdrawal(app, mode, seconds):
    _, player, match_id, participant_id = prepare(app, mode=mode)
    with app.app_context():
        match = db.session.get(Match, match_id)
        before = snapshot(Booking, Payment, Refund)
        with pytest.raises(InvalidMatchStateError, match="đã bắt đầu"):
            withdraw_match_request(
                match_id=match_id, user=db.session.get(User, player.id),
                now=kickoff(match) + timedelta(seconds=seconds),
            )
        db.session.expire_all()
        participant = db.session.get(MatchParticipant, participant_id)
        assert participant.status == "EXPIRED"
        assert participant.payment_due_at is None
        if participant.contribution:
            assert participant.contribution.user_id is None
            assert participant.contribution.expires_at is None
            assert participant.contribution.status == "PENDING"
        assert snapshot(Booking, Payment, Refund) == before


@pytest.mark.parametrize("mode,joined", [("FIND_PLAYERS", False), ("FIND_PLAYERS", True), ("FIND_OPPONENT", False)])
def test_valid_prestart_withdrawal_still_releases_slot_without_money_changes(app, mode, joined):
    _, player, match_id, participant_id = prepare(app, mode=mode, joined=joined)
    with app.app_context():
        match = db.session.get(Match, match_id)
        before = snapshot(Booking, Payment, Refund)
        participant = withdraw_match_request(
            match_id=match_id, user=db.session.get(User, player.id),
            now=kickoff(match) - timedelta(seconds=1),
        )
        assert participant.status == "WITHDRAWN"
        assert match.status == "OPEN"
        assert snapshot(Booking, Payment, Refund) == before


@pytest.mark.parametrize("mode,past", [("FIND_OPPONENT", False), ("FIND_OPPONENT", True), ("FIND_PLAYERS", True)])
def test_user_gets_render_stale_state_without_commit_or_orm_mutation(app, monkeypatch, mode, past):
    client = app.test_client()
    creator, player, match_id, participant_id = prepare(app, mode=mode)
    with app.app_context():
        match = db.session.get(Match, match_id)
        participant = db.session.get(MatchParticipant, participant_id)
        if past:
            match.booking.booking_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        if mode == "FIND_OPPONENT":
            participant.payment_due_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            participant.contribution.expires_at = participant.payment_due_at
        db.session.commit()
        before = snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund)
    login(client, email=player.email)

    def forbidden_commit(*args, **kwargs):
        raise AssertionError("GET must not commit")

    with monkeypatch.context() as guard:
        guard.setattr(db.session.session_factory.class_, "commit", forbidden_commit)
        for _ in range(2):
            with app.app_context():
                detail = client.get(f"/matches/{match_id}")
                mine = client.get("/matches/mine")
                assert detail.status_code == mine.status_code == 200
                html = detail.get_data(as_text=True)
                assert "Yêu cầu tham gia đã hết hạn" in html
                assert "Đã hết hạn thanh toán" in mine.get_data(as_text=True)
                assert "data-payment-submit" not in html
                assert f'action="/matches/{match_id}/requests/withdraw"' not in html
                assert not db.session.dirty
                assert not db.session.new
                assert snapshot(Booking, Match, MatchParticipant, BookingContribution, Payment, Refund) == before
    client.post("/auth/logout")
    login(client, email=creator.email)
    html = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Đã hết hạn thanh toán" in html
    assert f'/requests/{participant_id}/accept' not in html


def test_late_momo_success_after_listing_close_queues_refund_without_joining(app):
    from app.services import process_momo_payment_notification, start_momo_payment
    from tests.integration.test_momo_payments import build_client, payment_notification
    creator, player, match_id, participant_id = prepare(app)
    with app.app_context():
        participant = db.session.get(MatchParticipant, participant_id)
        match = db.session.get(Match, match_id)
        momo = build_client()
        checkout = start_momo_payment(
            booking_code=match.booking.booking_code, contribution_id=participant.contribution_id,
            payer=db.session.get(User, player.id), redirect_url="https://example.test/return",
            ipn_url="https://example.test/ipn", client=momo,
        )
        payload = payment_notification(checkout.payment)
        close_opponent_listing(match_id=match_id, creator=db.session.get(User, creator.id))
        booking_before = snapshot(Booking)
        payment = process_momo_payment_notification(payload, client=momo)
        assert payment.status == "EXPIRED"
        assert participant.status == "EXPIRED"
        assert match.status == "CANCELLED"
        assert snapshot(Booking) == booking_before
        assert db.session.scalar(db.select(Refund)).recipient_id == player.id
