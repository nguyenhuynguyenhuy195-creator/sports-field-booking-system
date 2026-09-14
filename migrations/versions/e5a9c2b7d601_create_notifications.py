"""Create USER notifications.

Revision ID: e5a9c2b7d601
Revises: d4b7e1c9a802
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "e5a9c2b7d601"
down_revision = "d4b7e1c9a802"
branch_labels = None
depends_on = None


def upgrade():
    timestamp = sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_key", sa.String(160), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.Unicode(160), nullable=False),
        sa.Column("message", sa.Unicode(500), nullable=False),
        sa.Column("target_url", sa.String(250), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("read_at", timestamp, nullable=True),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event"),
        sa.CheckConstraint(
            "type IN ('payment_success', 'join_request', 'request_accepted', "
            "'request_rejected', 'opponent_joined', 'participant_withdrawn', "
            "'booking_cancelled', 'match_cancelled', 'refund_success')",
            name="ck_notifications_type",
        ),
    )
    op.create_index("ix_notifications_user_read_created", "notifications", ["user_id", "is_read", "created_at"])


def downgrade():
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    op.drop_table("notifications")
