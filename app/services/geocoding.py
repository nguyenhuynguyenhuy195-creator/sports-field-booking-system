from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from app.services.administrative_unit import (
    AdministrativeUnitError,
    resolve_administrative_address,
)


class GeocodingError(ValueError):
    """Base error safe to show to an Owner."""


class GeocodingNotFoundError(GeocodingError):
    """Raised when the provider has no result for the supplied address."""


class GeocodingProviderError(GeocodingError):
    """Raised when the configured provider is unavailable or invalid."""


@dataclass(frozen=True)
class GeocodingResult:
    latitude: Decimal
    longitude: Decimal
    display_name: str
    query: str


_cache: dict[str, tuple[float, GeocodingResult]] = {}
_cache_lock = Lock()
_request_lock = Lock()
_last_request_at = 0.0
_MAX_RESPONSE_BYTES = 256 * 1024
_MAX_CACHE_ENTRIES = 256


def geocode_venue_address(
    *,
    address: str,
    province_code: str,
    ward_code: str,
) -> GeocodingResult:
    """Resolve a structured Venue address through the configured provider."""
    normalized_address = (address or "").strip()
    if len(normalized_address) < 5 or len(normalized_address) > 255:
        raise GeocodingError("Địa chỉ phải từ 5 đến 255 ký tự.")
    try:
        administrative_address = resolve_administrative_address(
            province_code=province_code,
            ward_code=ward_code,
        )
    except AdministrativeUnitError as exc:
        raise GeocodingError(str(exc)) from exc

    query = ", ".join(
        (
            normalized_address,
            administrative_address.ward.full_name,
            administrative_address.province.name,
            "Việt Nam",
        )
    )
    provider = str(current_app.config.get("GEOCODING_PROVIDER", "")).lower()
    if provider != "nominatim":
        raise GeocodingProviderError(
            "Dịch vụ tìm vị trí chưa được cấu hình hợp lệ."
        )
    return _geocode_with_nominatim(query)


def _geocode_with_nominatim(query: str) -> GeocodingResult:
    cache_key = query.casefold()
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    base_url = str(current_app.config["NOMINATIM_BASE_URL"]).rstrip("/")
    user_agent = str(current_app.config["NOMINATIM_USER_AGENT"]).strip()
    if not base_url.startswith("https://") or not user_agent:
        raise GeocodingProviderError(
            "Dịch vụ tìm vị trí chưa được cấu hình hợp lệ."
        )
    parameters = urlencode(
        {
            "format": "jsonv2",
            "q": query,
            "countrycodes": "vn",
            "limit": 1,
            "addressdetails": 1,
        }
    )
    request = Request(
        f"{base_url}/search?{parameters}",
        headers={
            "Accept": "application/json",
            "Accept-Language": "vi",
            "User-Agent": user_agent,
        },
    )
    timeout = min(
        max(float(current_app.config["GEOCODING_TIMEOUT_SECONDS"]), 1.0),
        10.0,
    )
    try:
        payload = _request_json(request, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        current_app.logger.warning(
            "Nominatim geocoding request failed: %s", type(exc).__name__
        )
        raise GeocodingProviderError(
            "Không thể kết nối dịch vụ tìm vị trí. Bạn vẫn có thể đặt ghim thủ công trên bản đồ."
        ) from exc

    if not isinstance(payload, list) or not payload:
        raise GeocodingNotFoundError(
            "Không tìm thấy vị trí phù hợp. Hãy kiểm tra địa chỉ hoặc đặt ghim thủ công trên bản đồ."
        )
    try:
        first = payload[0]
        latitude = _parse_coordinate(first["lat"], minimum=-90, maximum=90)
        longitude = _parse_coordinate(first["lon"], minimum=-180, maximum=180)
        display_name = str(first.get("display_name") or query).strip()
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        current_app.logger.warning("Nominatim returned an invalid result")
        raise GeocodingProviderError(
            "Dịch vụ tìm vị trí trả về dữ liệu không hợp lệ. Hãy đặt ghim thủ công trên bản đồ."
        ) from exc

    result = GeocodingResult(
        latitude=latitude,
        longitude=longitude,
        display_name=display_name[:500],
        query=query,
    )
    _store_cached(cache_key, result)
    return result


def _request_json(request: Request, *, timeout: float):
    global _last_request_at
    with _request_lock:
        wait_seconds = 1.0 - (monotonic() - _last_request_at)
        if wait_seconds > 0:
            sleep(wait_seconds)
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(_MAX_RESPONSE_BYTES + 1)
        finally:
            _last_request_at = monotonic()
    if len(body) > _MAX_RESPONSE_BYTES:
        raise ValueError("Geocoding response is too large")
    return json.loads(body.decode("utf-8"))


def _parse_coordinate(value, *, minimum: int, maximum: int) -> Decimal:
    coordinate = Decimal(str(value))
    if not coordinate.is_finite() or not minimum <= coordinate <= maximum:
        raise ValueError("Coordinate is outside the valid range")
    return coordinate.quantize(Decimal("0.000001"))


def _get_cached(key: str) -> GeocodingResult | None:
    ttl = max(int(current_app.config["GEOCODING_CACHE_TTL_SECONDS"]), 0)
    with _cache_lock:
        cached = _cache.get(key)
        if cached is None:
            return None
        stored_at, result = cached
        if monotonic() - stored_at <= ttl:
            return result
        _cache.pop(key, None)
    return None


def _store_cached(key: str, result: GeocodingResult) -> None:
    with _cache_lock:
        if len(_cache) >= _MAX_CACHE_ENTRIES:
            oldest_key = min(_cache, key=lambda item: _cache[item][0])
            _cache.pop(oldest_key, None)
        _cache[key] = (monotonic(), result)
