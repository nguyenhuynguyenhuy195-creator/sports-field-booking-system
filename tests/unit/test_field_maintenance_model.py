from app.models import FieldMaintenance, FieldMaintenanceStatus


def test_field_maintenance_status_contract_matches_documentation():
    assert {status.value for status in FieldMaintenanceStatus} == {
        "ACTIVE",
        "CANCELLED",
        "COMPLETED",
    }


def test_field_maintenance_table_has_required_constraints():
    constraint_names = {
        constraint.name for constraint in FieldMaintenance.__table__.constraints
    }

    assert "ck_field_maintenances_start_before_end" in constraint_names
    assert "ck_field_maintenances_status" in constraint_names


def test_field_maintenance_table_has_lookup_index():
    index_names = {index.name for index in FieldMaintenance.__table__.indexes}

    assert "ix_field_maintenances_field_date_status_time" in index_names
