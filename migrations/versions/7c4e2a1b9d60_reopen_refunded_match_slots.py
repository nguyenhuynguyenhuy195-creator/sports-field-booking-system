"""reopen refunded match slots

Revision ID: 7c4e2a1b9d60
Revises: 5bcf59c01c23
Create Date: 2026-08-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "7c4e2a1b9d60"
down_revision = "5bcf59c01c23"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("booking_contributions", schema=None) as batch_op:
        batch_op.drop_index("uq_booking_contributions_external_slot")
        batch_op.create_index(
            "uq_booking_contributions_external_slot",
            ["booking_id", "contribution_type", "slot_number"],
            unique=True,
            mssql_where=sa.text(
                "slot_number IS NOT NULL AND status <> 'REFUNDED'"
            ),
            sqlite_where=sa.text(
                "slot_number IS NOT NULL AND status <> 'REFUNDED'"
            ),
        )


def downgrade():
    with op.batch_alter_table("booking_contributions", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_booking_contributions_external_slot",
            mssql_where=sa.text(
                "slot_number IS NOT NULL AND status <> 'REFUNDED'"
            ),
            sqlite_where=sa.text(
                "slot_number IS NOT NULL AND status <> 'REFUNDED'"
            ),
        )
        batch_op.create_index(
            "uq_booking_contributions_external_slot",
            ["booking_id", "contribution_type", "slot_number"],
            unique=True,
            mssql_where=sa.text("slot_number IS NOT NULL"),
            sqlite_where=sa.text("slot_number IS NOT NULL"),
        )
