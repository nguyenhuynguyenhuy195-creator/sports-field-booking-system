from app.models import (
    BookingContribution,
    ContributionStatus,
    ContributionType,
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
)


def test_payment_foundation_enums_match_database_contract():
    assert {item.value for item in ContributionType} == {
        "CREATOR",
        "OPPONENT",
        "PLAYER",
        "TOP_UP",
    }
    assert "WAIVED" in {item.value for item in ContributionStatus}
    assert {item.value for item in PaymentProvider} == {"MOCK", "MOMO"}
    assert {item.value for item in PaymentMethod} == {
        "SIMULATED",
        "MOMO_WALLET",
    }
    assert {item.value for item in PaymentStatus} == {
        "PENDING",
        "SUCCESS",
        "FAILED",
        "CANCELLED",
        "EXPIRED",
    }
    assert {item.value for item in RefundStatus} == {
        "PENDING",
        "PROCESSING",
        "SUCCESS",
        "FAILED",
    }


def test_payment_foundation_has_money_checks_and_filtered_indexes():
    contribution_constraints = {
        item.name for item in BookingContribution.__table__.constraints
    }
    payment_constraints = {item.name for item in Payment.__table__.constraints}
    refund_constraints = {item.name for item in Refund.__table__.constraints}
    contribution_indexes = {
        item.name for item in BookingContribution.__table__.indexes
    }
    payment_indexes = {item.name for item in Payment.__table__.indexes}
    refund_indexes = {item.name for item in Refund.__table__.indexes}

    assert "ck_booking_contributions_amount_paid_range" in contribution_constraints
    assert "ck_booking_contributions_slot_number" in contribution_constraints
    assert "uq_booking_contributions_external_slot" in contribution_indexes
    assert "ck_payments_amount_positive" in payment_constraints
    assert "uq_payments_success_contribution" in payment_indexes
    assert "uq_payments_provider_trans_id_not_null" in payment_indexes
    assert "ck_refunds_amount_positive" in refund_constraints
    assert "uq_refunds_provider_trans_id_not_null" in refund_indexes
