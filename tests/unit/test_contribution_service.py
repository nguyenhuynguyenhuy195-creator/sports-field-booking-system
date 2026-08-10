from decimal import Decimal

import pytest

from app.models import BookingPaymentMode, ContributionType
from app.services import ContributionError, build_contribution_plan


def test_full_payment_allocates_everything_to_creator():
    plan = build_contribution_plan(
        payment_mode=BookingPaymentMode.FULL_PAYMENT.value,
        total_amount=Decimal("400000"),
    )

    assert plan.creator_amount == Decimal("400000")
    assert plan.external_amount == Decimal("0")
    assert len(plan.contributions) == 1


def test_opponent_split_keeps_exact_total_when_amount_is_odd():
    plan = build_contribution_plan(
        payment_mode=BookingPaymentMode.SPLIT_OPPONENT.value,
        total_amount=Decimal("400001"),
    )

    assert [part.amount_due for part in plan.contributions] == [
        Decimal("200000"),
        Decimal("200001"),
    ]
    assert sum(part.amount_due for part in plan.contributions) == plan.total_amount


def test_player_split_assigns_rounding_remainder_to_last_external_player():
    plan = build_contribution_plan(
        payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
        total_amount=Decimal("1000003"),
        total_players=10,
        required_players=3,
    )

    assert plan.existing_players == 7
    assert plan.creator_amount == Decimal("700000")
    assert [part.contribution_type for part in plan.external_contributions] == [
        ContributionType.PLAYER.value,
        ContributionType.PLAYER.value,
        ContributionType.PLAYER.value,
    ]
    assert [part.amount_due for part in plan.external_contributions] == [
        Decimal("100000"),
        Decimal("100000"),
        Decimal("100003"),
    ]
    assert sum(part.amount_due for part in plan.contributions) == plan.total_amount


@pytest.mark.parametrize("required_players", [None, 0, 10, 11])
def test_player_split_rejects_invalid_missing_player_count(required_players):
    with pytest.raises(ContributionError):
        build_contribution_plan(
            payment_mode=BookingPaymentMode.SPLIT_PLAYERS.value,
            total_amount=Decimal("400000"),
            total_players=10,
            required_players=required_players,
        )
