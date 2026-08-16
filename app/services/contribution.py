from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.extensions import db
from app.models import (
    Booking,
    BookingContribution,
    BookingMode,
    ContributionStatus,
    ContributionType,
)


DEPOSIT_RATE = Decimal("0.3000")


class ContributionError(ValueError):
    """Raised when a booking deposit cannot be allocated safely."""


@dataclass(frozen=True)
class PlannedContribution:
    contribution_type: str
    amount_due: Decimal
    slot_number: int | None = None


@dataclass(frozen=True)
class ContributionPlan:
    booking_mode: str
    deposit_amount: Decimal
    requested_players: int | None
    contributions: tuple[PlannedContribution, ...]

    @property
    def creator_amount(self) -> Decimal:
        return self.contributions[0].amount_due

    @property
    def external_amount(self) -> Decimal:
        return self.deposit_amount - self.creator_amount

    @property
    def external_contributions(self) -> tuple[PlannedContribution, ...]:
        return self.contributions[1:]


def calculate_deposit_amount(total_amount) -> Decimal:
    total = _whole_vnd(total_amount, field_name="Tổng tiền sân")
    deposit = (total * DEPOSIT_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if deposit <= 0 or deposit > total:
        raise ContributionError("Không thể tính khoản cọc hợp lệ.")
    return deposit


def build_contribution_plan(
    *,
    booking_mode: str,
    deposit_amount,
    requested_players: int | None = None,
) -> ContributionPlan:
    """Allocate only the online deposit; venue balance stays outside payments."""
    deposit = _whole_vnd(deposit_amount, field_name="Khoản cọc")
    if booking_mode in {
        BookingMode.DIRECT_BOOKING.value,
        BookingMode.FIND_PLAYERS.value,
    }:
        if booking_mode == BookingMode.FIND_PLAYERS.value:
            requested_players = _positive_integer(
                requested_players,
                field_name="Số người muốn tìm",
            )
        elif requested_players is not None:
            raise ContributionError(
                "Số người muốn tìm chỉ dùng cho hình thức tìm thêm người."
            )
        return ContributionPlan(
            booking_mode=booking_mode,
            deposit_amount=deposit,
            requested_players=requested_players,
            contributions=(
                PlannedContribution(
                    contribution_type=ContributionType.CREATOR.value,
                    amount_due=deposit,
                ),
            ),
        )

    if booking_mode != BookingMode.FIND_OPPONENT.value:
        raise ContributionError("Hình thức đặt sân không hợp lệ.")
    if requested_players is not None:
        raise ContributionError(
            "Số người muốn tìm không áp dụng cho hình thức tìm đối thủ."
        )
    deposit_vnd = int(deposit)
    creator_vnd = deposit_vnd // 2
    opponent_vnd = deposit_vnd - creator_vnd
    if creator_vnd <= 0:
        raise ContributionError("Khoản cọc quá nhỏ để chia cho hai phía.")
    return ContributionPlan(
        booking_mode=booking_mode,
        deposit_amount=deposit,
        requested_players=None,
        contributions=(
            PlannedContribution(
                contribution_type=ContributionType.CREATOR.value,
                amount_due=Decimal(creator_vnd),
            ),
            PlannedContribution(
                contribution_type=ContributionType.OPPONENT.value,
                amount_due=Decimal(opponent_vnd),
                slot_number=1,
            ),
        ),
    )


def add_initial_contributions(
    *,
    booking: Booking,
    creator_user_id: int,
    plan: ContributionPlan,
) -> list[BookingContribution]:
    if Decimal(booking.deposit_amount) != plan.deposit_amount:
        raise ContributionError("Kế hoạch đóng cọc không khớp lịch đặt sân.")
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


def _whole_vnd(value, *, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ContributionError(f"{field_name} không hợp lệ.") from exc
    if amount <= 0 or amount != amount.to_integral_value():
        raise ContributionError(f"{field_name} phải là số nguyên VND lớn hơn 0.")
    return amount.quantize(Decimal("1"))


def _positive_integer(value: int | None, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContributionError(f"{field_name} phải là số nguyên lớn hơn 0.")
    return value
