from app.models import DAY_OF_WEEK_LABELS, FieldPriceSlot, PriceSlotStatus


def test_price_slot_contract_matches_documentation():
    assert set(DAY_OF_WEEK_LABELS) == set(range(7))
    assert {status.value for status in PriceSlotStatus} == {
        "ACTIVE",
        "INACTIVE",
    }


def test_price_slot_table_has_required_constraints():
    constraint_names = {
        constraint.name for constraint in FieldPriceSlot.__table__.constraints
    }

    assert "ck_price_slots_day_of_week" in constraint_names
    assert "ck_price_slots_start_before_end" in constraint_names
    assert "ck_price_slots_hourly_price_positive" in constraint_names
    assert "ck_price_slots_status" in constraint_names


def test_price_slot_table_has_lookup_index():
    index_names = {index.name for index in FieldPriceSlot.__table__.indexes}

    assert "ix_price_slots_field_day_status_time" in index_names
