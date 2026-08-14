from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    CatalogStatus,
    FieldType,
    FieldTypeCode,
    Sport,
    SportCode,
)


class SportCatalogError(ValueError):
    """Raised when a sport or field type is not available in the MVP catalog."""


@dataclass(frozen=True)
class SportSeed:
    code: str
    name: str


@dataclass(frozen=True)
class FieldTypeSeed:
    sport_code: str
    code: str
    name: str
    standard_players_per_side: int | None


SPORT_SEEDS = (
    SportSeed(SportCode.FOOTBALL.value, "Bóng đá"),
    SportSeed(SportCode.BADMINTON.value, "Cầu lông"),
    SportSeed(SportCode.PICKLEBALL.value, "Pickleball"),
    SportSeed(SportCode.TENNIS.value, "Tennis"),
)

FIELD_TYPE_SEEDS = (
    FieldTypeSeed(
        SportCode.FOOTBALL.value,
        FieldTypeCode.FOOTBALL_5.value,
        "Sân bóng đá 5 người",
        5,
    ),
    FieldTypeSeed(
        SportCode.FOOTBALL.value,
        FieldTypeCode.FOOTBALL_7.value,
        "Sân bóng đá 7 người",
        7,
    ),
    FieldTypeSeed(
        SportCode.FOOTBALL.value,
        FieldTypeCode.FOOTBALL_11.value,
        "Sân bóng đá 11 người",
        11,
    ),
    FieldTypeSeed(
        SportCode.BADMINTON.value,
        FieldTypeCode.BADMINTON_STANDARD.value,
        "Sân cầu lông tiêu chuẩn",
        None,
    ),
    FieldTypeSeed(
        SportCode.PICKLEBALL.value,
        FieldTypeCode.PICKLEBALL_STANDARD.value,
        "Sân pickleball tiêu chuẩn",
        None,
    ),
    FieldTypeSeed(
        SportCode.TENNIS.value,
        FieldTypeCode.TENNIS_STANDARD.value,
        "Sân tennis tiêu chuẩn",
        None,
    ),
)


def seed_default_sport_catalog() -> None:
    """Seed the fixed MVP catalog for db.create_all based test databases."""
    existing_sports = {
        sport.code: sport for sport in db.session.scalars(db.select(Sport))
    }
    for seed in SPORT_SEEDS:
        if seed.code not in existing_sports:
            sport = Sport(
                code=seed.code,
                name=seed.name,
                status=CatalogStatus.ACTIVE.value,
            )
            db.session.add(sport)
            existing_sports[seed.code] = sport
    db.session.flush()

    existing_types = {
        field_type.code
        for field_type in db.session.scalars(db.select(FieldType))
    }
    for seed in FIELD_TYPE_SEEDS:
        if seed.code in existing_types:
            continue
        db.session.add(
            FieldType(
                sport_id=existing_sports[seed.sport_code].id,
                code=seed.code,
                name=seed.name,
                standard_players_per_side=seed.standard_players_per_side,
                status=CatalogStatus.ACTIVE.value,
            )
        )
    db.session.flush()


def list_active_sports() -> list[Sport]:
    return list(
        db.session.scalars(
            db.select(Sport)
            .where(Sport.status == CatalogStatus.ACTIVE.value)
            .order_by(Sport.id.asc())
        )
    )


def list_active_field_types(*, sport_code: str | None = None) -> list[FieldType]:
    statement = (
        db.select(FieldType)
        .options(joinedload(FieldType.sport))
        .join(Sport, Sport.id == FieldType.sport_id)
        .where(
            FieldType.status == CatalogStatus.ACTIVE.value,
            Sport.status == CatalogStatus.ACTIVE.value,
        )
        .order_by(Sport.id.asc(), FieldType.id.asc())
    )
    if sport_code:
        statement = statement.where(Sport.code == sport_code)
    return list(db.session.scalars(statement).unique())


def get_active_field_type(code: str) -> FieldType:
    normalized_code = (code or "").strip().upper()
    field_type = db.session.scalar(
        db.select(FieldType)
        .options(joinedload(FieldType.sport))
        .join(Sport, Sport.id == FieldType.sport_id)
        .where(
            FieldType.code == normalized_code,
            FieldType.status == CatalogStatus.ACTIVE.value,
            Sport.status == CatalogStatus.ACTIVE.value,
        )
    )
    if field_type is None:
        raise SportCatalogError("Loại sân không hợp lệ hoặc đã ngừng hoạt động.")
    return field_type


def get_active_sport(code: str) -> Sport:
    normalized_code = (code or "").strip().upper()
    sport = db.session.scalar(
        db.select(Sport).where(
            Sport.code == normalized_code,
            Sport.status == CatalogStatus.ACTIVE.value,
        )
    )
    if sport is None:
        raise SportCatalogError("Bộ môn không hợp lệ hoặc đã ngừng hoạt động.")
    return sport
