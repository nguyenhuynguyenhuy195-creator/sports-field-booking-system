from datetime import datetime, time, timedelta, timezone

import pytest

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingStatus,
    ContributionStatus,
    FieldTypeCode,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchStatus,
    User,
    UserRole,
    Venue,
    Ward,
)
from app.services import (
    DuplicateMatchRequestError,
    InvalidMatchStateError,
    MatchmakingError,
    create_booking,
    create_match,
    complete_finished_bookings,
    decide_match_request,
    expire_stale_match_participants,
    list_open_matches,
    pay_contribution_with_mock,
    request_to_join_match,
)
from tests.integration.test_bookings import (
    booking_day,
    create_bookable_field,
    create_user,
    login,
)


def _create_split_booking(
    app,
    *,
    creator_id: int,
    field_id: int,
    booking_mode: str,
    requested_players: int | None = None,
) -> str:
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator_id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=booking_mode,
            requested_players=requested_players,
        )
        creator_contribution = next(
            contribution
            for contribution in booking.contributions
            if contribution.user_id == creator_id
        )
        pay_contribution_with_mock(
            booking_code=booking.booking_code,
            contribution_id=creator_contribution.id,
            payer=db.session.get(User, creator_id),
        )
        return booking.booking_code


def _create_match(
    app,
    *,
    booking_code: str,
    creator_id: int,
) -> int:
    with app.app_context():
        match = create_match(
            booking_code=booking_code,
            creator=db.session.get(User, creator_id),
            title="Kèo giao hữu cuối tuần",
            description="Chơi vui, đúng giờ.",
            skill_level="INTERMEDIATE",
            contact_phone="0901000001",
            share_contact=True,
        )
        return match.id


def test_empty_match_list_guides_user_to_booking_flow(app, client):
    player = create_user(app, email="player@example.com")
    login(client, email=player.email)

    response = client.get("/matches")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Chưa có kèo đang mở" in html
    assert 'href="/venues"' in html
    assert 'href="/matches/mine"' in html
    assert ">Lịch sân</a>" in html
    assert ">Kèo của tôi</a>" in html


def test_match_discovery_filters_sport_structured_location_date_and_type(
    app,
    client,
):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    football_venue_id, football_field_id = create_bookable_field(
        app,
        owner_id=owner.id,
    )
    badminton_venue_id, badminton_field_id = create_bookable_field(
        app,
        owner_id=owner.id,
        field_type_code=FieldTypeCode.BADMINTON_STANDARD,
    )

    football_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=football_field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    badminton_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=badminton_field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=2,
    )
    football_match_id = _create_match(
        app,
        booking_code=football_code,
        creator_id=creator.id,
    )
    badminton_match_id = _create_match(
        app,
        booking_code=badminton_code,
        creator_id=creator.id,
    )

    with app.app_context():
        wards = list(db.session.scalars(db.select(Ward).order_by(Ward.code).limit(2)))
        football_venue = db.session.get(Venue, football_venue_id)
        badminton_venue = db.session.get(Venue, badminton_venue_id)
        for venue, ward in zip((football_venue, badminton_venue), wards, strict=True):
            venue.province_code = ward.province_code
            venue.province_name = ward.province.name
            venue.ward_code = ward.code
            venue.ward_name = ward.name
        db.session.get(Match, football_match_id).title = "Kèo bóng đá cần đối thủ"
        db.session.get(Match, badminton_match_id).title = "Kèo cầu lông cần người"
        badminton_province_code = badminton_venue.province_code
        badminton_ward_code = badminton_venue.ward_code
        canonical_extra_ward = db.session.scalar(
            db.select(Ward)
            .where(
                Ward.province_code == badminton_province_code,
                Ward.code.not_in([ward.code for ward in wards]),
            )
            .order_by(Ward.code)
        )
        canonical_extra_ward_name = canonical_extra_ward.full_name
        db.session.commit()

    response = client.get(
        "/matches",
        query_string={
            "sport": "BADMINTON",
            "province_code": badminton_province_code,
            "ward_code": badminton_ward_code,
            "play_date": booking_day().isoformat(),
            "match_type": "FIND_PLAYERS",
        },
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "1 kèo phù hợp" in html
    assert "Kèo cầu lông cần người" in html
    assert "Kèo bóng đá cần đối thủ" not in html
    assert 'id="sport"' not in html
    assert "match-sport-chip is-active" in html
    assert '<input type="hidden" name="sport" value="BADMINTON">' in html
    assert f'<option selected value="{badminton_province_code}">' in html
    assert f'<option selected value="{badminton_ward_code}">' in html
    assert canonical_extra_ward_name in html
    assert '<option selected value="FIND_PLAYERS">' in html
    assert f"province_code={badminton_province_code}" in html
    assert f"ward_code={badminton_ward_code}" in html
    assert "Xóa bộ lọc" in html


def test_match_discovery_ward_options_depend_on_canonical_province(app, client):
    with app.app_context():
        province_code = "01"
        province_wards = list(
            db.session.scalars(
                db.select(Ward)
                .where(Ward.province_code == province_code)
                .order_by(Ward.code)
            )
        )
        expected_ward_name = province_wards[-1].full_name

    no_province_page = client.get("/matches").get_data(as_text=True)
    province_page = client.get(
        "/matches",
        query_string={"province_code": province_code},
    ).get_data(as_text=True)

    assert 'disabled id="ward_code" name="ward_code"' in no_province_page
    assert expected_ward_name not in no_province_page
    assert expected_ward_name in province_page
    assert 'data-wards-url="/api/administrative-units/wards"' in province_page


def test_match_discovery_rejects_invalid_filter_values(app, client):
    response = client.get("/matches?match_type=NOT_A_MATCH_TYPE")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bộ lọc chưa hợp lệ" in html
    assert "Lựa chọn không hợp lệ." in html


def test_match_discovery_paginates_and_sorts_newest(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")

    for index in range(1, 12):
        _, field_id = create_bookable_field(app, owner_id=owner.id)
        booking_code = _create_split_booking(
            app,
            creator_id=creator.id,
            field_id=field_id,
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        match_id = _create_match(
            app,
            booking_code=booking_code,
            creator_id=creator.id,
        )
        with app.app_context():
            match = db.session.get(Match, match_id)
            match.title = f"Kèo phân trang {index:02d}"
            match.created_at = datetime(2026, 1, 1, index, 0, tzinfo=timezone.utc)
            db.session.commit()

    first_page = client.get("/matches?sort=newest")
    second_page = client.get("/matches?sort=newest&page=2")

    assert first_page.status_code == 200
    first_html = first_page.get_data(as_text=True)
    assert "11 kèo phù hợp" in first_html
    assert first_html.count('class="match-market-card marketplace-card"') == 10
    assert first_html.index("Kèo phân trang 11") < first_html.index("Kèo phân trang 10")
    assert "Trang 1/2" in first_html
    assert "sort=newest&amp;page=2" in first_html
    assert 'data-match-sort=""' in first_html
    assert 'class="bi bi-arrow-down-up match-sort-icon"' in first_html
    assert "match-sort-prefix" not in first_html
    assert "Áp dụng sắp xếp" not in first_html

    assert second_page.status_code == 200
    second_html = second_page.get_data(as_text=True)
    assert second_html.count('class="match-market-card marketplace-card"') == 1
    assert "Kèo phân trang 01" in second_html
    assert "Trang 2/2" in second_html


def test_opponent_request_payment_confirms_match_and_booking(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            message="Đội mình nhận kèo này.",
            contact_phone="0901000002",
            share_contact=True,
        )
        assert participant.status == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        assert participant.payment_due_at is not None
        assert participant.contribution.user_id == opponent.id

        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id),
        )
        db.session.refresh(participant)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert participant.status == MatchParticipantStatus.JOINED.value
        assert db.session.get(Match, match_id).status == MatchStatus.CONFIRMED.value
        assert booking.status == BookingStatus.PAID.value
        assert booking.paid_amount == booking.deposit_amount


def test_opponent_payment_window_is_capped_at_booking_start(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert booking.matchmaking_deadline is None
        assert booking.funding_deadline is None
        booking_start_utc = datetime.combine(
            booking.booking_date,
            booking.start_time,
        ) - timedelta(hours=7)
        accepted_at = booking_start_utc - timedelta(minutes=5)
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
            now=accepted_at,
        )
        assert participant.payment_due_at == booking_start_utc


def test_open_match_disappears_and_pending_request_expires_at_booking_start(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking_start_utc = datetime.combine(
            booking.booking_date,
            booking.start_time,
        ) - timedelta(hours=7)
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
            now=booking_start_utc - timedelta(minutes=1),
        )

        assert match_id in {
            match.id
            for match in list_open_matches(now=booking_start_utc - timedelta(seconds=1))
        }
        assert list_open_matches(now=booking_start_utc) == []
        assert expire_stale_match_participants(now=booking_start_utc) == 1
        assert participant.status == MatchParticipantStatus.EXPIRED.value


def test_partial_booking_without_opponent_completes_after_field_time(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        after_field_time = datetime.combine(
            booking.booking_date,
            booking.end_time,
        ) + timedelta(minutes=1)

        assert complete_finished_bookings(now=after_field_time) == 1
        assert booking.status == BookingStatus.COMPLETED.value
        assert participant.status == MatchParticipantStatus.EXPIRED.value
        assert db.session.get(Match, match_id).status == MatchStatus.COMPLETED.value
        opponent_contribution = db.session.scalar(
            db.select(BookingContribution).where(
                BookingContribution.booking_id == booking.id,
                BookingContribution.user_id.is_(None),
            )
        )
        assert opponent_contribution.status == ContributionStatus.EXPIRED.value


def test_expired_opponent_request_reopens_same_contribution(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    first = create_user(app, email="first@example.com")
    second = create_user(app, email="second@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)
    accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        first_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, first.id),
            contact_phone="0901000002",
            share_contact=True,
            now=accepted_at,
        )
        contribution_id = first_request.contribution_id
        assert expire_stale_match_participants(
            now=accepted_at + timedelta(minutes=16)
        ) == 1
        contribution = db.session.get(BookingContribution, contribution_id)
        assert first_request.status == MatchParticipantStatus.EXPIRED.value
        assert contribution.status == ContributionStatus.PENDING.value
        assert contribution.user_id is None

        second_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, second.id),
            contact_phone="0901000003",
            share_contact=True,
        )
        assert second_request.contribution_id == contribution_id


def test_only_one_opponent_can_hold_the_payment_slot(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    first = create_user(app, email="first@example.com")
    second = create_user(app, email="second@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        first_request = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, first.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        with pytest.raises(InvalidMatchStateError, match="đang được giữ chỗ"):
            request_to_join_match(
                match_id=match_id,
                user=db.session.get(User, second.id),
                contact_phone="0901000003",
                share_contact=True,
            )
        assert (
            first_request.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )


def test_old_pending_opponent_can_continue_without_creator_approval(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        participant = MatchParticipant(
            match_id=match_id,
            user_id=opponent.id,
            participant_type="OPPONENT_REPRESENTATIVE",
            status=MatchParticipantStatus.PENDING.value,
        )
        db.session.add(participant)
        db.session.commit()

        with pytest.raises(InvalidMatchStateError, match="không cần người tạo duyệt"):
            decide_match_request(
                match_id=match_id,
                participant_id=participant.id,
                creator=db.session.get(User, creator.id),
                accept=True,
            )

        continued = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        assert continued.id == participant.id
        assert (
            continued.status
            == MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value
        )
        assert continued.contribution_id is not None


def test_find_players_join_with_zalo_has_no_online_payment(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    players = [
        create_user(app, email=f"player{number}@example.com")
        for number in range(1, 3)
    ]
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=2,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        for index, player in enumerate(players, start=1):
            participant = request_to_join_match(
                match_id=match_id,
                user=db.session.get(User, player.id),
                contact_phone=f"091234560{index}",
                share_contact=True,
            )
            decide_match_request(
                match_id=match_id,
                participant_id=participant.id,
                creator=db.session.get(User, creator.id),
                accept=True,
            )
            assert participant.status == MatchParticipantStatus.JOINED.value
            assert participant.contribution_id is None
            assert participant.payment_due_at is None
            assert participant.contact_phone == f"091234560{index}"

        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        assert db.session.get(Match, match_id).status == MatchStatus.FULL.value
        assert booking.status == BookingStatus.PAID.value
        assert db.session.scalar(db.select(db.func.count(BookingContribution.id))) == 1


def test_find_players_requires_phone_consent_and_rejects_duplicate(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_PLAYERS.value,
        requested_players=2,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        user = db.session.get(User, player.id)
        with pytest.raises(MatchmakingError, match="điện thoại"):
            request_to_join_match(match_id=match_id, user=user)
        request_to_join_match(
            match_id=match_id,
            user=user,
            contact_phone="0912345678",
            share_contact=True,
        )
        with pytest.raises(DuplicateMatchRequestError):
            request_to_join_match(
                match_id=match_id,
                user=user,
                contact_phone="0912345678",
                share_contact=True,
            )


def test_cannot_create_match_before_creator_deposit(app):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    with app.app_context():
        booking = create_booking(
            user=db.session.get(User, creator.id),
            field_id=field_id,
            booking_date=booking_day(),
            start_time=time(18, 0),
            end_time=time(20, 0),
            booking_mode=BookingMode.FIND_OPPONENT.value,
        )
        with pytest.raises(InvalidMatchStateError):
            create_match(
                booking_code=booking.booking_code,
                creator=db.session.get(User, creator.id),
                title="Kèo chưa trả cọc",
                contact_phone="0901000001",
                share_contact=True,
            )


def test_match_pages_show_open_match_and_request_state(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    player = create_user(app, email="player@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    response = client.get("/matches")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Kèo giao hữu cuối tuần" in html
    assert "123 Đường Thể Thao, TP. Hồ Chí Minh" in html

    login(client, email=player.email)
    response = client.post(
        f"/matches/{match_id}/requests",
        data={
            "message": "Đội mình muốn tham gia.",
            "contact_phone": "0901000002",
            "share_contact": "y",
        },
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Đã giữ suất đối thủ trong 15 phút" in page
    assert "không cần chờ người tạo duyệt" in page
    assert "Đội mình muốn tham gia." not in page


def test_paid_opponent_appears_in_match_workspace_and_contacts_stay_private(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        contribution_id = participant.contribution_id

    login(client, email=opponent.email)
    before_payment = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "0901000001" not in before_payment

    with app.app_context():
        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=contribution_id,
            payer=db.session.get(User, opponent.id),
        )

    schedule_response = client.get("/bookings")
    assert schedule_response.status_code == 200
    schedule_page = schedule_response.get_data(as_text=True)
    assert "Kèo tôi đã tham gia" not in schedule_page
    assert "Kèo giao hữu cuối tuần" not in schedule_page
    assert f'href="/matches/{match_id}"' not in schedule_page
    assert "Xem và liên hệ" not in schedule_page

    match_workspace_response = client.get("/matches/mine")
    assert match_workspace_response.status_code == 200
    match_workspace_page = match_workspace_response.get_data(as_text=True)
    assert "Kèo giao hữu cuối tuần" in match_workspace_page
    assert "Đã tham gia" in match_workspace_page
    assert f'href="/matches/{match_id}"' in match_workspace_page
    assert match_workspace_page.count('data-bs-toggle="pill"') == 3
    assert 'id="match-created-tab"' in match_workspace_page
    assert 'id="match-joined-tab"' in match_workspace_page
    assert 'id="match-requests-tab"' in match_workspace_page
    assert 'id="match-created-panel"' in match_workspace_page
    assert 'id="match-joined-panel"' in match_workspace_page
    assert 'id="match-requests-panel"' in match_workspace_page

    opponent_page = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "Liên hệ người đăng kèo" in opponent_page
    assert "0901000001" in opponent_page
    assert "https://zalo.me/0901000001" in opponent_page
    assert "Xác nhận rút và mất cọc?" in opponent_page
    assert "Phần cọc đội bạn đã đóng sẽ không được hoàn" in opponent_page

    client.post("/auth/logout")
    login(client, email=creator.email)
    creator_page = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "0901000002" in creator_page
    assert "https://zalo.me/0901000002" in creator_page

    client.post("/auth/logout")
    public_page = client.get(f"/matches/{match_id}").get_data(as_text=True)
    assert "0901000001" not in public_page
    assert "0901000002" not in public_page


def test_existing_joined_match_can_add_missing_contacts(app, client):
    owner = create_user(app, email="owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="creator@example.com")
    opponent = create_user(app, email="opponent@example.com")
    _, field_id = create_bookable_field(app, owner_id=owner.id)
    booking_code = _create_split_booking(
        app,
        creator_id=creator.id,
        field_id=field_id,
        booking_mode=BookingMode.FIND_OPPONENT.value,
    )
    match_id = _create_match(app, booking_code=booking_code, creator_id=creator.id)

    with app.app_context():
        participant = request_to_join_match(
            match_id=match_id,
            user=db.session.get(User, opponent.id),
            contact_phone="0901000002",
            share_contact=True,
        )
        pay_contribution_with_mock(
            booking_code=booking_code,
            contribution_id=participant.contribution_id,
            payer=db.session.get(User, opponent.id),
        )
        match = db.session.get(Match, match_id)
        match.creator_contact_phone = None
        participant.contact_phone = None
        db.session.commit()

    login(client, email=creator.email)
    response = client.post(
        f"/matches/{match_id}/contact",
        data={
            "contact-contact_phone": "0911111111",
            "contact-share_contact": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Đã lưu số Zalo" in response.get_data(as_text=True)

    client.post("/auth/logout")
    login(client, email=opponent.email)
    response = client.post(
        f"/matches/{match_id}/contact",
        data={
            "contact-contact_phone": "0922222222",
            "contact-share_contact": "y",
        },
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "0911111111" in page
    assert "0922222222" in page

    with app.app_context():
        match = db.session.get(Match, match_id)
        participant = db.session.scalar(
            db.select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == opponent.id,
                MatchParticipant.status == MatchParticipantStatus.JOINED.value,
            )
        )
        assert match.creator_contact_phone == "0911111111"
        assert participant.contact_phone == "0922222222"
