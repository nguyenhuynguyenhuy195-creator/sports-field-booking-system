from app.models import (
    Booking,
    BookingPaymentMode,
    BookingPriceDetail,
    BookingStatus,
)


def test_booking_enum_contract_matches_documentation():
    assert {mode.value for mode in BookingPaymentMode} == {
        "FULL_PAYMENT",
        "SPLIT_OPPONENT",
        "SPLIT_PLAYERS",
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
    assert "ck_bookings_paid_amount_range" in booking_constraints
    assert "ck_booking_price_details_duration_positive" in detail_constraints
    assert "ix_bookings_field_date_status_time" in booking_indexes
    assert "ix_bookings_user_created" in booking_indexes
    assert "ix_bookings_status_initial_payment_due" in booking_indexes
