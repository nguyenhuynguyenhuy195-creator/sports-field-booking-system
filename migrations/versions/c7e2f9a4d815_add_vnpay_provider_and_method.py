"""add vnpay provider and method

Revision ID: c7e2f9a4d815
Revises: a6d8e4f2c913
Create Date: 2026-09-12 00:00:00.000000

"""

from alembic import op


revision = "c7e2f9a4d815"
down_revision = "a6d8e4f2c913"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("ck_payments_provider", type_="check")
        batch_op.create_check_constraint(
            "ck_payments_provider",
            "provider IN ('MOCK', 'MOMO', 'VNPAY')",
        )
        batch_op.drop_constraint("ck_payments_method", type_="check")
        batch_op.create_check_constraint(
            "ck_payments_method",
            "payment_method IN ('SIMULATED', 'MOMO_WALLET', 'VNPAY_GATEWAY')",
        )


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("ck_payments_method", type_="check")
        batch_op.create_check_constraint(
            "ck_payments_method",
            "payment_method IN ('SIMULATED', 'MOMO_WALLET')",
        )
        batch_op.drop_constraint("ck_payments_provider", type_="check")
        batch_op.create_check_constraint(
            "ck_payments_provider",
            "provider IN ('MOCK', 'MOMO')",
        )
