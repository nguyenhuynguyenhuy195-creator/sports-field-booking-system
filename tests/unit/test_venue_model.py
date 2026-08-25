from app.models import Venue, VenueStatus


def test_venue_status_values_match_database_contract():
    assert {status.value for status in VenueStatus} == {
        "PENDING",
        "ACTIVE",
        "HIDDEN",
        "INACTIVE",
    }


def test_venue_table_has_status_and_operating_hour_constraints():
    constraint_names = {
        constraint.name for constraint in Venue.__table__.constraints
    }

    assert "ck_venues_status" in constraint_names
    assert "ck_venues_opening_before_closing" in constraint_names
    assert "ck_venues_latitude_range" in constraint_names
    assert "ck_venues_longitude_range" in constraint_names
    assert "ck_venues_coordinate_pair" in constraint_names


def test_venue_table_has_owner_and_public_listing_indexes():
    index_names = {index.name for index in Venue.__table__.indexes}

    assert "ix_venues_owner_created" in index_names
    assert "ix_venues_status_city" in index_names
    assert "ix_venues_status_province_ward" in index_names


def test_full_address_prefers_structured_administrative_units():
    venue = Venue(
        address="123 Nguyễn Hữu Thọ",
        district="Quận 7",
        city="TP. Hồ Chí Minh",
        ward_name="Phường Tân Hưng",
        province_name="Thành phố Hồ Chí Minh",
    )

    assert venue.full_address == (
        "123 Nguyễn Hữu Thọ, Phường Tân Hưng, Thành phố Hồ Chí Minh"
    )


def test_full_address_keeps_legacy_venue_readable():
    venue = Venue(
        address="25 Nguyễn Tất Thành",
        district="Quận Thanh Khê",
        city="Đà Nẵng",
    )

    assert venue.full_address == "25 Nguyễn Tất Thành, Quận Thanh Khê, Đà Nẵng"
