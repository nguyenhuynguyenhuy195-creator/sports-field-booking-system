"""add momo checkout url

Revision ID: d7a1b9e4c320
Revises: c4f8d2a6e901
Create Date: 2026-08-13 00:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d7a1b9e4c320"
down_revision = "c4f8d2a6e901"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("checkout_url", sa.Unicode(length=2000), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_column("checkout_url")
