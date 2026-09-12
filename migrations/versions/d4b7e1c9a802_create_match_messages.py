"""create match messages

Revision ID: d4b7e1c9a802
Revises: c7e2f9a4d815
Create Date: 2026-09-13 09:40:12.118427

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision = "d4b7e1c9a802"
down_revision = "c7e2f9a4d815"
branch_labels = None
depends_on = None


SYSTEM_EVENT_FILTER = "message_type = 'SYSTEM'"


def upgrade():
    op.create_table(
        "match_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Unicode(length=500), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=True),
        sa.Column("event_key", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mssql.DATETIME2(), "mssql"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(message_type = 'USER' AND sender_id IS NOT NULL "
            "AND event_type IS NULL AND event_key IS NULL) "
            "OR (message_type = 'SYSTEM' AND sender_id IS NULL "
            "AND event_type IS NOT NULL AND event_key IS NOT NULL)",
            name="ck_match_messages_shape",
        ),
        sa.CheckConstraint(
            "content <> ''",
            name="ck_match_messages_content_present",
        ),
        sa.CheckConstraint(
            "event_type IS NULL OR event_type IN ("
            "'participant_joined', 'participant_withdrawn', 'listing_closed', "
            "'match_cancelled', 'match_completed')",
            name="ck_match_messages_event_type",
        ),
        sa.CheckConstraint(
            "message_type IN ('USER', 'SYSTEM')",
            name="ck_match_messages_type",
        ),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("match_messages", schema=None) as batch_op:
        batch_op.create_index(
            "ix_match_messages_match_id_id",
            ["match_id", "id"],
            unique=False,
        )
        batch_op.create_index(
            "uq_match_messages_system_event",
            ["match_id", "event_key"],
            unique=True,
            mssql_where=sa.text(SYSTEM_EVENT_FILTER),
            sqlite_where=sa.text(SYSTEM_EVENT_FILTER),
        )


def downgrade():
    with op.batch_alter_table("match_messages", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_match_messages_system_event",
            mssql_where=sa.text(SYSTEM_EVENT_FILTER),
            sqlite_where=sa.text(SYSTEM_EVENT_FILTER),
        )
        batch_op.drop_index("ix_match_messages_match_id_id")

    op.drop_table("match_messages")
