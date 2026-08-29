"""Scheduled and administrative Flask CLI commands."""
from flask import Flask

from .bookings import bookings_cli
from .demo import demo_cli
from .matches import matches_cli
from .refunds import refunds_cli
from .users import users_cli


def register_commands(app: Flask) -> None:
    app.cli.add_command(bookings_cli)
    app.cli.add_command(demo_cli)
    app.cli.add_command(matches_cli)
    app.cli.add_command(refunds_cli)
    app.cli.add_command(users_cli)


__all__ = ["register_commands"]
