from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from app.services.geocoding import (
    GeocodingNotFoundError,
    geocode_venue_address,
)


def test_nominatim_geocoder_builds_vietnam_query_and_parses_result(
    app,
    monkeypatch,
):
    captured = {}

    def fake_request_json(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return [
            {
                "lat": "10.7769",
                "lon": "106.7009",
                "display_name": "123 Nguyễn Hữu Thọ, Việt Nam",
            }
        ]

    monkeypatch.setattr(
        "app.services.geocoding._request_json",
        fake_request_json,
    )
    with app.app_context():
        result = geocode_venue_address(
            address="987 Nguyễn Hữu Thọ",
            province_code="79",
            ward_code="27475",
        )

    query = parse_qs(urlparse(captured["request"].full_url).query)
    assert query["countrycodes"] == ["vn"]
    assert query["limit"] == ["1"]
    assert "Phường Tân Hưng" in query["q"][0]
    assert captured["request"].get_header("User-agent")
    assert captured["timeout"] == 5.0
    assert result.latitude == Decimal("10.776900")
    assert result.longitude == Decimal("106.700900")


def test_nominatim_geocoder_reports_no_result_without_default_coordinates(
    app,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.geocoding._request_json",
        lambda request, timeout: [],
    )

    with app.app_context(), pytest.raises(GeocodingNotFoundError) as error:
        geocode_venue_address(
            address="988 Nguyễn Hữu Thọ",
            province_code="79",
            ward_code="27475",
        )

    assert "đặt ghim thủ công" in str(error.value)
