from app.models import (
    CatalogStatus,
    Field,
    FieldStatus,
    FieldType,
    FieldTypeCode,
    Sport,
    SportCode,
)


def test_multisport_catalog_enums_match_database_contract():
    assert {sport.value for sport in SportCode} == {
        "FOOTBALL",
        "BADMINTON",
        "PICKLEBALL",
        "TENNIS",
    }
    assert {field_type.value for field_type in FieldTypeCode} == {
        "FOOTBALL_5",
        "FOOTBALL_7",
        "FOOTBALL_11",
        "BADMINTON_STANDARD",
        "PICKLEBALL_STANDARD",
        "TENNIS_STANDARD",
    }
    assert {status.value for status in CatalogStatus} == {"ACTIVE", "INACTIVE"}
    assert {status.value for status in FieldStatus} == {"ACTIVE", "INACTIVE"}


def test_catalog_and_field_tables_have_required_constraints():
    sport_constraints = {item.name for item in Sport.__table__.constraints}
    type_constraints = {item.name for item in FieldType.__table__.constraints}
    field_constraints = {item.name for item in Field.__table__.constraints}

    assert "ck_sports_status" in sport_constraints
    assert "ck_field_types_players_per_side_positive" in type_constraints
    assert "ck_field_types_status" in type_constraints
    assert "uq_field_types_sport_name" in type_constraints
    assert "ck_fields_capacity_positive" in field_constraints
    assert "ck_fields_status" in field_constraints
    assert "uq_fields_venue_name" in field_constraints
    assert "ck_fields_type" not in field_constraints


def test_field_table_has_catalog_and_public_listing_indexes():
    index_names = {index.name for index in Field.__table__.indexes}

    assert "ix_fields_venue_status" in index_names
    assert "ix_fields_field_type_status" in index_names
