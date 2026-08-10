import click
from flask.cli import AppGroup

from app.services.refund import process_overdue_funding_refunds


refunds_cli = AppGroup(
    "refunds",
    help="Xử lý định kỳ chính sách hoàn tiền.",
)


@refunds_cli.command("funding-expire")
def funding_expire() -> None:
    """Refund split bookings that missed their 12-hour funding deadline."""
    processed_count = process_overdue_funding_refunds()
    click.echo(f"Đã xử lý hoàn tiền cho {processed_count} booking thiếu tiền.")
