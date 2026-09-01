"""add venue and field media images

Revision ID: a6d8e4f2c913
Revises: f3a7c9d2e410
Create Date: 2026-09-01 02:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = "a6d8e4f2c913"
down_revision = "f3a7c9d2e410"
branch_labels = None
depends_on = None


timestamp_type = sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")


def upgrade():
    op.create_table(
        "media_images",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=True),
        sa.Column("field_id", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.Unicode(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "is_cover",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("created_at", timestamp_type, nullable=False),
        sa.CheckConstraint(
            "(venue_id IS NOT NULL AND field_id IS NULL) OR "
            "(venue_id IS NULL AND field_id IS NOT NULL)",
            name="ck_media_images_single_parent",
        ),
        sa.CheckConstraint(
            "size_bytes > 0",
            name="ck_media_images_size_positive",
        ),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["fields.id"],
            name="fk_media_images_field_id_fields",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name="fk_media_images_venue_id_venues",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_path",
            name="uq_media_images_storage_path",
        ),
    )
    op.create_index(
        "ix_media_images_venue_created",
        "media_images",
        ["venue_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_media_images_field_created",
        "media_images",
        ["field_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_media_images_venue_cover",
        "media_images",
        ["venue_id"],
        unique=True,
        sqlite_where=sa.text("is_cover = 1 AND venue_id IS NOT NULL"),
        mssql_where=sa.text("is_cover = 1 AND venue_id IS NOT NULL"),
    )
    op.create_index(
        "uq_media_images_field_cover",
        "media_images",
        ["field_id"],
        unique=True,
        sqlite_where=sa.text("is_cover = 1 AND field_id IS NOT NULL"),
        mssql_where=sa.text("is_cover = 1 AND field_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_media_images_field_cover",
        table_name="media_images",
    )
    op.drop_index(
        "uq_media_images_venue_cover",
        table_name="media_images",
    )
    op.drop_index(
        "ix_media_images_field_created",
        table_name="media_images",
    )
    op.drop_index(
        "ix_media_images_venue_created",
        table_name="media_images",
    )
    op.drop_table("media_images")
