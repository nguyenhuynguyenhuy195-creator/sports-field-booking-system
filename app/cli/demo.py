import click
from flask import current_app
from flask.cli import AppGroup

from app.services.demo_data import (
    DemoDataError,
    reset_and_seed_demo_business_data,
)


demo_cli = AppGroup(
    "demo",
    help="Manage demonstration data in the development environment.",
)


@demo_cli.command("reset-business-data")
@click.option(
    "--yes",
    is_flag=True,
    help="Confirm the reset without an interactive prompt.",
)
def reset_business_data(yes: bool) -> None:
    """Delete dependent demo records and seed one structured venue dataset."""
    if current_app.config.get("APP_ENV_NAME") != "development":
        raise click.ClickException(
            "This command requires APP_ENV=development."
        )
    if not yes and not click.confirm(
        "Reset current Venue/Booking/Payment/Match demo data?"
    ):
        click.echo("Demo data reset cancelled.")
        return

    try:
        summary = reset_and_seed_demo_business_data()
    except DemoDataError as exc:
        raise click.ClickException("Demo data reset failed.") from exc

    removed_total = sum(summary.removed_counts.values())
    click.echo(f"Removed {removed_total} dependent demo business records.")
    click.echo(
        "Created one demo Venue with normalized Province/Ward: "
        f"#{summary.venue_id}."
    )
    click.echo(
        "Venue is PENDING without Google Maps data; the owner must select "
        "a valid location before Admin activation."
    )
