from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingPaymentMode,
    ContributionStatus,
    ContributionType,
)


class ContributionError(ValueError):
    """Raised when a booking cost cannot be allocated safely."""


@dataclass(frozen=True)
class PlannedContribution:
    contribution_type: str
    amount_due: Decimal
    slot_number: int | None = None


@dataclass(frozen=True)
class ContributionPlan:
    payment_mode: str
    total_amount: Decimal
    total_players: int | None
    required_players: int | None
    existing_players: int | None
    contributions: tuple[PlannedContribution, ...]

    @property
    def creator_amount(self) -> Decimal:
        return self.contributions[0].amount_due

    @property
    def external_amount(self) -> Decimal:
        return self.total_amount - self.creator_amount

    @property
    def external_contributions(self) -> tuple[PlannedContribution, ...]:
        return self.contributions[1:]


def build_contribution_plan(
    *,
    payment_mode: str,
    total_amount,
    total_players: int | None = None,
    required_players: int | None = None,
) -> ContributionPlan:
    """Return an integer-VND plan whose parts add up to the booking total."""
    total = _whole_vnd(total_amount)
    if payment_mode == BookingPaymentMode.FULL_PAYMENT.value:
        _reject_player_configuration(total_players, required_players)
        parts = (
            PlannedContribution(
                contribution_type=ContributionType.CREATOR.value,
                amount_due=total,
            ),
        )
        return ContributionPlan(payment_mode, total, None, None, None, parts)

    if payment_mode == BookingPaymentMode.SPLIT_OPPONENT.value:
        _reject_player_configuration(total_players, required_players)
        total_vnd = int(total)
        creator_vnd = total_vnd // 2
        opponent_vnd = total_vnd - creator_vnd
        if creator_vnd <= 0:
            raise ContributionError("Tổng tiền quá nhỏ để chia cho hai đội.")
        parts = (
            PlannedContribution(
                contribution_type=ContributionType.CREATOR.value,
                amount_due=Decimal(creator_vnd),
            ),
            PlannedContribution(
                contribution_type=ContributionType.OPPONENT.value,
                amount_due=Decimal(opponent_vnd),
                slot_number=1,
            ),
        )
        return ContributionPlan(payment_mode, total, None, None, None, parts)

    if payment_mode != BookingPaymentMode.SPLIT_PLAYERS.value:
        raise ContributionError("Hình thức chia tiền không hợp lệ.")

    normalized_total_players = _positive_integer(
        total_players,
        field_name="Tổng số người",
    )
    normalized_required_players = _positive_integer(
        required_players,
        field_name="Số người còn thiếu",
    )
    if normalized_total_players <= 1:
        raise ContributionError("Tổng số người phải lớn hơn 1.")
    if normalized_required_players >= normalized_total_players:
        raise ContributionError(
            "Số người còn thiếu phải nhỏ hơn tổng sức chứa của sân."
        )

    existing_players = normalized_total_players - normalized_required_players
    base_share, remainder = divmod(int(total), normalized_total_players)
    if base_share <= 0:
        raise ContributionError("Tổng tiền quá nhỏ để chia theo đầu người.")

    player_shares = [base_share] * normalized_total_players
    player_shares[-1] += remainder
    creator_amount = Decimal(sum(player_shares[:existing_players]))
    external_shares = player_shares[existing_players:]
    parts = [
        PlannedContribution(
            contribution_type=ContributionType.CREATOR.value,
            amount_due=creator_amount,
        )
    ]
    parts.extend(
        PlannedContribution(
            contribution_type=ContributionType.PLAYER.value,
            amount_due=Decimal(amount),
            slot_number=index,
        )
        for index, amount in enumerate(external_shares, start=1)
    )
    plan = ContributionPlan(
        payment_mode=payment_mode,
        total_amount=total,
        total_players=normalized_total_players,
        required_players=normalized_required_players,
        existing_players=existing_players,
        contributions=tuple(parts),
    )
    if sum((part.amount_due for part in plan.contributions), Decimal("0")) != total:
        raise ContributionError("Không thể phân bổ chính xác tổng tiền booking.")
    return plan


def add_initial_contributions(
    *,
    booking: Booking,
    creator_user_id: int,
    plan: ContributionPlan,
) -> list[BookingContribution]:
    """Attach the immutable initial allocation before the booking transaction commits."""
    if Decimal(booking.total_amount) != plan.total_amount:
        raise ContributionError("Kế hoạch đóng góp không khớp tổng tiền booking.")
    records: list[BookingContribution] = []
    for index, part in enumerate(plan.contributions):
        record = BookingContribution(
            booking_id=booking.id,
            user_id=creator_user_id if index == 0 else None,
            contribution_type=part.contribution_type,
            slot_number=part.slot_number,
            amount_due=part.amount_due,
            amount_paid=Decimal("0.00"),
            status=ContributionStatus.PENDING.value,
            expires_at=booking.initial_payment_due_at if index == 0 else None,
        )
        db.session.add(record)
        records.append(record)
    return records


def _whole_vnd(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ContributionError("Tổng tiền booking không hợp lệ.") from exc
    if amount <= 0 or amount != amount.to_integral_value():
        raise ContributionError("Tổng tiền phải là số nguyên VND lớn hơn 0.")
    return amount.quantize(Decimal("1"))


def _positive_integer(value: int | None, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContributionError(f"{field_name} phải là số nguyên lớn hơn 0.")
    return value


def _reject_player_configuration(
    total_players: int | None,
    required_players: int | None,
) -> None:
    if total_players is not None or required_players is not None:
        raise ContributionError(
            "Chỉ hình thức chia theo đầu người mới nhận số người còn thiếu."
        )
