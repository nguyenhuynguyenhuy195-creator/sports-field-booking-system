from __future__ import annotations

from collections import Counter
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.extensions import db
from app.models import Province, Ward


class AdministrativeUnitError(ValueError):
    """Raised when an administrative unit selection is invalid."""


@dataclass(frozen=True)
class AdministrativeAddress:
    province: Province
    ward: Ward


@lru_cache(maxsize=1)
def load_administrative_catalog_data() -> dict:
    catalog_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "vietnam_administrative_units_2025.json"
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    provinces = catalog["provinces"]
    wards = catalog["wards"]
    province_codes = {item["code"] for item in provinces}
    ward_codes = {item["code"] for item in wards}
    type_counts = Counter(item["type"] for item in wards)
    if (
        len(provinces) != 34
        or len(province_codes) != 34
        or len(wards) != 3321
        or len(ward_codes) != 3321
        or type_counts != Counter({"XA": 2621, "PHUONG": 687, "DAC_KHU": 13})
        or any(item["province_code"] not in province_codes for item in wards)
    ):
        raise AdministrativeUnitError(
            "Snapshot danh mục hành chính không đầy đủ hoặc không nhất quán."
        )
    return catalog


def seed_administrative_catalog() -> None:
    """Seed the immutable two-level catalog idempotently for fresh databases."""
    catalog = load_administrative_catalog_data()
    provinces = catalog["provinces"]
    wards = catalog["wards"]

    existing_provinces = {
        item.code: item
        for item in db.session.scalars(db.select(Province))
    }
    for item in provinces:
        existing = existing_provinces.get(item["code"])
        if existing is not None and existing.name != item["name"]:
            raise AdministrativeUnitError(
                f"Danh mục tỉnh/thành phố mã {item['code']} không đồng nhất."
            )
    missing_provinces = [
        item for item in provinces if item["code"] not in existing_provinces
    ]
    if missing_provinces:
        db.session.execute(db.insert(Province), missing_provinces)

    existing_wards = {
        item.code: item for item in db.session.scalars(db.select(Ward))
    }
    for item in wards:
        existing = existing_wards.get(item["code"])
        if existing is not None and (
            existing.province_code != item["province_code"]
            or existing.name != item["name"]
            or existing.type != item["type"]
        ):
            raise AdministrativeUnitError(
                f"Danh mục phường/xã mã {item['code']} không đồng nhất."
            )
    missing_wards = [item for item in wards if item["code"] not in existing_wards]
    if missing_wards:
        db.session.execute(db.insert(Ward), missing_wards)


def list_provinces() -> tuple[Province, ...]:
    return tuple(
        db.session.scalars(db.select(Province).order_by(Province.name.asc()))
    )


def list_wards(*, province_code: str) -> tuple[Ward, ...]:
    normalized_province_code = (province_code or "").strip()
    if not normalized_province_code:
        raise AdministrativeUnitError("Vui lòng chọn tỉnh hoặc thành phố.")
    if db.session.get(Province, normalized_province_code) is None:
        raise AdministrativeUnitError("Tỉnh hoặc thành phố không hợp lệ.")
    return tuple(
        db.session.scalars(
            db.select(Ward)
            .where(Ward.province_code == normalized_province_code)
            .order_by(Ward.name.asc(), Ward.code.asc())
        )
    )


def resolve_administrative_address(
    *,
    province_code: str,
    ward_code: str,
) -> AdministrativeAddress:
    normalized_province_code = (province_code or "").strip()
    normalized_ward_code = (ward_code or "").strip()
    province = db.session.get(Province, normalized_province_code)
    if province is None:
        raise AdministrativeUnitError("Tỉnh hoặc thành phố không hợp lệ.")
    ward = db.session.get(Ward, normalized_ward_code)
    if ward is None:
        raise AdministrativeUnitError("Phường, xã hoặc đặc khu không hợp lệ.")
    if ward.province_code != province.code:
        raise AdministrativeUnitError(
            "Phường, xã hoặc đặc khu không thuộc tỉnh/thành phố đã chọn."
        )
    return AdministrativeAddress(province=province, ward=ward)
