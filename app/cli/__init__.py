"""Scheduled and administrative Flask CLI commands."""
from flask import Flask

from .users import users_cli


def register_commands(app: Flask) -> None:
    app.cli.add_command(users_cli)


__all__ = ["register_commands"]
