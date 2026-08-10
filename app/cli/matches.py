import click
from flask.cli import AppGroup

from app.services.matchmaking import expire_stale_match_participants


matches_cli = AppGroup(
    "matches",
    help="Xử lý định kỳ yêu cầu tham gia kèo.",
)


@matches_cli.command("expire")
def expire() -> None:
    """Release accepted requests after their 15-minute payment deadline."""
    expired_count = expire_stale_match_participants()
    click.echo(f"Đã cập nhật {expired_count} yêu cầu tham gia hết hạn.")
