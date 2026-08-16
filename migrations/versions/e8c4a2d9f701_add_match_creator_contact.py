"""add match creator contact

Revision ID: e8c4a2d9f701
Revises: d7a1b9e4c320
Create Date: 2026-08-14 19:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e8c4a2d9f701"
down_revision = "d7a1b9e4c320"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("creator_contact_phone", sa.String(length=20), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_column("creator_contact_phone")
