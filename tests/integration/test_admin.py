from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    BookingPaymentPolicy,
    BookingStatus,
    ContributionStatus,
    ContributionType,
    Field,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    Match,
    MatchParticipant,
    MatchParticipantStatus,
    MatchParticipantType,
    MatchStatus,
    MatchType,
    OwnerApplication,
    OwnerApplicationStatus,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Province,
    Refund,
    RefundStatus,
    User,
    UserRole,
    UserStatus,
    Venue,
    VenueStatus,
    Ward,
)
from app.models.user import utc_now
from app.routes.admin import (
    BOOKING_STATUS_LABELS,
    PAYMENT_STATUS_LABELS,
    REFUND_STATUS_LABELS,
)
from app.services import register_user


PASSWORD = "MatKhauAnToan123"


@dataclass(frozen=True)
class CreatedUser:
    id: int
    email: str


def create_user(
    app,
    *,
    email: str,
    role: UserRole = UserRole.USER,
    full_name: str | None = None,
    phone: str = "0901234567",
    status: UserStatus = UserStatus.ACTIVE,
) -> CreatedUser:
    with app.app_context():
        user = register_user(
            full_name=full_name or f"Tài khoản {role.value}",
            email=email,
            phone=phone,
            password=PASSWORD,
        )
        user.role = role.value
        user.status = status.value
        db.session.commit()
        return CreatedUser(id=user.id, email=user.email)


def login(client, *, email: str):
    return client.post(
        "/auth/login",
        data={"email": email, "password": PASSWORD},
    )


def seed_monitoring_data(app, *, user_id: int, owner_id: int) -> str:
    with app.app_context():
        field_type = db.session.scalar(
            db.select(FieldType).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        venue = Venue(
            owner_id=owner_id,
            name="Cơ sở Admin Test",
            address="123 Đường Kiểm Thử",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(23, 0),
            status=VenueStatus.ACTIVE.value,
        )
        db.session.add(venue)
        db.session.flush()
        field = Field(
            venue_id=venue.id,
            name="Sân kiểm thử",
            field_type_id=field_type.id,
            capacity=10,
            status=FieldStatus.ACTIVE.value,
        )
        db.session.add(field)
        db.session.flush()

        booking_code = "BK-ADMIN-MONITOR"
        booking = Booking(
            booking_code=booking_code,
            user_id=user_id,
            field_id=field.id,
            booking_date=date.today() + timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 0),
            booking_mode=BookingMode.FIND_PLAYERS.value,
            play_format=None,
            requested_players=2,
            payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total_amount=Decimal("300000"),
            deposit_rate=Decimal("0.3000"),
            deposit_amount=Decimal("90000"),
            paid_amount=Decimal("80000"),
            cancellation_fee_amount=Decimal("0"),
            status=BookingStatus.PAID.value,
            initial_payment_due_at=utc_now() + timedelta(minutes=15),
        )
        db.session.add(booking)
        db.session.flush()

        contribution = BookingContribution(
            booking_id=booking.id,
            user_id=user_id,
            contribution_type=ContributionType.CREATOR.value,
            amount_due=Decimal("90000"),
            amount_paid=Decimal("80000"),
            status=ContributionStatus.PARTIALLY_REFUNDED.value,
        )
        db.session.add(contribution)
        db.session.flush()

        payment = Payment(
            booking_id=booking.id,
            contribution_id=contribution.id,
            payer_id=user_id,
            provider=PaymentProvider.MOCK.value,
            payment_method=PaymentMethod.SIMULATED.value,
            amount=Decimal("90000"),
            order_id="PAY-ADMIN-MONITOR",
            request_id="REQ-ADMIN-MONITOR",
            provider_trans_id="TRANS-ADMIN-MONITOR",
            status=PaymentStatus.SUCCESS.value,
            result_code="0",
            paid_at=utc_now(),
        )
        db.session.add(payment)
        db.session.flush()

        refund = Refund(
            booking_id=booking.id,
            payment_id=payment.id,
            recipient_id=user_id,
            amount=Decimal("10000"),
            reason="Hoàn tiền kiểm thử hệ thống",
            order_id="REFUND-ADMIN-MONITOR",
            request_id="REFUND-REQ-ADMIN-MONITOR",
            provider_refund_trans_id="REFUND-TRANS-ADMIN-MONITOR",
            status=RefundStatus.SUCCESS.value,
            result_code="0",
            refunded_at=utc_now(),
        )
        db.session.add(refund)

        match = Match(
            creator_id=user_id,
            booking_id=booking.id,
            match_type=MatchType.FIND_PLAYERS.value,
            title="Kèo Admin Test",
            total_players=10,
            required_players=2,
            status=MatchStatus.OPEN.value,
        )
        db.session.add(match)
        db.session.commit()
        return booking_code


def seed_booking_operations_data(app, *, user_id: int, owner_id: int) -> dict:
    """Create financially consistent records dedicated to the Phase 2.1 list."""
    with app.app_context():
        provinces = tuple(
            db.session.scalars(db.select(Province).order_by(Province.code).limit(2))
        )
        first_ward = db.session.scalar(
            db.select(Ward)
            .where(Ward.province_code == provinces[0].code)
            .order_by(Ward.code)
        )
        second_ward = db.session.scalar(
            db.select(Ward)
            .where(Ward.province_code == provinces[1].code)
            .order_by(Ward.code)
        )
        all_field_types = tuple(
            db.session.scalars(db.select(FieldType).order_by(FieldType.id))
        )
        field_types = (
            all_field_types[0],
            next(
                field_type
                for field_type in all_field_types[1:]
                if field_type.sport_id != all_field_types[0].sport_id
            ),
        )
        venues = (
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops A",
                address="1 Đường Vận Hành",
                province_code=provinces[0].code,
                province_name=provinces[0].name,
                ward_code=first_ward.code,
                ward_name=first_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops B",
                address="2 Đường Vận Hành",
                province_code=provinces[1].code,
                province_name=provinces[1].name,
                ward_code=second_ward.code,
                ward_name=second_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
            Venue(
                owner_id=owner_id,
                name="Cơ sở Booking Ops Legacy",
                address="3 Đường Vận Hành",
                province_name=provinces[0].name,
                ward_name=first_ward.full_name,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            ),
        )
        db.session.add_all(venues)
        db.session.flush()
        fields = (
            Field(
                venue_id=venues[0].id,
                name="Sân Booking Ops A",
                field_type_id=field_types[0].id,
                capacity=10,
                status=FieldStatus.ACTIVE.value,
            ),
            Field(
                venue_id=venues[1].id,
                name="Sân Booking Ops B",
                field_type_id=field_types[1].id,
                capacity=4,
                status=FieldStatus.ACTIVE.value,
            ),
            Field(
                venue_id=venues[2].id,
                name="Sân Booking Ops Legacy",
                field_type_id=field_types[0].id,
                capacity=10,
                status=FieldStatus.ACTIVE.value,
            ),
        )
        db.session.add_all(fields)
        db.session.flush()

        scheduled_date = date.today() + timedelta(days=7)

        def add_booking(
            code,
            *,
            field=fields[0],
            mode=BookingMode.DIRECT_BOOKING.value,
            policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total=Decimal("180000"),
            deposit=Decimal("54000"),
            paid=Decimal("0"),
            status=BookingStatus.CONFIRMED.value,
        ):
            booking = Booking(
                booking_code=code,
                user_id=user_id,
                field_id=field.id,
                booking_date=scheduled_date,
                start_time=time(18, 0),
                end_time=time(19, 0),
                booking_mode=mode,
                payment_policy=policy,
                total_amount=total,
                deposit_rate=(
                    Decimal("1.0000")
                    if policy == BookingPaymentPolicy.LEGACY_FULL_ONLINE.value
                    else Decimal("0.3000")
                ),
                deposit_amount=deposit,
                paid_amount=paid,
                cancellation_fee_amount=Decimal("0"),
                status=status,
            )
            db.session.add(booking)
            db.session.flush()
            return booking

        def add_payment(booking, status, suffix, *, amount=None):
            contribution = BookingContribution(
                booking_id=booking.id,
                user_id=user_id,
                contribution_type=ContributionType.CREATOR.value,
                amount_due=booking.deposit_amount,
                amount_paid=booking.paid_amount,
                status=(
                    ContributionStatus.PAID.value
                    if booking.paid_amount >= booking.deposit_amount
                    else ContributionStatus.PENDING.value
                ),
            )
            db.session.add(contribution)
            db.session.flush()
            payment = Payment(
                booking_id=booking.id,
                contribution_id=contribution.id,
                payer_id=user_id,
                provider=PaymentProvider.MOCK.value,
                payment_method=PaymentMethod.SIMULATED.value,
                amount=amount or booking.deposit_amount,
                order_id=f"PAY-OPS-{suffix}",
                request_id=f"REQ-OPS-{suffix}",
                status=status,
                paid_at=utc_now() if status == PaymentStatus.SUCCESS.value else None,
            )
            db.session.add(payment)
            db.session.flush()
            return payment

        main = add_booking(
            "BK-OPS-MAIN",
            paid=Decimal("40000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        main_payment = add_payment(
            main,
            PaymentStatus.SUCCESS.value,
            "SEARCH-TARGET",
            amount=Decimal("54000"),
        )
        db.session.add(
            Refund(
                booking_id=main.id,
                payment_id=main_payment.id,
                recipient_id=user_id,
                amount=Decimal("14000"),
                reason="Hoàn một phần hợp lệ",
                order_id="REFUND-OPS-SEARCH-TARGET",
                request_id="REFUND-REQ-OPS-SEARCH-TARGET",
                status=RefundStatus.SUCCESS.value,
                refunded_at=utc_now(),
            )
        )

        opponent = add_booking(
            "BK-OPS-OPPONENT",
            mode=BookingMode.FIND_OPPONENT.value,
            total=Decimal("300000"),
            deposit=Decimal("90000"),
            paid=Decimal("45000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        add_payment(
            opponent,
            PaymentStatus.SUCCESS.value,
            "OPPONENT",
            amount=Decimal("45000"),
        )

        legacy = add_booking(
            "BK-OPS-LEGACY",
            field=fields[1],
            policy=BookingPaymentPolicy.LEGACY_FULL_ONLINE.value,
            total=Decimal("200000"),
            deposit=Decimal("200000"),
            paid=Decimal("200000"),
            status=BookingStatus.PAID.value,
        )
        add_payment(legacy, PaymentStatus.SUCCESS.value, "LEGACY")

        legacy_location = add_booking("BK-OPS-LEGACY-LOCATION", field=fields[2])

        payment_attention_codes = {}
        for payment_status in (
            PaymentStatus.PENDING.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.CANCELLED.value,
            PaymentStatus.EXPIRED.value,
        ):
            booking = add_booking(f"BK-OPS-PAY-{payment_status}")
            add_payment(booking, payment_status, payment_status)
            payment_attention_codes[payment_status] = booking.booking_code

        refund_attention_codes = {}
        for refund_status in (
            RefundStatus.PENDING.value,
            RefundStatus.PROCESSING.value,
            RefundStatus.FAILED.value,
        ):
            booking = add_booking(
                f"BK-OPS-REF-{refund_status}",
                paid=Decimal("54000"),
                status=BookingStatus.PAID.value,
            )
            payment = add_payment(
                booking,
                PaymentStatus.SUCCESS.value,
                f"REF-{refund_status}",
            )
            db.session.add(
                Refund(
                    booking_id=booking.id,
                    payment_id=payment.id,
                    recipient_id=user_id,
                    amount=Decimal("10000"),
                    reason="Theo dõi hoàn tiền",
                    order_id=f"REFUND-OPS-{refund_status}",
                    request_id=f"REFUND-REQ-OPS-{refund_status}",
                    status=refund_status,
                )
            )
            refund_attention_codes[refund_status] = booking.booking_code

        combined = add_booking(
            "BK-OPS-COMBINED",
            paid=Decimal("54000"),
            status=BookingStatus.REFUND_PENDING.value,
        )
        combined_payment = add_payment(
            combined,
            PaymentStatus.SUCCESS.value,
            "COMBINED-SUCCESS",
        )
        add_payment(combined, PaymentStatus.FAILED.value, "COMBINED-FAILED")
        db.session.add(
            Refund(
                booking_id=combined.id,
                payment_id=combined_payment.id,
                recipient_id=user_id,
                amount=Decimal("10000"),
                reason="Theo dõi kết hợp",
                order_id="REFUND-OPS-COMBINED",
                request_id="REFUND-REQ-OPS-COMBINED",
                status=RefundStatus.PENDING.value,
            )
        )

        db.session.commit()
        return {
            "main": main.booking_code,
            "opponent": opponent.booking_code,
            "legacy": legacy.booking_code,
            "legacy_location": legacy_location.booking_code,
            "scheduled_date": scheduled_date.isoformat(),
            "province_code": provinces[0].code,
            "province_name": provinces[0].name,
            "ward_code": first_ward.code,
            "ward_name": first_ward.full_name,
            "other_province_code": provinces[1].code,
            "venue_id": venues[0].id,
            "field_id": fields[0].id,
            "sport_code": field_types[0].sport.code,
            "other_sport_code": field_types[1].sport.code,
            "other_venue_id": venues[1].id,
            "other_field_id": fields[1].id,
            "customer_email": db.session.get(User, user_id).email,
            "customer_name": db.session.get(User, user_id).full_name,
            "payment_attention_codes": payment_attention_codes,
            "refund_attention_codes": refund_attention_codes,
            "combined": combined.booking_code,
        }


def seed_match_operations_data(
    app,
    *,
    creator_id: int,
    owner_id: int,
    participant_ids: tuple[int, ...],
) -> dict:
    """Create varied read-only records for the dedicated Match module."""
    booking_data = seed_booking_operations_data(
        app,
        user_id=creator_id,
        owner_id=owner_id,
    )
    with app.app_context():
        primary_field = db.session.get(Field, booking_data["field_id"])
        other_field = db.session.get(Field, booking_data["other_field_id"])
        legacy_booking = db.session.scalar(
            db.select(Booking).where(
                Booking.booking_code == booking_data["legacy_location"]
            )
        )
        legacy_field = legacy_booking.field
        scheduled_date = date.today() + timedelta(days=9)
        recorded_at = datetime(2026, 9, 4, 8, 0)

        def add_match(
            suffix,
            *,
            field,
            match_type=MatchType.FIND_PLAYERS.value,
            match_status=MatchStatus.OPEN.value,
            paid=Decimal("90000"),
            booking_status=BookingStatus.PAID.value,
            title=None,
            created_offset=0,
        ):
            booking = Booking(
                booking_code=f"BK-MATCH-OPS-{suffix}",
                user_id=creator_id,
                field_id=field.id,
                booking_date=scheduled_date,
                start_time=time(18, 0),
                end_time=time(19, 0),
                booking_mode=match_type,
                requested_players=(
                    2 if match_type == MatchType.FIND_PLAYERS.value else None
                ),
                payment_policy=BookingPaymentPolicy.DEPOSIT_30.value,
                total_amount=Decimal("300000"),
                deposit_rate=Decimal("0.3000"),
                deposit_amount=Decimal("90000"),
                paid_amount=paid,
                cancellation_fee_amount=Decimal("0"),
                status=booking_status,
                created_at=recorded_at + timedelta(minutes=created_offset),
            )
            db.session.add(booking)
            db.session.flush()
            match = Match(
                creator_id=creator_id,
                booking_id=booking.id,
                match_type=match_type,
                title=title or f"Kèo vận hành {suffix}",
                total_players=(
                    10 if match_type == MatchType.FIND_PLAYERS.value else None
                ),
                required_players=(
                    2 if match_type == MatchType.FIND_PLAYERS.value else 1
                ),
                status=match_status,
                created_at=recorded_at + timedelta(minutes=created_offset),
            )
            db.session.add(match)
            db.session.flush()
            return booking, match

        players_booking, players_match = add_match(
            "PLAYERS",
            field=primary_field,
            title="Kèo cầu lông Alpha",
            created_offset=1,
        )
        player_states = (
            MatchParticipantStatus.PENDING.value,
            MatchParticipantStatus.JOINED.value,
            MatchParticipantStatus.REJECTED.value,
            MatchParticipantStatus.WITHDRAWN.value,
        )
        for index, participant_status in enumerate(player_states):
            db.session.add(
                MatchParticipant(
                    match_id=players_match.id,
                    user_id=participant_ids[index],
                    participant_type=MatchParticipantType.PLAYER.value,
                    status=participant_status,
                    created_at=recorded_at + timedelta(minutes=10 + index),
                    decided_at=(
                        None
                        if participant_status == MatchParticipantStatus.PENDING.value
                        else recorded_at + timedelta(minutes=20 + index)
                    ),
                )
            )

        awaiting_booking, awaiting_match = add_match(
            "OPPONENT-AWAITING",
            field=primary_field,
            match_type=MatchType.FIND_OPPONENT.value,
            paid=Decimal("45000"),
            booking_status=BookingStatus.PARTIALLY_PAID.value,
            title="Kèo đối thủ chờ cọc",
            created_offset=2,
        )
        awaiting_contribution = BookingContribution(
            booking_id=awaiting_booking.id,
            user_id=participant_ids[0],
            contribution_type=ContributionType.OPPONENT.value,
            slot_number=1,
            amount_due=Decimal("45000"),
            amount_paid=Decimal("0"),
            status=ContributionStatus.PENDING.value,
            created_at=recorded_at + timedelta(minutes=30),
        )
        db.session.add(awaiting_contribution)
        db.session.flush()
        awaiting_participant = MatchParticipant(
            match_id=awaiting_match.id,
            user_id=participant_ids[0],
            contribution_id=awaiting_contribution.id,
            participant_type=MatchParticipantType.OPPONENT_REPRESENTATIVE.value,
            status=MatchParticipantStatus.ACCEPTED_AWAITING_PAYMENT.value,
            payment_due_at=recorded_at + timedelta(minutes=45),
            created_at=recorded_at + timedelta(minutes=31),
            decided_at=recorded_at + timedelta(minutes=31),
        )
        db.session.add(awaiting_participant)

        joined_booking, joined_match = add_match(
            "OPPONENT-JOINED",
            field=primary_field,
            match_type=MatchType.FIND_OPPONENT.value,
            match_status=MatchStatus.CONFIRMED.value,
            title="Kèo đối thủ đã nhận",
            created_offset=3,
        )
        joined_contribution = BookingContribution(
            booking_id=joined_booking.id,
            user_id=participant_ids[1],
            contribution_type=ContributionType.OPPONENT.value,
            slot_number=1,
            amount_due=Decimal("45000"),
            amount_paid=Decimal("45000"),
            status=ContributionStatus.PAID.value,
            created_at=recorded_at + timedelta(minutes=40),
        )
        db.session.add(joined_contribution)
        db.session.flush()
        db.session.add(
            MatchParticipant(
                match_id=joined_match.id,
                user_id=participant_ids[1],
                contribution_id=joined_contribution.id,
                participant_type=(
                    MatchParticipantType.OPPONENT_REPRESENTATIVE.value
                ),
                status=MatchParticipantStatus.JOINED.value,
                created_at=recorded_at + timedelta(minutes=41),
                decided_at=recorded_at + timedelta(minutes=42),
            )
        )

        completed_booking, completed_match = add_match(
            "COMPLETED",
            field=other_field,
            match_status=MatchStatus.COMPLETED.value,
            booking_status=BookingStatus.COMPLETED.value,
            created_offset=4,
        )
        completed_booking.updated_at = recorded_at + timedelta(hours=5)
        completed_match.updated_at = recorded_at + timedelta(hours=5)

        cancelled_booking, cancelled_match = add_match(
            "CANCELLED",
            field=other_field,
            match_status=MatchStatus.CANCELLED.value,
            booking_status=BookingStatus.CANCELLED.value,
            created_offset=5,
        )
        cancelled_booking.cancellation_reason = "Chủ sân hủy lịch kiểm thử"
        cancelled_match.updated_at = recorded_at + timedelta(hours=6)

        _, full_match = add_match(
            "FULL",
            field=primary_field,
            match_status=MatchStatus.FULL.value,
            created_offset=6,
        )
        _, legacy_location_match = add_match(
            "LEGACY-LOCATION",
            field=legacy_field,
            created_offset=7,
        )
        past_open_booking, past_open_match = add_match(
            "PAST-OPEN",
            field=primary_field,
            title="Kèo đã qua giờ nhưng còn mở trong dữ liệu",
            created_offset=8,
        )
        past_open_booking.booking_date = date.today() - timedelta(days=1)

        db.session.commit()
        return {
            **booking_data,
            "scheduled_date": scheduled_date.isoformat(),
            "players_match_id": players_match.id,
            "players_booking_code": players_booking.booking_code,
            "awaiting_match_id": awaiting_match.id,
            "awaiting_booking_code": awaiting_booking.booking_code,
            "joined_match_id": joined_match.id,
            "joined_booking_code": joined_booking.booking_code,
            "completed_match_id": completed_match.id,
            "cancelled_match_id": cancelled_match.id,
            "full_match_id": full_match.id,
            "legacy_location_match_id": legacy_location_match.id,
            "past_open_match_id": past_open_match.id,
            "past_open_booking_code": past_open_booking.booking_code,
        }


def setup_admin_match_operations(app, client, token: str) -> dict:
    admin = create_user(
        app,
        email=f"match-{token}-admin@example.com",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        app,
        email=f"match-{token}-owner@example.com",
        role=UserRole.OWNER,
    )
    creator = create_user(
        app,
        email=f"match-{token}-creator@example.com",
        full_name="Nguyễn Người Tạo Kèo",
    )
    participants = tuple(
        create_user(
            app,
            email=f"match-{token}-participant-{index}@example.com",
            full_name=f"Người tham gia {index}",
        )
        for index in range(4)
    )
    data = seed_match_operations_data(
        app,
        creator_id=creator.id,
        owner_id=owner.id,
        participant_ids=tuple(participant.id for participant in participants),
    )
    login(client, email=admin.email)
    data["creator_name"] = "Nguyễn Người Tạo Kèo"
    data["creator_email"] = creator.email
    data["participant_emails"] = tuple(
        participant.email for participant in participants
    )
    return data


def seed_booking_detail_data(app, *, user_id: int, owner_id: int) -> dict:
    list_data = seed_booking_operations_data(
        app,
        user_id=user_id,
        owner_id=owner_id,
    )
    with app.app_context():
        field = db.session.get(Field, list_data["field_id"])
        occurred_at = datetime(2026, 9, 3, 8, 0)
        scheduled_date = date(2030, 1, 15)

        def add_booking(
            code: str,
            *,
            mode=BookingMode.DIRECT_BOOKING.value,
            policy=BookingPaymentPolicy.DEPOSIT_30.value,
            total=Decimal("180000"),
            deposit=Decimal("54000"),
            paid=Decimal("0"),
            status=BookingStatus.CONFIRMED.value,
            cancellation_reason=None,
        ):
            booking = Booking(
                booking_code=code,
                user_id=user_id,
                field_id=field.id,
                booking_date=scheduled_date,
                start_time=time(18, 0),
                end_time=time(19, 0),
                booking_mode=mode,
                payment_policy=policy,
                total_amount=total,
                deposit_rate=(
                    Decimal("1.0000")
                    if policy == BookingPaymentPolicy.LEGACY_FULL_ONLINE.value
                    else Decimal("0.3000")
                ),
                deposit_amount=deposit,
                paid_amount=paid,
                cancellation_fee_amount=Decimal("0"),
                status=status,
                cancellation_reason=cancellation_reason,
                created_at=occurred_at,
            )
            db.session.add(booking)
            db.session.flush()
            return booking

        def add_contribution(
            booking,
            *,
            due,
            paid,
            status,
            contribution_type=ContributionType.CREATOR.value,
            slot_number=None,
            user=user_id,
        ):
            contribution = BookingContribution(
                booking_id=booking.id,
                user_id=user,
                contribution_type=contribution_type,
                slot_number=slot_number,
                amount_due=due,
                amount_paid=paid,
                status=status,
                created_at=occurred_at,
            )
            db.session.add(contribution)
            db.session.flush()
            return contribution

        def add_payment(
            booking,
            contribution,
            *,
            amount,
            token,
            paid_at,
        ):
            payment = Payment(
                booking_id=booking.id,
                contribution_id=contribution.id,
                payer_id=user_id,
                provider=PaymentProvider.MOMO.value,
                payment_method=PaymentMethod.MOMO_WALLET.value,
                amount=amount,
                order_id=f"ORDER-{token}",
                request_id=f"REQUEST-{token}",
                provider_trans_id=f"TRANS-{token}",
                status=PaymentStatus.SUCCESS.value,
                result_code="0",
                paid_at=paid_at,
                created_at=occurred_at,
            )
            db.session.add(payment)
            db.session.flush()
            return payment

        def add_refund(
            booking,
            payment,
            *,
            amount,
            token,
            status,
            refunded_at=None,
        ):
            refund = Refund(
                booking_id=booking.id,
                payment_id=payment.id,
                recipient_id=user_id,
                amount=amount,
                reason=f"Hoàn tiền {token}",
                order_id=f"REFUND-{token}",
                request_id=f"REFUND-REQUEST-{token}",
                provider_refund_trans_id=(
                    f"REFUND-TRANS-{token}"
                    if status == RefundStatus.SUCCESS.value
                    else None
                ),
                status=status,
                result_code="0" if status == RefundStatus.SUCCESS.value else None,
                refunded_at=refunded_at,
                created_at=occurred_at,
            )
            db.session.add(refund)
            db.session.flush()
            return refund

        normal = add_booking(
            "BK-DETAIL-DEPOSIT",
            paid=Decimal("54000"),
            status=BookingStatus.PAID.value,
        )
        normal_contribution = add_contribution(
            normal,
            due=Decimal("54000"),
            paid=Decimal("54000"),
            status=ContributionStatus.PAID.value,
        )
        normal_payment = add_payment(
            normal,
            normal_contribution,
            amount=Decimal("54000"),
            token="DETAIL-NORMAL",
            paid_at=occurred_at + timedelta(hours=1),
        )

        legacy = add_booking(
            "BK-DETAIL-LEGACY",
            policy=BookingPaymentPolicy.LEGACY_FULL_ONLINE.value,
            total=Decimal("200000"),
            deposit=Decimal("200000"),
            paid=Decimal("200000"),
            status=BookingStatus.PAID.value,
        )
        add_contribution(
            legacy,
            due=Decimal("200000"),
            paid=Decimal("200000"),
            status=ContributionStatus.PAID.value,
        )

        missing_payment = add_booking(
            "BK-DETAIL-MISSING-PAYMENT",
            total=Decimal("300000"),
            deposit=Decimal("90000"),
            paid=Decimal("45000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        add_contribution(
            missing_payment,
            due=Decimal("90000"),
            paid=Decimal("45000"),
            status=ContributionStatus.PENDING.value,
        )

        partial_refund = add_booking(
            "BK-DETAIL-PARTIAL-REFUND",
            paid=Decimal("40000"),
            status=BookingStatus.PARTIALLY_PAID.value,
        )
        partial_contribution = add_contribution(
            partial_refund,
            due=Decimal("54000"),
            paid=Decimal("40000"),
            status=ContributionStatus.PARTIALLY_REFUNDED.value,
        )
        partial_payment = add_payment(
            partial_refund,
            partial_contribution,
            amount=Decimal("54000"),
            token="DETAIL-PARTIAL",
            paid_at=occurred_at + timedelta(hours=2),
        )
        partial_refund_record = add_refund(
            partial_refund,
            partial_payment,
            amount=Decimal("14000"),
            token="DETAIL-PARTIAL",
            status=RefundStatus.SUCCESS.value,
            refunded_at=occurred_at + timedelta(hours=3),
        )

        full_refund = add_booking(
            "BK-DETAIL-FULL-REFUND",
            paid=Decimal("0"),
            status=BookingStatus.CANCELLED.value,
            cancellation_reason="Chủ sân hủy do sự cố kiểm thử",
        )
        full_contribution = add_contribution(
            full_refund,
            due=Decimal("54000"),
            paid=Decimal("0"),
            status=ContributionStatus.REFUNDED.value,
        )
        full_payment = add_payment(
            full_refund,
            full_contribution,
            amount=Decimal("54000"),
            token="DETAIL-FULL",
            paid_at=occurred_at + timedelta(hours=2),
        )
        add_refund(
            full_refund,
            full_payment,
            amount=Decimal("54000"),
            token="DETAIL-FULL",
            status=RefundStatus.SUCCESS.value,
            refunded_at=occurred_at + timedelta(hours=4),
        )

        refund_attention = add_booking(
            "BK-DETAIL-REFUND-ATTENTION",
            paid=Decimal("54000"),
            status=BookingStatus.REFUND_PENDING.value,
        )
        attention_contribution = add_contribution(
            refund_attention,
            due=Decimal("54000"),
            paid=Decimal("54000"),
            status=ContributionStatus.REFUND_PENDING.value,
        )
        attention_payment = add_payment(
            refund_attention,
            attention_contribution,
            amount=Decimal("54000"),
            token="DETAIL-ATTENTION",
            paid_at=occurred_at + timedelta(hours=1),
        )
        for index, refund_status in enumerate(
            (
                RefundStatus.PENDING.value,
                RefundStatus.PROCESSING.value,
                RefundStatus.FAILED.value,
            ),
            start=1,
        ):
            add_refund(
                refund_attention,
                attention_payment,
                amount=Decimal("5000"),
                token=f"DETAIL-ATTENTION-{index}",
                status=refund_status,
            )

        completed_match = add_booking(
            "BK-DETAIL-COMPLETED-MATCH",
            mode=BookingMode.FIND_OPPONENT.value,
            total=Decimal("300000"),
            deposit=Decimal("90000"),
            paid=Decimal("45000"),
            status=BookingStatus.COMPLETED.value,
        )
        creator_contribution = add_contribution(
            completed_match,
            due=Decimal("45000"),
            paid=Decimal("45000"),
            status=ContributionStatus.PAID.value,
        )
        add_contribution(
            completed_match,
            due=Decimal("45000"),
            paid=Decimal("0"),
            status=ContributionStatus.EXPIRED.value,
            contribution_type=ContributionType.OPPONENT.value,
            slot_number=1,
            user=None,
        )
        add_payment(
            completed_match,
            creator_contribution,
            amount=Decimal("45000"),
            token="DETAIL-MATCH",
            paid_at=occurred_at + timedelta(hours=1),
        )
        match = Match(
            creator_id=user_id,
            booking_id=completed_match.id,
            match_type=MatchType.FIND_OPPONENT.value,
            title="Kèo liên quan Booking Detail",
            required_players=1,
            status=MatchStatus.COMPLETED.value,
            created_at=occurred_at + timedelta(minutes=30),
        )
        db.session.add(match)
        db.session.flush()
        participant = MatchParticipant(
            match_id=match.id,
            user_id=user_id,
            contribution_id=creator_contribution.id,
            participant_type=MatchParticipantType.OPPONENT_REPRESENTATIVE.value,
            status=MatchParticipantStatus.JOINED.value,
            created_at=occurred_at + timedelta(minutes=35),
            decided_at=occurred_at + timedelta(hours=2),
        )
        db.session.add(participant)
        db.session.commit()

        return {
            **list_data,
            "normal": normal.booking_code,
            "normal_payment_id": normal_payment.id,
            "legacy_no_payment": legacy.booking_code,
            "missing_payment": missing_payment.booking_code,
            "partial_refund": partial_refund.booking_code,
            "partial_refund_id": partial_refund_record.id,
            "full_refund": full_refund.booking_code,
            "refund_attention": refund_attention.booking_code,
            "completed_match": completed_match.booking_code,
        }


def test_admin_pages_require_admin_role(app, client):
    user = create_user(app, email="player-admin-denied@example.com")
    login(client, email=user.email)

    admin_paths = (
        "/admin",
        "/admin/accounts",
        "/admin/users",
        "/admin/users/999",
        "/admin/owner-applications",
        "/admin/venues",
        "/admin/monitoring",
        "/admin/bookings",
        "/admin/bookings/UNKNOWN",
        "/admin/matches",
        "/admin/matches/999",
        "/admin/monitoring/bookings/UNKNOWN",
    )
    for path in admin_paths:
        assert client.get(path).status_code == 403

    client.post("/auth/logout")
    owner = create_user(
        app,
        email="owner-admin-denied@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)
    for path in admin_paths:
        assert client.get(path).status_code == 403


def test_admin_dashboard_and_navigation_are_available(app, client):
    admin = create_user(app, email="dashboard-admin@example.com", role=UserRole.ADMIN)
    create_user(app, email="dashboard-player@example.com")
    login(client, email=admin.email)

    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Tổng quan vận hành" in page
    assert "Quản lý tài khoản" in page
    assert "Giám sát dữ liệu" not in page
    assert "/static/css/admin.css" in page
    assert "/static/js/admin-navigation.js" in page
    assert "app-footer" not in page
    assert "/admin/users" in page
    assert 'href="/admin/bookings" title="Lịch đặt sân"' in page


def test_admin_dashboard_uses_database_counts_for_phase_one_kpis(app, client):
    admin = create_user(app, email="kpi-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="kpi-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="kpi-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)

    with app.app_context():
        db.session.add(
            OwnerApplication(
                user_id=player.id,
                business_name="Cơ sở KPI",
                contact_phone="0901234567",
                status=OwnerApplicationStatus.PENDING.value,
            )
        )
        pending_venue = Venue(
            owner_id=owner.id,
            name="Cơ sở chờ KPI",
            address="45 Đường KPI",
            city="TP. Hồ Chí Minh",
            opening_time=time(6, 0),
            closing_time=time(22, 0),
            status=VenueStatus.PENDING.value,
        )
        db.session.add(pending_venue)
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        booking.booking_date = date.today()
        db.session.commit()

    login(client, email=admin.email)
    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Yêu cầu chủ sân đang chờ" in page
    assert "Cơ sở đang chờ duyệt" in page
    assert "Lịch đặt sân hôm nay" in page
    assert "Các vấn đề cần xử lý" in page
    assert "Thanh toán cần kiểm tra" in page
    assert "Hoàn tiền chưa hoàn tất" in page
    assert "PENDING" not in page
    assert "PROCESSING" not in page
    assert "FAILED" not in page

    owner_applications_page = client.get(
        "/admin/owner-applications"
    ).get_data(as_text=True)
    assert "tự động cấp quyền chủ sân" in owner_applications_page
    assert "Role chỉ được đổi qua workflow này" not in owner_applications_page
    assert "Chờ duyệt" in owner_applications_page

    venues_page = client.get("/admin/venues").get_data(as_text=True)
    assert "Kiểm tra đường đi" in venues_page
    assert "Mở chỉ đường trên Google Maps" in venues_page


def test_admin_status_labels_use_vietnamese_business_language():
    assert BOOKING_STATUS_LABELS == {
        BookingStatus.PENDING.value: "Chờ xác nhận",
        BookingStatus.CONFIRMED.value: "Đang giữ chỗ",
        BookingStatus.PARTIALLY_PAID.value: "Đã cọc một phần",
        BookingStatus.PAID.value: "Đã thanh toán cọc",
        BookingStatus.REFUND_PENDING.value: "Đang hoàn tiền",
        BookingStatus.COMPLETED.value: "Đã hoàn thành",
        BookingStatus.REJECTED.value: "Đã từ chối",
        BookingStatus.CANCELLED.value: "Đã hủy",
        BookingStatus.EXPIRED.value: "Đã hết hạn",
    }
    assert PAYMENT_STATUS_LABELS == {
        PaymentStatus.PENDING.value: "Đang chờ xác nhận",
        PaymentStatus.SUCCESS.value: "Thanh toán thành công",
        PaymentStatus.FAILED.value: "Thanh toán thất bại",
        PaymentStatus.CANCELLED.value: "Đã hủy",
        PaymentStatus.EXPIRED.value: "Đã hết hạn",
    }
    assert REFUND_STATUS_LABELS == {
        RefundStatus.PENDING.value: "Chờ xử lý",
        RefundStatus.PROCESSING.value: "Đang xử lý",
        RefundStatus.SUCCESS.value: "Đã hoàn tiền",
        RefundStatus.FAILED.value: "Hoàn tiền thất bại",
    }


def test_admin_sidebar_uses_accepted_operations_endpoints(app, client):
    admin = create_user(app, email="sidebar-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get("/admin")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    for expected_href in (
        "/admin",
        "/admin/owner-applications",
        "/admin/venues",
        "/admin/bookings",
        "/admin/matches",
        "/admin/users",
        "/auth/logout",
    ):
        assert expected_href in page
    assert "/admin/monitoring?section=matches" not in page
    assert 'title="Thanh toán"' not in page
    assert 'title="Hoàn tiền"' not in page

    match_page = client.get("/admin/matches").get_data(as_text=True)
    assert 'title="Kèo chơi" aria-current="page"' in match_page


def test_admin_can_filter_accounts_without_exposing_password_hash(app, client):
    admin = create_user(app, email="accounts-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="unique-player@example.com")
    login(client, email=admin.email)

    response = client.get("/admin/users?q=unique-player&role=USER&status=ACTIVE")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert target.email in page
    assert admin.email not in page
    assert "data-admin-account-root" in page
    assert "data-admin-account-detail-link" in page
    assert "Chọn nhóm tài khoản" in page
    assert "Người dùng" in page
    assert "Đang hoạt động" in page
    assert "password_hash" not in page
    assert PASSWORD not in page


def test_admin_users_searches_name_email_phone_and_handles_empty_result(
    app, client
):
    admin = create_user(app, email="search-admin@example.com", role=UserRole.ADMIN)
    target = create_user(
        app,
        email="minh.anh@example.com",
        full_name="Nguyễn Minh Anh",
        phone="0987654321",
    )
    unrelated = create_user(app, email="unrelated@example.com")
    login(client, email=admin.email)

    for query in ("Minh Anh", "minh.anh@example.com", "0987654321"):
        response = client.get("/admin/users", query_string={"q": query})
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert target.email in page
        assert unrelated.email not in page

    empty = client.get("/admin/users?q=khong-ton-tai")
    empty_page = empty.get_data(as_text=True)
    assert empty.status_code == 200
    assert "Không tìm thấy tài khoản" in empty_page
    assert "khong-ton-tai" in empty_page


def test_admin_users_filters_each_role_and_existing_status(app, client):
    admin = create_user(app, email="filter-admin@example.com", role=UserRole.ADMIN)
    player = create_user(app, email="filter-player@example.com")
    owner = create_user(
        app,
        email="filter-owner@example.com",
        role=UserRole.OWNER,
        status=UserStatus.LOCKED,
    )
    inactive = create_user(
        app,
        email="filter-inactive@example.com",
        status=UserStatus.INACTIVE,
    )
    login(client, email=admin.email)

    expectations = (
        ({"role": "USER", "status": "ACTIVE"}, player.email),
        ({"role": "OWNER", "status": "LOCKED"}, owner.email),
        ({"role": "ADMIN", "status": "ACTIVE"}, admin.email),
        ({"role": "USER", "status": "INACTIVE"}, inactive.email),
    )
    for filters, expected_email in expectations:
        response = client.get("/admin/users", query_string=filters)
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert expected_email in page


def test_admin_users_paginates_at_database_and_keeps_filters(app, client):
    admin = create_user(
        app,
        email="pagination-admin@example.com",
        role=UserRole.ADMIN,
    )
    users = [
        create_user(
            app,
            email=f"locked-{index:02d}@example.com",
            status=UserStatus.LOCKED,
        )
        for index in range(21)
    ]
    login(client, email=admin.email)

    first_page = client.get(
        "/admin/users?role=USER&status=LOCKED&page=1"
    ).get_data(as_text=True)
    second_page = client.get(
        "/admin/users?role=USER&status=LOCKED&page=2"
    ).get_data(as_text=True)

    assert "Trang 1/2" in first_page
    assert "Trang 2/2" in second_page
    assert users[0].email not in first_page
    assert users[0].email in second_page
    assert "role=USER" in first_page
    assert "status=LOCKED" in first_page


def test_admin_user_detail_shows_profile_and_related_data(app, client):
    admin = create_user(app, email="detail-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-player@example.com")
    seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        db.session.add(
            OwnerApplication(
                user_id=owner.id,
                business_name="Hồ sơ chủ sân gần nhất",
                contact_phone="0901234567",
                status=OwnerApplicationStatus.PENDING.value,
            )
        )
        db.session.commit()
    login(client, email=admin.email)

    owner_response = client.get(f"/admin/users/{owner.id}")
    owner_page = owner_response.get_data(as_text=True)
    assert owner_response.status_code == 200
    assert owner.email in owner_page
    assert "Cập nhật gần nhất" in owner_page
    assert "Hồ sơ chủ sân gần nhất" in owner_page
    assert "Số cơ sở sở hữu" in owner_page
    assert "Chờ duyệt" in owner_page

    player_page = client.get(f"/admin/users/{player.id}").get_data(as_text=True)
    assert player.email in player_page
    assert "Số lịch đã đặt" in player_page
    assert "Dữ liệu liên quan" in player_page


def test_admin_locks_and_unlocks_account_without_deleting_history(app, client):
    admin = create_user(app, email="status-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="status-player@example.com")
    login(client, email=admin.email)

    locked = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert locked.status_code == 302

    with app.app_context():
        account = db.session.get(User, target.id)
        assert account is not None
        assert account.status == UserStatus.LOCKED.value

    client.post("/auth/logout")
    rejected_login = login(client, email=target.email)
    assert rejected_login.status_code == 200
    assert "hiện không thể đăng nhập" in rejected_login.get_data(as_text=True)

    login(client, email=admin.email)
    unlocked = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.ACTIVE.value},
    )
    assert unlocked.status_code == 302
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_admin_cannot_lock_current_account_or_submit_invalid_status(app, client):
    admin = create_user(app, email="self-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="invalid-status-player@example.com")
    login(client, email=admin.email)

    self_lock = client.post(
        f"/admin/users/{admin.id}/status",
        data={"status": UserStatus.LOCKED.value},
        follow_redirects=True,
    )
    assert "không thể tự khóa" in self_lock.get_data(as_text=True)

    invalid = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.INACTIVE.value},
        follow_redirects=True,
    )
    assert "không hợp lệ" in invalid.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(User, admin.id).status == UserStatus.ACTIVE.value
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_admin_cannot_change_another_admin_status(app, client):
    admin = create_user(app, email="actor-admin@example.com", role=UserRole.ADMIN)
    other_admin = create_user(
        app,
        email="readonly-admin@example.com",
        role=UserRole.ADMIN,
    )
    login(client, email=admin.email)

    response = client.post(
        f"/admin/users/{other_admin.id}/status",
        data={"status": UserStatus.LOCKED.value},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "chỉ được xem" in page
    with app.app_context():
        account = db.session.get(User, other_admin.id)
        assert account.status == UserStatus.ACTIVE.value
        assert account.role == UserRole.ADMIN.value


def test_non_admin_cannot_change_account_status(app, client):
    target = create_user(app, email="protected-player@example.com")
    user = create_user(app, email="unauthorized-player@example.com")
    login(client, email=user.email)

    response = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert response.status_code == 403

    client.post("/auth/logout")
    owner = create_user(
        app,
        email="unauthorized-owner@example.com",
        role=UserRole.OWNER,
    )
    login(client, email=owner.email)
    response = client.post(
        f"/admin/users/{target.id}/status",
        data={"status": UserStatus.LOCKED.value},
    )
    assert response.status_code == 403

    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_get_cannot_change_account_status_and_post_requires_csrf(app, client):
    admin = create_user(app, email="method-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="method-player@example.com")
    login(client, email=admin.email)

    get_response = client.get(f"/admin/users/{target.id}/status")
    assert get_response.status_code == 405
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value

    app.config["WTF_CSRF_ENABLED"] = True
    try:
        csrf_response = client.post(
            f"/admin/users/{target.id}/status",
            data={"status": UserStatus.LOCKED.value},
        )
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
    assert csrf_response.status_code == 400
    with app.app_context():
        assert db.session.get(User, target.id).status == UserStatus.ACTIVE.value


def test_account_status_action_keeps_current_filters_and_role(app, client):
    admin = create_user(app, email="return-admin@example.com", role=UserRole.ADMIN)
    target = create_user(app, email="return-player@example.com")
    login(client, email=admin.email)

    response = client.post(
        f"/admin/users/{target.id}/status",
        data={
            "status": UserStatus.LOCKED.value,
            "q": "return-player",
            "role": UserRole.USER.value,
            "filter_status": UserStatus.ACTIVE.value,
            "page": "1",
            "selected_id": str(target.id),
        },
    )

    assert response.status_code == 302
    assert f"/admin/users/{target.id}" in response.headers["Location"]
    assert "q=return-player" in response.headers["Location"]
    assert "role=USER" in response.headers["Location"]
    assert "status=ACTIVE" in response.headers["Location"]
    with app.app_context():
        account = db.session.get(User, target.id)
        assert account.status == UserStatus.LOCKED.value
        assert account.role == UserRole.USER.value


def test_admin_booking_operations_is_dedicated_compact_read_only_list(app, client):
    admin = create_user(app, email="booking-ops-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-ops-owner@example.com", role=UserRole.OWNER)
    player = create_user(
        app,
        email="booking-ops-player@example.com",
        full_name="Nguyễn Khách Vận Hành",
    )
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    response = client.get("/admin/bookings", query_string={"q": data["opponent"]})
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-admin-bookings-root" in page
    assert "data-admin-booking-filters" in page
    assert data["opponent"] in page
    assert "300.000 đ" in page
    assert "45.000 đ" in page
    assert "255.000 đ" in page
    assert "Online đã ghi nhận" in page
    assert "Tại sân" in page
    assert "Lịch sử thanh toán" not in page
    assert "Lịch sử hoàn tiền" not in page
    assert "PAY-OPS-OPPONENT" not in page
    assert f"/admin/bookings/{data['opponent']}" in page
    assert f"/admin/monitoring/bookings/{data['opponent']}" not in page
    assert "/static/js/administrative-unit-picker.js" in page
    assert "/static/js/admin-bookings.js" in page
    assert 'href="/admin/bookings">Xóa lọc</a>' in page
    assert "admin-booking-code" in page


def test_admin_booking_operations_searches_all_accepted_sources(app, client):
    admin = create_user(app, email="booking-search-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-search-owner@example.com", role=UserRole.OWNER)
    player = create_user(
        app,
        email="booking-search-player@example.com",
        full_name="Trần Minh Booking Ops",
    )
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    for query in (
        data["main"],
        data["customer_name"],
        data["customer_email"],
        "PAY-OPS-SEARCH-TARGET",
        "REFUND-OPS-SEARCH-TARGET",
    ):
        response = client.get("/admin/bookings", query_string={"q": query})
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        if query in {data["customer_name"], data["customer_email"]}:
            assert data["customer_email"] in page
        else:
            assert data["main"] in page, query
            assert data["opponent"] not in page


def test_admin_booking_operations_filters_status_sport_date_and_location(app, client):
    admin = create_user(app, email="booking-filter-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-filter-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-filter-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    filters = {
        "status": BookingStatus.PARTIALLY_PAID.value,
        "sport": data["sport_code"],
        "date": data["scheduled_date"],
        "province_code": data["province_code"],
        "ward_code": data["ward_code"],
        "venue": data["venue_id"],
        "field": data["field_id"],
    }
    response = client.get("/admin/bookings", query_string=filters)
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert data["main"] in page
    assert data["opponent"] in page
    assert data["legacy"] not in page
    assert f'value="{data["province_code"]}"' in page
    assert data["ward_name"] in page
    assert "Cơ sở Booking Ops A" in page
    assert "Sân Booking Ops A" in page

    status_page = client.get(
        "/admin/bookings",
        query_string={"status": BookingStatus.PAID.value, "q": data["legacy"]},
    ).get_data(as_text=True)
    assert data["legacy"] in status_page
    assert data["main"] not in status_page

    sport_page = client.get(
        "/admin/bookings",
        query_string={"sport": data["other_sport_code"]},
    ).get_data(as_text=True)
    assert data["legacy"] in sport_page
    assert data["main"] not in sport_page

    wrong_date_page = client.get(
        "/admin/bookings",
        query_string={"date": (date.today() + timedelta(days=30)).isoformat()},
    ).get_data(as_text=True)
    assert "Không tìm thấy lịch đặt" in wrong_date_page

    other_location_page = client.get(
        "/admin/bookings",
        query_string={
            "province_code": data["other_province_code"],
            "venue": data["other_venue_id"],
            "field": data["other_field_id"],
        },
    ).get_data(as_text=True)
    assert data["legacy"] in other_location_page
    assert data["main"] not in other_location_page

    legacy_fallback = client.get(
        "/admin/bookings",
        query_string={
            "q": data["legacy_location"],
            "province_code": data["province_code"],
            "ward_code": data["ward_code"],
        },
    ).get_data(as_text=True)
    assert data["legacy_location"] in legacy_fallback

    invalid_ward = client.get(
        "/admin/bookings",
        query_string={"ward_code": data["ward_code"]},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "chọn tỉnh hoặc thành phố trước" in invalid_ward

    invalid_chain = client.get(
        "/admin/bookings",
        query_string={
            "province_code": data["other_province_code"],
            "venue": data["venue_id"],
        },
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Cơ sở không thuộc khu vực đã chọn" in invalid_chain


def test_admin_booking_operations_paginates_six_and_preserves_filters(app, client):
    admin = create_user(app, email="booking-page-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-page-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-page-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    response = client.get(
        "/admin/bookings",
        query_string={
            "q": "BK-OPS",
            "date": data["scheduled_date"],
            "province_code": data["province_code"],
            "page": 1,
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert page.count('class="admin-booking-code"') == 6
    assert "Trang <strong>1</strong> / 2" in page
    assert "q=BK-OPS" in page
    assert f"date={data['scheduled_date']}" in page
    assert f"province_code={data['province_code']}" in page

    second_page = client.get(
        "/admin/bookings",
        query_string={
            "q": "BK-OPS",
            "date": data["scheduled_date"],
            "province_code": data["province_code"],
            "page": 2,
        },
    ).get_data(as_text=True)
    assert "Trang <strong>2</strong> / 2" in second_page


def test_admin_booking_operations_distinguishes_legacy_policy_and_attention(app, client):
    admin = create_user(app, email="booking-attention-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-attention-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-attention-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    legacy = client.get(
        "/admin/bookings", query_string={"q": "PAY-OPS-LEGACY"}
    ).get_data(as_text=True)
    assert "Online toàn phần (lịch sử)" in legacy
    assert "Cọc online theo chính sách" not in legacy

    pending = client.get(
        "/admin/bookings",
        query_string={"q": data["payment_attention_codes"][PaymentStatus.PENDING.value]},
    ).get_data(as_text=True)
    assert "Thanh toán chờ xác nhận" in pending
    assert "Thanh toán cần kiểm tra" not in pending

    for payment_status in (
        PaymentStatus.FAILED.value,
        PaymentStatus.CANCELLED.value,
        PaymentStatus.EXPIRED.value,
    ):
        page = client.get(
            "/admin/bookings",
            query_string={"q": data["payment_attention_codes"][payment_status]},
        ).get_data(as_text=True)
        assert "Thanh toán cần kiểm tra" in page

    for refund_status in (
        RefundStatus.PENDING.value,
        RefundStatus.PROCESSING.value,
        RefundStatus.FAILED.value,
    ):
        page = client.get(
            "/admin/bookings",
            query_string={"q": data["refund_attention_codes"][refund_status]},
        ).get_data(as_text=True)
        assert "Hoàn tiền cần theo dõi" in page

    combined = client.get(
        "/admin/bookings", query_string={"q": data["combined"]}
    ).get_data(as_text=True)
    assert "Thanh toán và hoàn tiền cần theo dõi" in combined

    success_only = client.get(
        "/admin/bookings", query_string={"q": data["main"]}
    ).get_data(as_text=True)
    assert "Hoàn tiền cần theo dõi" not in success_only
    assert "Thanh toán và hoàn tiền cần theo dõi" not in success_only
    assert "Thanh toán cần kiểm tra" not in success_only
    assert "Thanh toán chờ xác nhận" not in success_only


def test_admin_booking_operations_get_does_not_mutate_financial_data(app, client):
    admin = create_user(app, email="booking-read-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="booking-read-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="booking-read-player@example.com")
    data = seed_booking_operations_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["main"])
        )
        before = (booking.status, booking.paid_amount)
        payment_count = db.session.scalar(db.select(db.func.count()).select_from(Payment))
        refund_count = db.session.scalar(db.select(db.func.count()).select_from(Refund))
        contribution_count = db.session.scalar(
            db.select(db.func.count()).select_from(BookingContribution)
        )

    login(client, email=admin.email)
    assert client.get("/admin/bookings").status_code == 200

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["main"])
        )
        assert (booking.status, booking.paid_amount) == before
        assert db.session.scalar(db.select(db.func.count()).select_from(Payment)) == payment_count
        assert db.session.scalar(db.select(db.func.count()).select_from(Refund)) == refund_count
        assert (
            db.session.scalar(
                db.select(db.func.count()).select_from(BookingContribution)
            )
            == contribution_count
        )


def test_admin_match_operations_search_filters_and_paginates(app, client):
    data = setup_admin_match_operations(app, client, "list")

    response = client.get("/admin/matches")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert page.count("data-match-row=") == 6
    assert "Kèo" in page
    assert "Lịch đặt" in page
    assert "Người tạo" in page
    assert "Địa điểm" in page
    assert "Loại &amp; số người" in page
    assert "Trạng thái / Theo dõi" in page
    assert "/static/js/administrative-unit-picker.js" in page
    assert "data-admin-dependent-location" in page

    searches = (
        str(data["players_match_id"]),
        "Kèo cầu lông Alpha",
        data["players_booking_code"],
    )
    for query in searches:
        search_page = client.get(
            "/admin/matches", query_string={"q": query}
        ).get_data(as_text=True)
        assert "Kèo cầu lông Alpha" in search_page, query

    for creator_query in (data["creator_name"], data["creator_email"]):
        creator_page = client.get(
            "/admin/matches", query_string={"q": creator_query}
        ).get_data(as_text=True)
        assert creator_page.count("data-match-row=") == 6
        assert data["creator_email"] in creator_page

    completed_page = client.get(
        "/admin/matches",
        query_string={"status": MatchStatus.COMPLETED.value},
    ).get_data(as_text=True)
    assert f'data-match-row="{data["completed_match_id"]}"' in completed_page
    assert f'data-match-row="{data["players_match_id"]}"' not in completed_page

    opponent_page = client.get(
        "/admin/matches",
        query_string={"match_type": MatchType.FIND_OPPONENT.value},
    ).get_data(as_text=True)
    assert "Kèo đối thủ chờ cọc" in opponent_page
    assert "Kèo đối thủ đã nhận" in opponent_page
    assert "Kèo cầu lông Alpha" not in opponent_page

    sport_page = client.get(
        "/admin/matches",
        query_string={"sport": data["other_sport_code"]},
    ).get_data(as_text=True)
    assert f'data-match-row="{data["completed_match_id"]}"' in sport_page
    assert f'data-match-row="{data["players_match_id"]}"' not in sport_page

    date_page = client.get(
        "/admin/matches",
        query_string={"date": data["scheduled_date"]},
    ).get_data(as_text=True)
    assert "7</strong> kèo chơi" in date_page

    location_filters = {
        "province_code": data["province_code"],
        "ward_code": data["ward_code"],
        "venue": data["venue_id"],
        "field": data["field_id"],
    }
    location_page = client.get(
        "/admin/matches", query_string=location_filters
    ).get_data(as_text=True)
    assert "Kèo cầu lông Alpha" in location_page
    assert f'data-match-row="{data["completed_match_id"]}"' not in location_page

    legacy_location_page = client.get(
        "/admin/matches",
        query_string={
            "q": "LEGACY-LOCATION",
            "province_code": data["province_code"],
            "ward_code": data["ward_code"],
        },
    ).get_data(as_text=True)
    assert f'data-match-row="{data["legacy_location_match_id"]}"' in legacy_location_page

    invalid_ward = client.get(
        "/admin/matches",
        query_string={"ward_code": data["ward_code"]},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "chọn tỉnh hoặc thành phố trước" in invalid_ward

    invalid_chain = client.get(
        "/admin/matches",
        query_string={
            "province_code": data["other_province_code"],
            "venue": data["venue_id"],
        },
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Cơ sở không thuộc khu vực đã chọn" in invalid_chain

    invalid_type = client.get(
        "/admin/matches",
        query_string={"match_type": "UNKNOWN"},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Loại kèo không hợp lệ" in invalid_type

    first_page = client.get(
        "/admin/matches",
        query_string={
            "q": "BK-MATCH-OPS",
            "date": data["scheduled_date"],
            "page": 1,
        },
    ).get_data(as_text=True)
    assert first_page.count("data-match-row=") == 6
    assert "Trang <strong>1</strong> / 2" in first_page
    assert "q=BK-MATCH-OPS" in first_page
    assert f"date={data['scheduled_date']}" in first_page

    second_page = client.get(
        "/admin/matches",
        query_string={
            "q": "BK-MATCH-OPS",
            "date": data["scheduled_date"],
            "page": 2,
        },
    ).get_data(as_text=True)
    assert "Trang <strong>2</strong> / 2" in second_page
    assert f'data-match-row="{data["players_match_id"]}"' in second_page


def test_admin_match_operations_attention_and_detail_context(app, client):
    data = setup_admin_match_operations(app, client, "detail")

    pending_list = client.get(
        "/admin/matches", query_string={"q": data["players_booking_code"]}
    ).get_data(as_text=True)
    assert "1 yêu cầu tham gia đang chờ xử lý" in pending_list

    awaiting_list = client.get(
        "/admin/matches", query_string={"q": data["awaiting_booking_code"]}
    ).get_data(as_text=True)
    assert "1 người đang chờ thanh toán cọc" in awaiting_list
    assert "thanh toán thất bại" not in awaiting_list.lower()

    detail_response = client.get(
        f'/admin/matches/{data["awaiting_match_id"]}'
    )
    detail_page = detail_response.get_data(as_text=True)
    assert detail_response.status_code == 200
    assert data["awaiting_booking_code"] in detail_page
    assert f'/admin/bookings/{data["awaiting_booking_code"]}' in detail_page
    assert "Đại diện đội đối thủ" in detail_page
    assert "Chờ đặt cọc" in detail_page
    assert "Hạn thanh toán cọc" in detail_page
    assert "Đội đối thủ" in detail_page
    assert "45.000 đ" in detail_page
    assert "255.000 đ" in detail_page
    assert "Đây là trạng thái theo dõi, không tự động là lỗi" in detail_page
    assert "Lịch sử thanh toán" not in detail_page
    assert "Lịch sử hoàn tiền" not in detail_page
    assert "Mã giao dịch nhà cung cấp" not in detail_page

    players_page = client.get(
        f'/admin/matches/{data["players_match_id"]}'
    ).get_data(as_text=True)
    for label in ("Đang chờ", "Đã tham gia", "Đã từ chối", "Đã rút"):
        assert label in players_page
    assert "Không có nghĩa vụ online được liên kết" in players_page
    assert "1 yêu cầu tham gia đang chờ xử lý" in players_page
    assert 'data-closed-participants="2"' in players_page
    assert "yêu cầu đã từ chối, hết hạn hoặc rút khỏi kèo" in players_page

    joined_page = client.get(
        f'/admin/matches/{data["joined_match_id"]}'
    ).get_data(as_text=True)
    assert "Đã có đối thủ" in joined_page
    assert "Hiện ghi nhận: 45.000 đ" in joined_page


def test_admin_match_effective_status_is_read_only_and_filterable(app, client):
    data = setup_admin_match_operations(app, client, "effective-status")
    with app.app_context():
        before_match_states = tuple(
            db.session.execute(
                db.select(Match.id, Match.status).order_by(Match.id)
            ).all()
        )
        before_booking_states = tuple(
            db.session.execute(
                db.select(Booking.id, Booking.status).order_by(Booking.id)
            ).all()
        )

    past_list = client.get(
        "/admin/matches",
        query_string={"q": data["past_open_booking_code"]},
    ).get_data(as_text=True)
    assert (
        f'data-match-row="{data["past_open_match_id"]}" '
        'data-match-effective-status="ENDED"'
    ) in past_list
    assert "Đã kết thúc" in past_list

    future_list = client.get(
        "/admin/matches",
        query_string={"q": data["players_booking_code"]},
    ).get_data(as_text=True)
    assert (
        f'data-match-row="{data["players_match_id"]}" '
        'data-match-effective-status="OPEN"'
    ) in future_list
    assert "Đang mở" in future_list

    open_filter = client.get(
        "/admin/matches",
        query_string={"status": MatchStatus.OPEN.value},
    ).get_data(as_text=True)
    assert f'data-match-row="{data["players_match_id"]}"' in open_filter
    assert f'data-match-row="{data["past_open_match_id"]}"' not in open_filter

    ended_filter = client.get(
        "/admin/matches",
        query_string={"status": "ENDED"},
    ).get_data(as_text=True)
    assert f'data-match-row="{data["past_open_match_id"]}"' in ended_filter
    assert 'data-match-effective-status="ENDED"' in ended_filter

    past_detail = client.get(
        f'/admin/matches/{data["past_open_match_id"]}'
    ).get_data(as_text=True)
    assert 'data-current-match-status="OPEN"' in past_detail
    assert 'data-current-match-effective-status="ENDED"' in past_detail
    assert "Đã kết thúc" in past_detail

    with app.app_context():
        assert tuple(
            db.session.execute(
                db.select(Match.id, Match.status).order_by(Match.id)
            ).all()
        ) == before_match_states
        assert tuple(
            db.session.execute(
                db.select(Booking.id, Booking.status).order_by(Booking.id)
            ).all()
        ) == before_booking_states


def test_admin_match_detail_uses_only_recorded_historical_timestamps(app, client):
    data = setup_admin_match_operations(app, client, "history")

    players_page = client.get(
        f'/admin/matches/{data["players_match_id"]}'
    ).get_data(as_text=True)
    assert 'data-event-type="match_created"' in players_page
    assert players_page.count('data-event-type="participant_created"') == 4
    assert players_page.count('data-event-type="participant_decided"') == 3
    assert "Sự kiện đã ghi nhận" in players_page

    completed_page = client.get(
        f'/admin/matches/{data["completed_match_id"]}'
    ).get_data(as_text=True)
    assert "Đã hoàn thành" in completed_page
    assert completed_page.count("data-event-type=") == 1
    assert "04/09/2026 13:00" not in completed_page
    assert "Hoàn tất kèo" not in completed_page

    cancelled_page = client.get(
        f'/admin/matches/{data["cancelled_match_id"]}'
    ).get_data(as_text=True)
    assert "Đã hủy" in cancelled_page
    assert "Chủ sân hủy lịch kiểm thử" in cancelled_page
    assert cancelled_page.count("data-event-type=") == 1
    assert "04/09/2026 14:00" not in cancelled_page


def test_admin_match_get_routes_do_not_mutate_domain_data(app, client):
    data = setup_admin_match_operations(app, client, "readonly")
    with app.app_context():
        match_states = tuple(
            db.session.execute(
                db.select(Match.id, Match.status).order_by(Match.id)
            ).all()
        )
        participant_states = tuple(
            db.session.execute(
                db.select(
                    MatchParticipant.id,
                    MatchParticipant.status,
                    MatchParticipant.decided_at,
                ).order_by(MatchParticipant.id)
            ).all()
        )
        booking_states = tuple(
            db.session.execute(
                db.select(Booking.id, Booking.status, Booking.paid_amount).order_by(
                    Booking.id
                )
            ).all()
        )
        counts = (
            db.session.scalar(db.select(db.func.count()).select_from(Match)),
            db.session.scalar(
                db.select(db.func.count()).select_from(MatchParticipant)
            ),
            db.session.scalar(
                db.select(db.func.count()).select_from(BookingContribution)
            ),
            db.session.scalar(db.select(db.func.count()).select_from(Payment)),
            db.session.scalar(db.select(db.func.count()).select_from(Refund)),
        )

    assert client.get("/admin/matches").status_code == 200
    assert client.get(f'/admin/matches/{data["awaiting_match_id"]}').status_code == 200

    with app.app_context():
        assert tuple(
            db.session.execute(
                db.select(Match.id, Match.status).order_by(Match.id)
            ).all()
        ) == match_states
        assert tuple(
            db.session.execute(
                db.select(
                    MatchParticipant.id,
                    MatchParticipant.status,
                    MatchParticipant.decided_at,
                ).order_by(MatchParticipant.id)
            ).all()
        ) == participant_states
        assert tuple(
            db.session.execute(
                db.select(Booking.id, Booking.status, Booking.paid_amount).order_by(
                    Booking.id
                )
            ).all()
        ) == booking_states
        assert (
            db.session.scalar(db.select(db.func.count()).select_from(Match)),
            db.session.scalar(
                db.select(db.func.count()).select_from(MatchParticipant)
            ),
            db.session.scalar(
                db.select(db.func.count()).select_from(BookingContribution)
            ),
            db.session.scalar(db.select(db.func.count()).select_from(Payment)),
            db.session.scalar(db.select(db.func.count()).select_from(Refund)),
        ) == counts


def test_admin_match_legacy_mapping_sidebar_and_booking_cross_link(app, client):
    data = setup_admin_match_operations(app, client, "compat")

    legacy = client.get(
        "/admin/monitoring",
        query_string={
            "section": "matches",
            "q": "BK-MATCH-OPS",
            "status": MatchStatus.OPEN.value,
            "venue": data["venue_id"],
            "field": data["field_id"],
            "page": 2,
            "focus": "payment_issue",
            "venue_q": "khong-mang-theo",
        },
    )
    assert legacy.status_code == 302
    assert legacy.location.startswith("/admin/matches?")
    for expected in (
        "q=BK-MATCH-OPS",
        "status=OPEN",
        f'venue={data["venue_id"]}',
        f'field={data["field_id"]}',
        "page=2",
    ):
        assert expected in legacy.location
    assert "section=" not in legacy.location
    assert "focus=" not in legacy.location
    assert "venue_q=" not in legacy.location

    match_page = client.get(
        f'/admin/matches/{data["players_match_id"]}'
    ).get_data(as_text=True)
    assert 'title="Kèo chơi" aria-current="page"' in match_page
    assert 'title="Thanh toán"' not in match_page
    assert 'title="Hoàn tiền"' not in match_page

    booking_page = client.get(
        f'/admin/bookings/{data["players_booking_code"]}'
    ).get_data(as_text=True)
    assert f'/admin/matches/{data["players_match_id"]}' in booking_page
    assert "Mở Match Detail" in booking_page

    missing = client.get("/admin/matches/999999", follow_redirects=True)
    assert missing.status_code == 200
    assert "Không tìm thấy kèo chơi cần theo dõi" in missing.get_data(as_text=True)


def test_admin_monitoring_lists_all_mvp_records(app, client):
    admin = create_user(app, email="monitor-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="monitor-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="monitor-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    expected = {
        "bookings": booking_code,
        "catalog": "Sân bóng đá 5 người",
    }
    for section, marker in expected.items():
        response = client.get(f"/admin/monitoring?section={section}")
        assert response.status_code == 200
        assert marker in response.get_data(as_text=True)


def test_admin_monitoring_explains_data_and_opens_booking_detail(app, client):
    admin = create_user(app, email="monitor-ui-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="monitor-ui-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="monitor-ui-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    monitoring = client.get("/admin/monitoring?section=bookings")
    monitoring_page = monitoring.get_data(as_text=True)

    assert monitoring.status_code == 200
    assert "Tình trạng cần kiểm tra" not in monitoring_page
    assert "Lịch đặt sân &amp; dòng tiền" in monitoring_page
    assert "Chọn cơ sở" in monitoring_page
    assert "Cơ sở Admin Test" in monitoring_page
    assert "Sân kiểm thử" in monitoring_page
    assert "Tiến độ tiền cọc" in monitoring_page
    assert "Xem thanh toán và hoàn tiền" in monitoring_page
    assert "PAY-ADMIN-MONITOR" in monitoring_page
    assert "REFUND-ADMIN-MONITOR" in monitoring_page
    assert "Xem hồ sơ đầy đủ" in monitoring_page
    assert "data-admin-workspace-detail-link" in monitoring_page
    assert f"/admin/monitoring/bookings/{booking_code}" in monitoring_page

    legacy_detail = client.get(f"/admin/monitoring/bookings/{booking_code}")
    assert legacy_detail.status_code == 302
    assert legacy_detail.headers["Location"].endswith(
        f"/admin/bookings/{booking_code}"
    )

    detail = client.get(f"/admin/bookings/{booking_code}")
    detail_page = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert booking_code in detail_page
    assert "Số tiền hiện được ghi nhận" in detail_page
    assert "Đối chiếu nghĩa vụ và số tiền hiện tại" in detail_page
    assert "Lịch sử thanh toán" in detail_page
    assert "Lịch sử hoàn tiền" in detail_page
    assert "Sự kiện đã ghi nhận" in detail_page
    assert "Trạng thái hiện tại" in detail_page
    assert "PAY-ADMIN-MONITOR" in detail_page
    assert "REFUND-ADMIN-MONITOR" in detail_page
    assert "Kèo Admin Test" in detail_page
    assert "90.000 đ" in detail_page
    assert "10.000 đ" in detail_page
    assert "80.000 đ" in detail_page
    assert "220.000 đ" in detail_page


def test_admin_booking_detail_shows_canonical_read_only_deposit_record(app, client):
    admin = create_user(app, email="detail-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["normal"])
        )
        before = (
            booking.status,
            booking.paid_amount,
            booking.contributions[0].status,
            booking.contributions[0].amount_paid,
            db.session.scalar(db.select(db.func.count()).select_from(Payment)),
            db.session.scalar(db.select(db.func.count()).select_from(Refund)),
        )

    login(client, email=admin.email)
    response = client.get(
        f"/admin/bookings/{data['normal']}",
        query_string={
            "q": "booking detail",
            "status": BookingStatus.PAID.value,
            "page": 2,
            "next": "https://example.com/not-allowed",
        },
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-admin-booking-detail" in page
    assert data["normal"] in page
    assert "Cọc online theo chính sách" in page
    assert "180.000 đ" in page
    assert "54.000 đ" in page
    assert "126.000 đ" in page
    assert "ORDER-DETAIL-NORMAL" in page
    assert "REQUEST-DETAIL-NORMAL" in page
    assert "TRANS-DETAIL-NORMAL" in page
    assert "Mã đơn hàng" in page
    assert "Mã yêu cầu" in page
    assert "Mã giao dịch nhà cung cấp" in page
    assert "Thời điểm thanh toán" in page
    assert "Online ròng đang ghi nhận" in page
    assert "Đã thanh toán thành công" in page
    assert "Đã hoàn tiền thành công" in page
    assert "Ví MoMo" in page
    assert "03/09/2026 09:00" in page
    assert 'title="Lịch đặt sân" aria-current="page"' in page
    assert "q=booking+detail" in page
    assert "status=PAID" in page
    assert "page=2" in page
    assert "https://example.com/not-allowed" not in page
    assert "Chỉ xem" in page

    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == data["normal"])
        )
        after = (
            booking.status,
            booking.paid_amount,
            booking.contributions[0].status,
            booking.contributions[0].amount_paid,
            db.session.scalar(db.select(db.func.count()).select_from(Payment)),
            db.session.scalar(db.select(db.func.count()).select_from(Refund)),
        )
        assert after == before


def test_admin_booking_detail_preserves_financial_policy_edge_cases(app, client):
    admin = create_user(app, email="detail-money-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-money-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-money-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    opponent_page = client.get(
        f"/admin/bookings/{data['opponent']}"
    ).get_data(as_text=True)
    assert "300.000 đ" in opponent_page
    assert "45.000 đ" in opponent_page
    assert "255.000 đ" in opponent_page
    assert "Tìm đối thủ" in opponent_page

    legacy_page = client.get(
        f"/admin/bookings/{data['legacy_no_payment']}"
    ).get_data(as_text=True)
    assert "Online toàn phần (lịch sử)" in legacy_page
    assert "Khoản online lịch sử" in legacy_page
    assert 'data-missing-payment-history="legacy"' in legacy_page
    assert "không có Payment chi tiết" in legacy_page
    assert "Cần đối chiếu:</strong>" not in legacy_page

    inconsistent_page = client.get(
        f"/admin/bookings/{data['missing_payment']}"
    ).get_data(as_text=True)
    assert "Cọc online theo chính sách" in inconsistent_page
    assert 'data-missing-payment-history="investigate"' in inconsistent_page
    assert "không có Payment tương ứng" in inconsistent_page
    assert "Cần đối chiếu:</strong>" in inconsistent_page


def test_admin_booking_detail_reconciles_successful_payments_and_refunds(app, client):
    admin = create_user(app, email="detail-refund-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-refund-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-refund-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    partial_page = client.get(
        f"/admin/bookings/{data['partial_refund']}"
    ).get_data(as_text=True)
    contribution_table = partial_page.split(
        '<table class="table admin-table admin-contribution-table', 1
    )[1].split("</table>", 1)[0]
    assert "54.000 đ" in contribution_table
    assert "14.000 đ" in contribution_table
    assert "40.000 đ" in contribution_table
    assert "Hoàn một phần" in contribution_table
    assert "ORDER-DETAIL-PARTIAL" in partial_page
    assert f'href="#refund-{data["partial_refund_id"]}"' in partial_page
    assert "REFUND-DETAIL-PARTIAL" in partial_page
    assert "REFUND-REQUEST-DETAIL-PARTIAL" in partial_page
    assert "REFUND-TRANS-DETAIL-PARTIAL" in partial_page
    assert "Payment gốc: ORDER-DETAIL-PARTIAL" in partial_page
    assert "Mã giao dịch hoàn tiền" in partial_page
    assert "Thời điểm hoàn tiền" in partial_page
    assert "Cần đối chiếu:</strong>" not in partial_page

    full_page = client.get(
        f"/admin/bookings/{data['full_refund']}"
    ).get_data(as_text=True)
    full_table = full_page.split(
        '<table class="table admin-table admin-contribution-table', 1
    )[1].split("</table>", 1)[0]
    assert full_table.count("54.000 đ") >= 2
    assert "0 đ" in full_table
    assert "Đã hoàn" in full_table
    assert "Chủ sân hủy do sự cố kiểm thử" in full_page
    assert "Cần đối chiếu:</strong>" not in full_page

    attention_page = client.get(
        f"/admin/bookings/{data['refund_attention']}"
    ).get_data(as_text=True)
    attention_table = attention_page.split(
        '<table class="table admin-table admin-contribution-table', 1
    )[1].split("</table>", 1)[0]
    assert attention_table.count("54.000 đ") >= 2
    assert "0 đ" in attention_table
    assert "3 Refund cần theo dõi" in attention_page
    assert "Chờ xử lý" in attention_page
    assert "Đang xử lý" in attention_page
    assert "Hoàn tiền thất bại" in attention_page
    assert "Cần đối chiếu:</strong>" not in attention_page
    assert 'data-event-type="refund_success"' not in attention_page


def test_admin_booking_detail_separates_recorded_events_from_current_state(app, client):
    admin = create_user(app, email="detail-events-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-events-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-events-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    completed_page = client.get(
        f"/admin/bookings/{data['completed_match']}"
    ).get_data(as_text=True)
    assert 'data-current-booking-status="COMPLETED"' in completed_page
    assert "Kèo liên quan Booking Detail" in completed_page
    assert "Mở Match Detail" in completed_page
    assert "/admin/matches/" in completed_page
    assert 'data-event-type="booking_created"' in completed_page
    assert 'data-event-type="match_created"' in completed_page
    assert 'data-event-type="payment_success"' in completed_page
    assert 'data-event-type="participant_decided"' in completed_page
    assert 'data-event-type="booking_completed"' not in completed_page
    assert "completed_at" not in completed_page
    assert "updated_at" not in completed_page
    assert completed_page.index('data-event-type="booking_created"') < completed_page.index(
        'data-event-type="match_created"'
    )
    assert completed_page.index('data-event-type="match_created"') < completed_page.index(
        'data-event-type="payment_success"'
    )

    cancelled_page = client.get(
        f"/admin/bookings/{data['full_refund']}"
    ).get_data(as_text=True)
    assert 'data-current-booking-status="CANCELLED"' in cancelled_page
    assert "Lý do hủy" in cancelled_page
    assert 'data-event-type="booking_cancelled"' not in cancelled_page
    assert "cancelled_at" not in cancelled_page
    assert 'data-event-type="payment_success"' in cancelled_page
    assert 'data-event-type="refund_success"' in cancelled_page


def test_admin_booking_detail_legacy_route_redirects_to_canonical_with_safe_filters(
    app,
    client,
):
    admin = create_user(app, email="detail-route-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="detail-route-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="detail-route-player@example.com")
    data = seed_booking_detail_data(app, user_id=player.id, owner_id=owner.id)
    login(client, email=admin.email)

    response = client.get(
        f"/admin/monitoring/bookings/{data['normal']}",
        query_string={
            "q": "safe",
            "province_code": data["province_code"],
            "venue": data["venue_id"],
            "page": 2,
            "next": "https://example.com/not-allowed",
            "section": "payments",
        },
    )

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith(f"/admin/bookings/{data['normal']}?")
    assert "q=safe" in location
    assert f"province_code={data['province_code']}" in location
    assert f"venue={data['venue_id']}" in location
    assert "page=2" in location
    assert "example.com" not in location
    assert "section=" not in location


def test_admin_booking_detail_redirects_when_booking_does_not_exist(app, client):
    admin = create_user(app, email="missing-booking-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get(
        "/admin/monitoring/bookings/DOES-NOT-EXIST",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Không tìm thấy lịch đặt sân cần theo dõi" in response.get_data(as_text=True)


def test_admin_monitoring_filters_by_venue_and_field_with_friendly_labels(
    app,
    client,
):
    admin = create_user(app, email="location-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="location-owner@example.com", role=UserRole.OWNER)
    player = create_user(app, email="location-player@example.com")
    booking_code = seed_monitoring_data(app, user_id=player.id, owner_id=owner.id)
    with app.app_context():
        booking = db.session.scalar(
            db.select(Booking).where(Booking.booking_code == booking_code)
        )
        venue_id = booking.field.venue_id
        field_id = booking.field_id
    login(client, email=admin.email)

    for section in ("bookings",):
        response = client.get(
            f"/admin/monitoring?section={section}&venue={venue_id}&field={field_id}"
        )
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Cơ sở Admin Test" in page
        assert "Sân kiểm thử" in page

    payments_page = client.get(
        f"/admin/monitoring?section=bookings&venue={venue_id}&field={field_id}"
    ).get_data(as_text=True)
    assert "Thanh toán thử nghiệm" in payments_page
    assert ">MOCK<" not in payments_page

    invalid_field = client.get(
        f"/admin/monitoring?section=bookings&venue={venue_id}&field=999999",
        follow_redirects=True,
    )
    assert "Không tìm thấy sân đã chọn" in invalid_field.get_data(as_text=True)


def test_admin_monitoring_searches_regions_and_paginates_many_venues(app, client):
    admin = create_user(app, email="many-venues-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="many-venues-owner@example.com", role=UserRole.OWNER)
    with app.app_context():
        venue_ids = []
        field_type = db.session.scalar(
            db.select(FieldType).where(
                FieldType.code == FieldTypeCode.FOOTBALL_5.value
            )
        )
        for index in range(1, 51):
            venue = Venue(
                owner_id=owner.id,
                name=f"Cơ sở mở rộng {index:02d}",
                address=f"{index} Đường mở rộng {index:02d}",
                district="Quận 7" if index % 2 == 0 else "Quận 9",
                city="TP. Hồ Chí Minh",
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                status=VenueStatus.ACTIVE.value,
            )
            db.session.add(venue)
            db.session.flush()
            venue_ids.append(venue.id)
        for index in range(1, 31):
            db.session.add(
                Field(
                    venue_id=venue_ids[-1],
                    name=f"Sân mở rộng {index:02d}",
                    field_type_id=field_type.id,
                    capacity=10,
                    status=FieldStatus.ACTIVE.value,
                )
            )
        db.session.commit()
    login(client, email=admin.email)

    first_page = client.get(
        "/admin/monitoring",
        query_string={"section": "bookings", "venue_q": "Cơ sở mở rộng"},
    ).get_data(as_text=True)
    assert "50 cơ sở phù hợp" in first_page
    assert "Cơ sở mở rộng 01" in first_page
    assert "Cơ sở mở rộng 10" in first_page
    assert "Cơ sở mở rộng 11" not in first_page
    assert "Trang 1/5" in first_page

    second_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue_q": "Cơ sở mở rộng",
            "venue_page": 5,
        },
    ).get_data(as_text=True)
    assert "Cơ sở mở rộng 41" in second_page
    assert "Cơ sở mở rộng 50" in second_page
    assert "Cơ sở mở rộng 01" not in second_page
    assert "Trang 5/5" in second_page

    district_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue_q": "Cơ sở mở rộng",
            "venue_city": "TP. Hồ Chí Minh",
            "venue_district": "Quận 7",
        },
    ).get_data(as_text=True)
    assert "25 cơ sở phù hợp" in district_page
    assert "Cơ sở mở rộng 02" in district_page
    assert "Cơ sở mở rộng 01" not in district_page

    selected_page = client.get(
        "/admin/monitoring",
        query_string={
            "section": "bookings",
            "venue": venue_ids[-1],
            "venue_q": "Cơ sở mở rộng",
            "venue_page": 5,
        },
    ).get_data(as_text=True)
    assert "Cơ sở mở rộng 50" in selected_page
    assert "30 sân" in selected_page
    assert "data-admin-field-search" in selected_page
    assert "Xem thêm 22 sân" in selected_page
    assert 'data-field-search-value="Sân mở rộng 30' in selected_page
    assert "hidden data-admin-field-extra" in selected_page


def test_admin_monitoring_validates_filters(app, client):
    admin = create_user(app, email="filter-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    invalid_section = client.get(
        "/admin/monitoring?section=secrets",
        follow_redirects=True,
    )
    assert "không hợp lệ" in invalid_section.get_data(as_text=True)

    invalid_status = client.get(
        "/admin/monitoring?section=bookings&status=UNKNOWN",
        follow_redirects=True,
    )
    assert "Trạng thái lịch đặt sân không hợp lệ" in invalid_status.get_data(
        as_text=True
    )

    invalid_date = client.get(
        "/admin/monitoring?section=bookings&date=not-a-date",
        follow_redirects=True,
    )
    assert "Ngày lọc phải có định dạng hợp lệ" in invalid_date.get_data(
        as_text=True
    )


def test_admin_monitoring_loads_partial_navigation_assets(app, client):
    admin = create_user(app, email="smooth-monitoring-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    response = client.get("/admin/monitoring?section=bookings")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-admin-monitoring-root" in page
    assert "data-admin-monitoring-status" in page
    assert "/static/js/admin-monitoring.js" in page


def test_admin_monitoring_redirects_legacy_finance_sections(app, client):
    admin = create_user(app, email="legacy-monitor-admin@example.com", role=UserRole.ADMIN)
    login(client, email=admin.email)

    expected_focus = {
        "contributions": "incomplete_deposit",
        "payments": "payment_issue",
        "refunds": "refund_pending",
    }
    for legacy_section, focus in expected_focus.items():
        response = client.get(
            "/admin/monitoring",
            query_string={"section": legacy_section, "venue": 7},
        )
        assert response.status_code == 302
        assert f"section=bookings" in response.location
        assert f"focus={focus}" in response.location
        assert "venue=7" in response.location


def test_admin_match_detail_shows_participant_states_without_private_contacts(
    app,
    client,
):
    admin = create_user(app, email="match-recipient-admin@example.com", role=UserRole.ADMIN)
    owner = create_user(app, email="match-recipient-owner@example.com", role=UserRole.OWNER)
    creator = create_user(app, email="match-recipient-creator@example.com")
    joined_user = create_user(app, email="match-recipient-joined@example.com")
    withdrawn_user = create_user(app, email="match-recipient-withdrawn@example.com")
    booking_code = seed_monitoring_data(app, user_id=creator.id, owner_id=owner.id)

    with app.app_context():
        db.session.get(User, joined_user.id).full_name = "Người đã nhận kèo"
        db.session.get(User, withdrawn_user.id).full_name = "Người đã rút kèo"
        match = db.session.scalar(
            db.select(Match).join(Booking).where(Booking.booking_code == booking_code)
        )
        db.session.add(
            MatchParticipant(
                match_id=match.id,
                user_id=joined_user.id,
                participant_type=MatchParticipantType.PLAYER.value,
                status=MatchParticipantStatus.JOINED.value,
                contact_phone="0901111222",
            )
        )
        db.session.add(
            MatchParticipant(
                match_id=match.id,
                user_id=withdrawn_user.id,
                participant_type=MatchParticipantType.PLAYER.value,
                status=MatchParticipantStatus.WITHDRAWN.value,
                contact_phone="0903333444",
            )
        )
        db.session.commit()
        match_id = match.id

    login(client, email=admin.email)
    response = client.get(f"/admin/matches/{match_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Người đã nhận kèo" in page
    assert "Người đã rút kèo" in page
    assert "Đã tham gia" in page
    assert "Đã rút" in page
    assert "0901111222" not in page
    assert "0903333444" not in page
    assert f"/admin/bookings/{booking_code}" in page
