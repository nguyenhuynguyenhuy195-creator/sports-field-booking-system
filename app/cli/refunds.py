import click
from flask.cli import AppGroup

from app.services.refund import (
    process_overdue_funding_refunds,
    process_pending_momo_refunds,
    process_pending_vnpay_refunds,
)


refunds_cli = AppGroup(
    "refunds",
    help="Xử lý định kỳ chính sách hoàn tiền.",
)


@refunds_cli.command("funding-expire")
def funding_expire() -> None:
    """Refund split bookings that missed their 12-hour funding deadline."""
    processed_count = process_overdue_funding_refunds()
    click.echo(f"Đã xử lý hoàn tiền cho {processed_count} booking thiếu tiền.")


@refunds_cli.command("momo-pending")
def momo_pending() -> None:
    """Submit or query durable MoMo Sandbox refund records."""
    succeeded_count = process_pending_momo_refunds()
    click.echo(f"Đã hoàn tất {succeeded_count} yêu cầu hoàn tiền MoMo.")


@refunds_cli.command("vnpay-pending")
def vnpay_pending() -> None:
    """Submit durable VNPAY Sandbox refund records still PENDING/PROCESSING."""
    succeeded_count = process_pending_vnpay_refunds()
    click.echo(f"Đã hoàn tất {succeeded_count} yêu cầu hoàn tiền VNPAY.")
