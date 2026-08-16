from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

from flask import Flask


VIETNAM_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def local_datetime(value: datetime | None) -> str:
    """Format a naive UTC database timestamp in Vietnam local time."""
    if value is None:
        return "—"
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return utc_value.astimezone(VIETNAM_TIMEZONE).strftime("%d/%m/%Y %H:%M")


def vnd_currency(value) -> str:
    """Format a database amount as whole Vietnamese đồng for display."""
    if value is None:
        return "—"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    formatted = f"{amount:,.0f}".replace(",", ".")
    return f"{formatted} đ"


def phone_digits(value: str | None) -> str:
    """Return digits only for tel/Zalo links without changing displayed text."""
    return re.sub(r"\D", "", value or "")


def register_template_filters(app: Flask) -> None:
    app.add_template_filter(local_datetime, "local_datetime")
    app.add_template_filter(vnd_currency, "vnd_currency")
    app.add_template_filter(phone_digits, "phone_digits")
