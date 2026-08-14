from decimal import Decimal

import pytest

from app.models import BookingMode, ContributionType
from app.services import (
    ContributionError,
    build_contribution_plan,
    calculate_deposit_amount,
)


def test_deposit_is_thirty_percent_rounded_to_whole_vnd():
    assert calculate_deposit_amount(Decimal("400001")) == Decimal("120000")
    assert calculate_deposit_amount(Decimal("400002")) == Decimal("120001")


def test_direct_booking_allocates_entire_deposit_to_creator():
    plan = build_contribution_plan(
        booking_mode=BookingMode.DIRECT_BOOKING.value,
        deposit_amount=Decimal("120000"),
    )

    assert plan.creator_amount == Decimal("120000")
    assert plan.external_amount == Decimal("0")
    assert len(plan.contributions) == 1


def test_opponent_mode_splits_deposit_exactly_when_amount_is_odd():
    plan = build_contribution_plan(
        booking_mode=BookingMode.FIND_OPPONENT.value,
        deposit_amount=Decimal("120001"),
    )

    assert [part.amount_due for part in plan.contributions] == [
        Decimal("60000"),
        Decimal("60001"),
    ]
    assert sum(part.amount_due for part in plan.contributions) == plan.deposit_amount
    assert plan.external_contributions[0].contribution_type == ContributionType.OPPONENT.value


def test_find_players_charges_only_creator_and_keeps_requested_count():
    plan = build_contribution_plan(
        booking_mode=BookingMode.FIND_PLAYERS.value,
        deposit_amount=Decimal("300000"),
        requested_players=3,
    )

    assert plan.creator_amount == Decimal("300000")
    assert plan.external_amount == Decimal("0")
    assert plan.requested_players == 3
    assert plan.external_contributions == ()


@pytest.mark.parametrize("requested_players", [None, 0, -1])
def test_find_players_requires_positive_requested_count(requested_players):
    with pytest.raises(ContributionError):
        build_contribution_plan(
            booking_mode=BookingMode.FIND_PLAYERS.value,
            deposit_amount=Decimal("120000"),
            requested_players=requested_players,
        )
