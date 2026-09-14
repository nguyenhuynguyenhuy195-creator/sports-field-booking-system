"""Real DB/service coverage for the USER notification center (offline only)."""
from datetime import datetime, timedelta
import re

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mssql

from app.extensions import db
from app.models import (
    Booking, BookingMode, Match, MatchParticipant, Notification, Payment, Refund,
    User, UserRole,
)
from app.services import (
    cancel_owner_booking, cancel_user_booking, decide_match_request,
    pay_contribution_with_mock, process_vnpay_ipn, request_to_join_match,
    start_vnpay_payment, withdraw_match_request,
)
from app.services import notification as service
from app.services.matchmaking import close_opponent_listing
from tests.integration.test_bookings import create_user, create_bookable_field, login
from tests.integration.test_matchmaking import _create_split_booking, _create_match
from tests.integration.test_refunds import _prepare_joined_opponent
from tests.integration.test_vnpay_payments import (
    create_direct_booking, build_vnpay_client, vnpay_callback_payload,
)


def add(user_id, key="payment_success:1", **overrides):
    values = dict(user_id=user_id, event_key=key, type="payment_success",
                  title="Thanh toán thành công", message="Tiền cọc đã được ghi nhận.",
                  target_url="/bookings/BOOKING-1")
    values.update(overrides)
    return service.create_notification_once(**values)


def rows(kind=None, uid=None):
    query = db.select(Notification)
    if kind:
        query = query.where(Notification.type == kind)
    if uid:
        query = query.where(Notification.user_id == uid)
    return list(db.session.scalars(query.order_by(Notification.id)))


@pytest.fixture()
def users(app):
    return [create_user(app, email=f"notify-{i}@example.com") for i in range(2)]


def test_schema_dedupe_and_sql_server_compilation(app, users):
    with app.app_context():
        first = add(users[0].id)
        duplicate = add(users[0].id)
        other = add(users[1].id)
        assert first.id == duplicate.id != other.id
        assert first.event_key == "payment_success:1"
        assert not first.is_read and first.read_at is None
        assert first.created_at is not None
        info = inspect(db.engine)
        assert info.get_foreign_keys("notifications")[0]["referred_table"] == "users"
        assert info.get_unique_constraints("notifications")[0]["column_names"] == ["user_id", "event_key"]
        assert info.get_indexes("notifications")[0]["column_names"] == ["user_id", "is_read", "created_at"]
        ddl = str(CreateTable(Notification.__table__).compile(dialect=mssql.dialect()))
        assert "DATETIME2" in ddl and "NVARCHAR(500)" in ddl
        for index in Notification.__table__.indexes:
            assert "CREATE INDEX" in str(CreateIndex(index).compile(dialect=mssql.dialect()))
        # DB-level dedupe, independent of the SELECT-first service check.
        db.session.add(Notification(user_id=users[0].id, event_key=first.event_key,
                                    type=first.type, title="a", message="b", target_url="/notifications"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


@pytest.mark.parametrize("target", ["https://evil.test", "http://evil.test", "//evil.test", "javascript:alert(1)",
    "/\\evil.test", "/matches/1\n", "/matches/%2f%2fevil", "/matches/../auth/logout", "/notifications?next=//evil.test", " /notifications", "/admin", None])
def test_target_rejects_unsafe_paths(target):
    with pytest.raises(ValueError):
        service.validate_target_url(target)


@pytest.mark.parametrize("target", ["/notifications", "/matches/4", "/bookings/BK-123", "/bookings"])
def test_target_accepts_internal_paths(target):
    assert service.validate_target_url(target) == target


@pytest.mark.parametrize("overrides", [{"type": "anything"}, {"event_key": ""}, {"title": "x" * 161}, {"message": "x" * 501}])
def test_invalid_notification_rejected(app, users, overrides):
    with app.app_context(), pytest.raises(ValueError):
        add(users[0].id, **overrides)


def test_order_limit_count_scoping_and_read_idempotence(app, users):
    with app.app_context():
        ids = [add(users[0].id, f"payment_success:{i}").id for i in range(7)]
        foreign = add(users[1].id).id
        for i, nid in enumerate(ids):
            db.session.get(Notification, nid).created_at = datetime(2026, 1, 1) + timedelta(minutes=i)
        db.session.commit()
        assert service.count_unread_notifications(users[0].id) == 7
        assert [n["id"] for n in service.list_recent_notifications(users[0].id)] == ids[::-1][:5]
        assert not service.mark_notification_read(users[0].id, foreign)
        assert service.mark_notification_read(users[0].id, ids[0])
        read_at = db.session.get(Notification, ids[0]).read_at
        assert read_at is not None
        service.mark_notification_read(users[0].id, ids[0])
        assert db.session.get(Notification, ids[0]).read_at == read_at
        assert service.count_unread_notifications(users[0].id) == 6
        service.mark_all_notifications_read(users[0].id)
        assert service.count_unread_notifications(users[0].id) == 0
        assert service.count_unread_notifications(users[1].id) == 1


def test_routes_dto_idor_post_only_and_escaped_history(app, client, users):
    with app.app_context():
        own = add(users[0].id, title="<script>alert(1)</script>", message='<img src=x onerror="alert(1)">').id
        foreign = add(users[1].id, message="OTHER USER PRIVATE MESSAGE").id
    login(client, email=users[0].email)
    response = client.get("/notifications/recent?user_id=" + str(users[1].id))
    assert response.headers["Cache-Control"] == "no-store"
    dto = response.json
    assert dto["unread_count"] == 1
    assert set(dto) == {"unread_count", "notifications"}
    assert set(dto["notifications"][0]) == {"id", "type", "title", "message", "target_url", "is_read", "created_at"}
    assert dto["notifications"][0]["id"] == own
    html = client.get("/notifications").text
    assert "&lt;script&gt;" in html and "&lt;img" in html
    assert "OTHER USER PRIVATE MESSAGE" not in html
    assert '<script>alert(1)</script>' not in html
    assert client.get(f"/notifications/{own}/read").status_code == 405
    assert client.get("/notifications/read-all").status_code == 405
    assert client.post(f"/notifications/{foreign}/read", json={}).status_code == 404
    assert client.post("/notifications/999999/read", json={}).status_code == 404
    assert client.post(f"/notifications/{own}/read", json={"user_id": users[1].id}).json == {"ok": True}
    assert client.post("/notifications/read-all", data={"user_id": users[1].id}).status_code == 302
    with app.app_context():
        assert service.count_unread_notifications(users[1].id) == 1


@pytest.mark.parametrize("path,method", [("/notifications", "get"), ("/notifications/recent", "get"),
    ("/notifications/1/read", "post"), ("/notifications/read-all", "post")])
@pytest.mark.parametrize("role", [None, UserRole.OWNER, UserRole.ADMIN])
def test_access_restrictions(app, client, role, path, method):
    if role:
        user = create_user(app, email="role@example.com", role=role)
        login(client, email=user.email)
        with app.app_context():
            assert add(user.id) is None
    response = getattr(client, method)(path)
    assert response.status_code == (403 if role else 302)
    if role is None:
        assert "/auth/login" in response.location


def test_csrf_enforced_for_both_writes(app, client, users):
    with app.app_context():
        nid = add(users[0].id).id
    login(client, email=users[0].email)
    app.config["WTF_CSRF_ENABLED"] = True
    for path in (f"/notifications/{nid}/read", "/notifications/read-all"):
        assert client.post(path, json={}).status_code == 400
        assert client.post(path, json={}, headers={"X-CSRFToken": "wrong"}).status_code == 400
    html = client.get("/notifications").text
    token = re.search(r'name="csrf_token" value="([^"]+)"', html)[1]
    assert client.post(f"/notifications/{nid}/read", json={}, headers={"X-CSRFToken": token}).status_code == 200
    assert client.post("/notifications/read-all", data={"csrf_token": token}).status_code == 302


@pytest.mark.parametrize("role", [None, UserRole.USER, UserRole.OWNER, UserRole.ADMIN])
def test_navbar_and_polling_loaded_only_for_user(app, client, role):
    if role:
        user = create_user(app, email="navbar@example.com", role=role)
        login(client, email=user.email)
    html = client.get("/").text
    enabled = role == UserRole.USER
    assert ('data-notification-center' in html) == enabled
    assert ('js/notifications.js' in html) == enabled
    if enabled:
        assert 'data-notification-count hidden' in html
        assert 'data-notification-items' in html
        assert 'data-csrf-token=' in html
        assert 'bi bi-bell' in html


def test_history_pagination_and_unsafe_stored_target_fallback(app, client, users):
    with app.app_context():
        for i in range(23):
            add(users[0].id, f"payment_success:{i}")
        last = rows()[-1]
        last.target_url = "//evil.test"
        db.session.commit()
        assert service.list_recent_notifications(users[0].id)[0]["target_url"] == "/notifications"
        pagination, entries = service.list_user_notifications(users[0].id, page=2)
        assert pagination.total == 23 and len(entries) == 3
    login(client, email=users[0].email)
    assert client.get("/notifications").text.count('<article ') == 20
    assert client.get("/notifications?page=2").text.count('<article ') == 3
    assert "//evil.test" not in client.get("/notifications").text


def prepare_match(app, mode="FIND_PLAYERS"):
    owner = create_user(app, email="match-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="match-creator@example.com")
    player = create_user(app, email="match-player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    code = _create_split_booking(app, creator_id=creator.id, field_id=field_id,
                                 booking_mode=mode, requested_players=2 if mode == "FIND_PLAYERS" else None)
    mid = _create_match(app, booking_code=code, creator_id=creator.id)
    return owner, creator, player, code, mid


def request_join(mid, uid):
    return request_to_join_match(match_id=mid, user=db.session.get(User, uid),
                                 contact_phone="0901000002", share_contact=True)


@pytest.mark.parametrize("accept", [True, False])
def test_find_players_request_and_decision(app, accept):
    _, creator, player, code, mid = prepare_match(app)
    with app.app_context():
        participant = request_join(mid, player.id)
        note = rows("join_request")[0]
        assert note.user_id == creator.id and note.event_key == f"join_request:{participant.id}"
        assert note.target_url == f"/matches/{mid}"
        decide_match_request(match_id=mid, participant_id=participant.id,
                             creator=db.session.get(User, creator.id), accept=accept)
        kind = "request_accepted" if accept else "request_rejected"
        assert len(rows(kind)) == 1 and rows(kind)[0].user_id == player.id
        if accept:
            assert participant.status == "JOINED" and participant.contribution_id is None
            assert "thanh toán" not in rows(kind)[0].message
        assert not rows("opponent_joined")


def test_opponent_hold_does_not_notify_then_payment_and_withdrawal(app):
    _, creator, player, code, mid = prepare_match(app, "FIND_OPPONENT")
    with app.app_context():
        participant = request_join(mid, player.id)
        assert participant.status == "ACCEPTED_AWAITING_PAYMENT"
        assert not rows("opponent_joined") and not rows("join_request")
        payment = pay_contribution_with_mock(booking_code=code, contribution_id=participant.contribution_id,
                                             payer=db.session.get(User, player.id))
        assert participant.status == "JOINED"
        assert rows("opponent_joined")[0].user_id == creator.id
        assert rows("payment_success", player.id)[0].target_url == f"/matches/{mid}"
        withdraw_match_request(match_id=mid, user=db.session.get(User, player.id))
        assert rows("participant_withdrawn")[0].user_id == creator.id
        assert "không được hoàn lại" in rows("participant_withdrawn")[0].message
        assert not rows("refund_success")
        replacement = create_user(app, email="replacement@example.com")
        joined = request_join(mid, replacement.id)
        assert joined.status == "JOINED"
        assert len(rows("opponent_joined")) == 2


@pytest.mark.parametrize("actor", ["owner", "creator"])
def test_cancellation_and_refund_success_recipients_and_dedupe(app, actor):
    owner, creator, opponent, code, mid, pid = _prepare_joined_opponent(app)
    unrelated = create_user(app, email="unrelated@example.com")
    with app.app_context():
        if actor == "owner":
            booking = cancel_owner_booking(booking_code=code, owner=db.session.get(User, owner.id), reason="Sân bảo trì")
        else:
            booking = cancel_user_booking(booking_code=code, user=db.session.get(User, creator.id))
        assert booking.status == "CANCELLED"
        cancelled = rows("booking_cancelled")
        assert {n.user_id for n in cancelled} == {creator.id, opponent.id}
        assert next(n for n in cancelled if n.user_id == opponent.id).target_url == f"/matches/{mid}"
        refunds = rows("refund_success")
        assert {n.user_id for n in refunds} == ({creator.id, opponent.id} if actor == "owner" else {opponent.id})
        assert not rows(uid=unrelated.id) and not rows(uid=owner.id)
        for refund in db.session.scalars(db.select(Refund)):
            assert refund.status == "SUCCESS"
            service.queue_business_notification("refund_success", refund)
        service.queue_cancellation_notification(booking)
        db.session.commit()
        assert len(rows("refund_success")) == len(refunds)
        assert len(rows("booking_cancelled")) == 2


def test_pending_player_cancellation_and_listing_close(app):
    owner, creator, player, code, mid = prepare_match(app)
    with app.app_context():
        participant = request_join(mid, player.id)
        cancel_owner_booking(booking_code=code, owner=db.session.get(User, owner.id), reason="Đóng sân")
        assert {n.user_id for n in rows("booking_cancelled")} == {creator.id, player.id}
        assert not rows("request_rejected")  # Cancellation is not a creator rejection.


def test_cancellation_excludes_previously_rejected_requester(app):
    owner, creator, rejected, code, mid = prepare_match(app)
    pending = create_user(app, email="still-pending@example.com")
    with app.app_context():
        participant = request_join(mid, rejected.id)
        decide_match_request(match_id=mid, participant_id=participant.id,
                             creator=db.session.get(User, creator.id), accept=False)
        request_join(mid, pending.id)
        cancel_owner_booking(booking_code=code, owner=db.session.get(User, owner.id), reason="Đóng sân")
        assert {n.user_id for n in rows("booking_cancelled")} == {creator.id, pending.id}


def test_close_opponent_listing(app):
    _, creator, player, code, mid = prepare_match(app, "FIND_OPPONENT")
    with app.app_context():
        request_join(mid, player.id)
        close_opponent_listing(match_id=mid, creator=db.session.get(User, creator.id))
        assert {n.user_id for n in rows("match_cancelled")} == {creator.id, player.id}
        assert db.session.get(Match, mid).booking.status != "CANCELLED"


def test_vnpay_success_and_duplicate_ipn(app):
    case = create_direct_booking(app, email_prefix="notification-ipn")
    gateway = build_vnpay_client()
    app.config["VNPAY_ENABLED"] = True
    with app.app_context():
        checkout = start_vnpay_payment(booking_code=case["booking_code"], contribution_id=case["contribution_id"],
            payer=db.session.get(User, case["player_id"]), return_url="https://example.test/return",
            ip_addr="127.0.0.1", client=gateway)
        assert not rows("payment_success")
        payload = vnpay_callback_payload(checkout.payment, gateway)
        process_vnpay_ipn(payload, client=gateway)
        process_vnpay_ipn(payload, client=gateway)
        assert len(rows("payment_success")) == 1
        assert rows()[0].event_key == f"payment_success:{checkout.payment.id}"


def test_business_payment_survives_real_notification_insert_failure(app):
    case = create_direct_booking(app, email_prefix="notification-failure")
    with app.app_context():
        def fail_notification(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO NOTIFICATIONS"):
                raise OperationalError("notification insert unavailable", {}, Exception("test failure"))
        event.listen(db.engine, "before_cursor_execute", fail_notification)
        try:
            payment = pay_contribution_with_mock(booking_code=case["booking_code"],
                contribution_id=case["contribution_id"], payer=db.session.get(User, case["player_id"]))
            pid = payment.id
        finally:
            event.remove(db.engine, "before_cursor_execute", fail_notification)
        db.session.remove()
        assert db.session.get(Payment, pid).status == "SUCCESS"
        assert db.session.get(Booking, case["booking_id"]).paid_amount > 0
        assert not rows()


@pytest.mark.parametrize("accept", [True, False])
def test_notification_failure_does_not_undo_request_decision_or_cancel(app, monkeypatch, accept):
    owner, creator, player, code, mid = prepare_match(app)
    monkeypatch.setattr(service, "create_notification_once", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    with app.app_context():
        participant = request_join(mid, player.id)
        pid = participant.id
        decide_match_request(match_id=mid, participant_id=pid, creator=db.session.get(User, creator.id), accept=accept)
        db.session.expire_all()
        assert db.session.get(MatchParticipant, pid).status == ("JOINED" if accept else "REJECTED")
        cancel_owner_booking(booking_code=code, owner=db.session.get(User, owner.id), reason="Đóng sân")
        db.session.expire_all()
        assert db.session.get(Match, mid).booking.status == "CANCELLED"
        assert all(r.status == "SUCCESS" for r in db.session.scalars(db.select(Refund)))


def test_rollback_discards_events_and_delivery_waits_for_outer_commit(app):
    case = create_direct_booking(app, email_prefix="rollback")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        booking.status = "CANCELLED"
        service.queue_cancellation_notification(booking)
        db.session.rollback()
        db.session.commit()
        assert not rows()
        booking.status = "CANCELLED"
        with db.session.begin_nested():
            service.queue_cancellation_notification(booking)
        # No delivery on a savepoint commit.
        assert not rows()
        db.session.commit()
        assert len(rows("booking_cancelled")) == 1


def test_duplicate_insert_race_returns_existing_row(app, users, monkeypatch):
    with app.app_context():
        existing = add(users[0].id)
        real_scalar = Session.scalar
        missed = False

        def miss_first_select(session, statement, *args, **kwargs):
            nonlocal missed
            if not missed:
                missed = True
                return None  # Another writer inserted after the SELECT snapshot.
            return real_scalar(session, statement, *args, **kwargs)

        monkeypatch.setattr(Session, "scalar", miss_first_select)
        assert add(users[0].id).id == existing.id
        assert len(rows()) == 1


def test_provider_refund_only_notifies_persisted_success(app):
    from app.services import apply_owner_cancellation_refunds, process_pending_vnpay_refunds, reconcile_vnpay_refund_manually
    from tests.integration.test_vnpay_refunds import _pay_direct_booking_via_vnpay, _build_refund_client

    app.config["VNPAY_ENABLED"] = True
    case = _pay_direct_booking_via_vnpay(app, email_prefix="notification-refund")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        apply_owner_cancellation_refunds(booking=booking, reason="Đóng sân")
        db.session.commit()
        refund = db.session.scalar(db.select(Refund))
        assert refund.status == "PENDING" and not rows("refund_success")
        process_pending_vnpay_refunds(booking_id=booking.id,
                                     client=_build_refund_client(transaction_status="05"))
        assert refund.status == "PROCESSING" and not rows("refund_success")
        reconcile_vnpay_refund_manually(refund.id, outcome="SUCCESS", provider_trans_id="TEST-REFUND-CONFIRMED")
        assert len(rows("refund_success")) == 1
        assert rows("refund_success")[0].user_id == case["player_id"]
        service.queue_business_notification("refund_success", refund)
        db.session.commit()
        assert len(rows("refund_success")) == 1


def test_withdrawal_survives_notification_failure(app, monkeypatch):
    _, creator, opponent, code, mid, pid = _prepare_joined_opponent(app)
    monkeypatch.setattr(service, "create_notification_once", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    with app.app_context():
        withdraw_match_request(match_id=mid, user=db.session.get(User, opponent.id))
        db.session.remove()
        participant = db.session.get(MatchParticipant, pid)
        assert participant.status == "WITHDRAWN"
        assert participant.contribution.status == "FORFEITED"


def test_session_close_does_not_replay_queued_event(app):
    case = create_direct_booking(app, email_prefix="close-session")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        booking.status = "CANCELLED"
        service.queue_cancellation_notification(booking)
        db.session.close()
        db.session.commit()
        assert not rows()


def test_cancellation_preparation_never_queries_or_flushes_business_session(app):
    case = create_direct_booking(app, email_prefix="no-preparation-sql")
    with app.app_context():
        booking = db.session.get(Booking, case["booking_id"])
        db.session.expire(booking)

        def reject_sql(*args):
            raise AssertionError("Notification preparation attempted SQL")

        event.listen(db.engine, "before_cursor_execute", reject_sql)
        try:
            service.queue_cancellation_notification(booking)
            # No exception was swallowed: the descriptor was actually queued.
            assert len(db.session.info[service._QUEUE]) == 1
        finally:
            event.remove(db.engine, "before_cursor_execute", reject_sql)
        db.session.rollback()


@pytest.mark.parametrize("operation", ["count", "read_one", "read_all"])
def test_unread_service_predicates_compile_as_sql_server_bit_comparisons(app, users, operation):
    with app.app_context():
        note = add(users[0].id)
        statements = []

        def capture_sql(conn, cursor, statement, parameters, context, executemany):
            if context.compiled is not None:
                statements.append(str(context.compiled.statement.compile(dialect=mssql.dialect())))

        event.listen(db.engine, "before_cursor_execute", capture_sql)
        try:
            if operation == "count":
                assert service.count_unread_notifications(users[0].id) == 1
            elif operation == "read_one":
                assert service.mark_notification_read(users[0].id, note.id)
            else:
                service.mark_all_notifications_read(users[0].id)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture_sql)
        assert any("notifications.is_read = 0" in sql for sql in statements)
        assert all("is_read IS 0" not in sql and "is_read IS 1" not in sql for sql in statements)


def test_notification_migration_downgrade_and_reupgrade():
    from app import create_app
    from flask_migrate import upgrade, downgrade

    application = create_app("testing")
    with application.app_context():
        upgrade(directory="migrations")
        downgrade(directory="migrations", revision="d4b7e1c9a802")
        assert "notifications" not in inspect(db.engine).get_table_names()
        assert "match_messages" in inspect(db.engine).get_table_names()
        upgrade(directory="migrations")
        assert "notifications" in inspect(db.engine).get_table_names()
        db.session.remove()
        db.engine.dispose()
