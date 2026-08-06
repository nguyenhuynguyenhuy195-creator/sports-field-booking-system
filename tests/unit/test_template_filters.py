from datetime import datetime

from app.template_filters import local_datetime


def test_local_datetime_converts_utc_to_vietnam_time():
    utc_timestamp = datetime(2026, 8, 6, 17, 29)

    assert local_datetime(utc_timestamp) == "07/08/2026 00:29"


def test_local_datetime_handles_missing_value():
    assert local_datetime(None) == "—"
