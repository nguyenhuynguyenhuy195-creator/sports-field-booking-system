"""add multisport catalog and venue location

Revision ID: b2e91c4a7d10
Revises: 7c4e2a1b9d60
Create Date: 2026-08-12 23:55:00.000000

"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = "b2e91c4a7d10"
down_revision = "7c4e2a1b9d60"
branch_labels = None
depends_on = None


timestamp_type = sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")


def upgrade():
    op.create_table(
        "sports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.Unicode(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("created_at", timestamp_type, nullable=False),
        sa.Column("updated_at", timestamp_type, nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_sports_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_sports_code"),
        sa.UniqueConstraint("name", name="uq_sports_name"),
    )
    op.create_table(
        "field_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sport_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.Unicode(length=100), nullable=False),
        sa.Column("standard_players_per_side", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("created_at", timestamp_type, nullable=False),
        sa.Column("updated_at", timestamp_type, nullable=True),
        sa.CheckConstraint(
            "standard_players_per_side IS NULL "
            "OR standard_players_per_side > 0",
            name="ck_field_types_players_per_side_positive",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_field_types_status",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            name="fk_field_types_sport_id_sports",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_field_types_code"),
        sa.UniqueConstraint(
            "sport_id",
            "name",
            name="uq_field_types_sport_name",
        ),
    )
    op.create_index(
        "ix_field_types_sport_status",
        "field_types",
        ["sport_id", "status"],
        unique=False,
    )

    _seed_catalog()

    with op.batch_alter_table("fields", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("field_type_id", sa.Integer(), nullable=True)
        )

    connection = op.get_bind()
    legacy_mapping = {
        "FIVE_A_SIDE": "FOOTBALL_5",
        "SEVEN_A_SIDE": "FOOTBALL_7",
        "ELEVEN_A_SIDE": "FOOTBALL_11",
    }
    for legacy_code, target_code in legacy_mapping.items():
        connection.execute(
            sa.text(
                "UPDATE fields SET field_type_id = "
                "(SELECT id FROM field_types WHERE code = :target_code) "
                "WHERE field_type = :legacy_code"
            ),
            {"target_code": target_code, "legacy_code": legacy_code},
        )

    unmapped = connection.scalar(
        sa.text("SELECT COUNT(*) FROM fields WHERE field_type_id IS NULL")
    )
    if unmapped:
        raise RuntimeError(
            "Multisport migration stopped because one or more legacy "
            "field_type values could not be mapped."
        )

    with op.batch_alter_table("fields", schema=None) as batch_op:
        batch_op.drop_constraint("ck_fields_type", type_="check")
        batch_op.alter_column(
            "field_type_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_fields_field_type_id_field_types",
            "field_types",
            ["field_type_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_fields_field_type_status",
            ["field_type_id", "status"],
            unique=False,
        )
        batch_op.drop_column("field_type")

    with op.batch_alter_table("venues", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("google_place_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_venues_latitude_range",
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
        )
        batch_op.create_check_constraint(
            "ck_venues_longitude_range",
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
        )
        batch_op.create_check_constraint(
            "ck_venues_coordinate_pair",
            "(latitude IS NULL AND longitude IS NULL) "
            "OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
        )


def downgrade():
    connection = op.get_bind()
    unsupported = connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM fields f "
            "JOIN field_types ft ON ft.id = f.field_type_id "
            "WHERE ft.code NOT IN "
            "('FOOTBALL_5', 'FOOTBALL_7', 'FOOTBALL_11')"
        )
    )
    if unsupported:
        raise RuntimeError(
            "Cannot downgrade while non-football fields exist. "
            "Deactivate and migrate them explicitly instead of losing data."
        )

    with op.batch_alter_table("venues", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_venues_coordinate_pair",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_venues_longitude_range",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_venues_latitude_range",
            type_="check",
        )
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.drop_column("google_place_id")

    with op.batch_alter_table("fields", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("field_type", sa.String(length=50), nullable=True)
        )

    connection.execute(
        sa.text(
            "UPDATE fields SET field_type = ("
            "SELECT CASE code "
            "WHEN 'FOOTBALL_5' THEN 'FIVE_A_SIDE' "
            "WHEN 'FOOTBALL_7' THEN 'SEVEN_A_SIDE' "
            "WHEN 'FOOTBALL_11' THEN 'ELEVEN_A_SIDE' END "
            "FROM field_types WHERE field_types.id = fields.field_type_id)"
        )
    )

    with op.batch_alter_table("fields", schema=None) as batch_op:
        batch_op.drop_index("ix_fields_field_type_status")
        batch_op.drop_constraint(
            "fk_fields_field_type_id_field_types",
            type_="foreignkey",
        )
        batch_op.alter_column(
            "field_type",
            existing_type=sa.String(length=50),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_fields_type",
            "field_type IN "
            "('FIVE_A_SIDE', 'SEVEN_A_SIDE', 'ELEVEN_A_SIDE')",
        )
        batch_op.drop_column("field_type_id")

    op.drop_index("ix_field_types_sport_status", table_name="field_types")
    op.drop_table("field_types")
    op.drop_table("sports")


def _seed_catalog() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sports_table = sa.table(
        "sports",
        sa.column("code", sa.String),
        sa.column("name", sa.Unicode),
        sa.column("status", sa.String),
        sa.column("created_at", timestamp_type),
    )
    op.bulk_insert(
        sports_table,
        [
            {"code": "FOOTBALL", "name": "Bóng đá", "status": "ACTIVE", "created_at": now},
            {"code": "BADMINTON", "name": "Cầu lông", "status": "ACTIVE", "created_at": now},
            {"code": "PICKLEBALL", "name": "Pickleball", "status": "ACTIVE", "created_at": now},
            {"code": "TENNIS", "name": "Tennis", "status": "ACTIVE", "created_at": now},
        ],
    )

    connection = op.get_bind()
    sport_ids = dict(
        connection.execute(sa.text("SELECT code, id FROM sports")).all()
    )
    field_types_table = sa.table(
        "field_types",
        sa.column("sport_id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.Unicode),
        sa.column("standard_players_per_side", sa.Integer),
        sa.column("status", sa.String),
        sa.column("created_at", timestamp_type),
    )
    op.bulk_insert(
        field_types_table,
        [
            {
                "sport_id": sport_ids["FOOTBALL"],
                "code": "FOOTBALL_5",
                "name": "Sân bóng đá 5 người",
                "standard_players_per_side": 5,
                "status": "ACTIVE",
                "created_at": now,
            },
            {
                "sport_id": sport_ids["FOOTBALL"],
                "code": "FOOTBALL_7",
                "name": "Sân bóng đá 7 người",
                "standard_players_per_side": 7,
                "status": "ACTIVE",
                "created_at": now,
            },
            {
                "sport_id": sport_ids["FOOTBALL"],
                "code": "FOOTBALL_11",
                "name": "Sân bóng đá 11 người",
                "standard_players_per_side": 11,
                "status": "ACTIVE",
                "created_at": now,
            },
            {
                "sport_id": sport_ids["BADMINTON"],
                "code": "BADMINTON_STANDARD",
                "name": "Sân cầu lông tiêu chuẩn",
                "standard_players_per_side": None,
                "status": "ACTIVE",
                "created_at": now,
            },
            {
                "sport_id": sport_ids["PICKLEBALL"],
                "code": "PICKLEBALL_STANDARD",
                "name": "Sân pickleball tiêu chuẩn",
                "standard_players_per_side": None,
                "status": "ACTIVE",
                "created_at": now,
            },
            {
                "sport_id": sport_ids["TENNIS"],
                "code": "TENNIS_STANDARD",
                "name": "Sân tennis tiêu chuẩn",
                "standard_players_per_side": None,
                "status": "ACTIVE",
                "created_at": now,
            },
        ],
    )
