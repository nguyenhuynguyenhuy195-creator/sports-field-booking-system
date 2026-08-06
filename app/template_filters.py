from datetime import datetime, timedelta, timezone

from flask import Flask


VIETNAM_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def local_datetime(value: datetime | None) -> str:
    """Format a naive UTC database timestamp in Vietnam local time."""
    if value is None:
        return "—"
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return utc_value.astimezone(VIETNAM_TIMEZONE).strftime("%d/%m/%Y %H:%M")


def register_template_filters(app: Flask) -> None:
    app.add_template_filter(local_datetime, "local_datetime")
