import click
from flask.cli import AppGroup

from app.services.booking import expire_stale_bookings


bookings_cli = AppGroup(
    "bookings",
    help="Xử lý định kỳ vòng đời booking.",
)


@bookings_cli.command("expire")
def expire() -> None:
    """Expire unpaid reservations whose 15-minute hold has passed."""
    expired_count = expire_stale_bookings()
    click.echo(f"Đã cập nhật {expired_count} booking hết hạn.")
