from app.models import Field, FieldStatus, FieldType


def test_field_enums_match_database_contract():
    assert {field_type.value for field_type in FieldType} == {
        "FIVE_A_SIDE",
        "SEVEN_A_SIDE",
        "ELEVEN_A_SIDE",
    }
    assert {status.value for status in FieldStatus} == {
        "ACTIVE",
        "INACTIVE",
    }


def test_field_table_has_required_constraints():
    constraint_names = {
        constraint.name for constraint in Field.__table__.constraints
    }

    assert "ck_fields_type" in constraint_names
    assert "ck_fields_capacity_positive" in constraint_names
    assert "ck_fields_status" in constraint_names
    assert "uq_fields_venue_name" in constraint_names


def test_field_table_has_public_listing_index():
    index_names = {index.name for index in Field.__table__.indexes}

    assert "ix_fields_venue_status" in index_names
