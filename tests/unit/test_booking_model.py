from app.models import (
    Booking,
    BookingMode,
    BookingPaymentPolicy,
    BookingPriceDetail,
    BookingStatus,
    PlayFormat,
)


def test_booking_enum_contract_matches_documentation():
    assert {mode.value for mode in BookingMode} == {
        "DIRECT_BOOKING",
        "FIND_OPPONENT",
        "FIND_PLAYERS",
    }
    assert {item.value for item in PlayFormat} == {"SINGLES", "DOUBLES"}
    assert {item.value for item in BookingPaymentPolicy} == {
        "LEGACY_FULL_ONLINE",
        "DEPOSIT_30",
    }
    assert {status.value for status in BookingStatus} == {
        "PENDING",
        "CONFIRMED",
        "PARTIALLY_PAID",
        "PAID",
        "REFUND_PENDING",
        "COMPLETED",
        "REJECTED",
        "CANCELLED",
        "EXPIRED",
    }


def test_booking_tables_have_required_constraints_and_indexes():
    booking_constraints = {
        constraint.name for constraint in Booking.__table__.constraints
    }
    detail_constraints = {
        constraint.name for constraint in BookingPriceDetail.__table__.constraints
    }
    booking_indexes = {index.name for index in Booking.__table__.indexes}

    assert "ck_bookings_start_before_end" in booking_constraints
    assert "ck_bookings_total_amount_positive" in booking_constraints
    assert "ck_bookings_deposit_rate" in booking_constraints
    assert "ck_bookings_deposit_amount_range" in booking_constraints
    assert "ck_bookings_paid_amount_range" in booking_constraints
    assert "ck_bookings_requested_players" in booking_constraints
    assert "ck_booking_price_details_duration_positive" in detail_constraints
    assert "ix_bookings_field_date_status_time" in booking_indexes
    assert "ix_bookings_user_created" in booking_indexes
    assert "ix_bookings_status_initial_payment_due" in booking_indexes
    assert "ix_bookings_status_matchmaking_deadline" in booking_indexes
