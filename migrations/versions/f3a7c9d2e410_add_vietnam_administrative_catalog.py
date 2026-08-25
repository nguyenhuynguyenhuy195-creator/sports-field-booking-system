"""add vietnam administrative catalog

Revision ID: f3a7c9d2e410
Revises: e8c4a2d9f701
Create Date: 2026-08-25 10:00:00.000000
"""

from collections import Counter
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "f3a7c9d2e410"
down_revision = "e8c4a2d9f701"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provinces",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.Unicode(length=100), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("name", name="uq_provinces_name"),
    )
    op.create_table(
        "wards",
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.Unicode(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "type IN ('PHUONG', 'XA', 'DAC_KHU')",
            name="ck_wards_type",
        ),
        sa.ForeignKeyConstraint(
            ["province_code"],
            ["provinces.code"],
            name="fk_wards_province_code_provinces",
        ),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        "ix_wards_province_name",
        "wards",
        ["province_code", "name"],
        unique=False,
    )
    _seed_catalog()

    with op.batch_alter_table("venues", schema=None) as batch_op:
        batch_op.alter_column(
            "city",
            existing_type=sa.Unicode(length=100),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("province_code", sa.String(length=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("province_name", sa.Unicode(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ward_code", sa.String(length=5), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ward_name", sa.Unicode(length=100), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_venues_province_code_provinces",
            "provinces",
            ["province_code"],
            ["code"],
        )
        batch_op.create_foreign_key(
            "fk_venues_ward_code_wards",
            "wards",
            ["ward_code"],
            ["code"],
        )
        batch_op.create_index(
            "ix_venues_status_province_ward",
            ["status", "province_code", "ward_code"],
            unique=False,
        )


def downgrade():
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE venues SET district = ward_name "
            "WHERE district IS NULL AND ward_name IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE venues SET city = COALESCE(city, province_name, :fallback) "
            "WHERE city IS NULL"
        ),
        {"fallback": "Chưa xác định"},
    )

    with op.batch_alter_table("venues", schema=None) as batch_op:
        batch_op.drop_index("ix_venues_status_province_ward")
        batch_op.drop_constraint(
            "fk_venues_ward_code_wards",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_venues_province_code_provinces",
            type_="foreignkey",
        )
        batch_op.drop_column("ward_name")
        batch_op.drop_column("ward_code")
        batch_op.drop_column("province_name")
        batch_op.drop_column("province_code")
        batch_op.alter_column(
            "city",
            existing_type=sa.Unicode(length=100),
            nullable=False,
        )

    op.drop_index("ix_wards_province_name", table_name="wards")
    op.drop_table("wards")
    op.drop_table("provinces")


def _seed_catalog() -> None:
    catalog_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "data"
        / "vietnam_administrative_units_2025.json"
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    province_codes = {item["code"] for item in catalog["provinces"]}
    ward_codes = {item["code"] for item in catalog["wards"]}
    type_counts = Counter(item["type"] for item in catalog["wards"])
    if (
        len(catalog["provinces"]) != 34
        or len(province_codes) != 34
        or len(catalog["wards"]) != 3321
        or len(ward_codes) != 3321
        or type_counts != Counter({"XA": 2621, "PHUONG": 687, "DAC_KHU": 13})
        or any(
            item["province_code"] not in province_codes
            for item in catalog["wards"]
        )
    ):
        raise RuntimeError("Administrative catalog snapshot is incomplete.")

    provinces_table = sa.table(
        "provinces",
        sa.column("code", sa.String),
        sa.column("name", sa.Unicode),
    )
    wards_table = sa.table(
        "wards",
        sa.column("code", sa.String),
        sa.column("province_code", sa.String),
        sa.column("name", sa.Unicode),
        sa.column("type", sa.String),
    )
    op.bulk_insert(provinces_table, catalog["provinces"])
    for offset in range(0, len(catalog["wards"]), 500):
        op.bulk_insert(wards_table, catalog["wards"][offset : offset + 500])
