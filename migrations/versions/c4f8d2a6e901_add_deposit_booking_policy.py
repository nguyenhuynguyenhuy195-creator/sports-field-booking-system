"""add deposit booking policy

Revision ID: c4f8d2a6e901
Revises: b2e91c4a7d10
Create Date: 2026-08-13 00:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = "c4f8d2a6e901"
down_revision = "b2e91c4a7d10"
branch_labels = None
depends_on = None


timestamp_type = sa.DateTime().with_variant(mssql.DATETIME2(), "mssql")


def upgrade():
    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("booking_mode", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("play_format", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("requested_players", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payment_policy", sa.String(30), nullable=True))
        batch_op.add_column(
            sa.Column("deposit_rate", sa.Numeric(precision=5, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deposit_amount", sa.Numeric(precision=12, scale=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("matchmaking_deadline", timestamp_type, nullable=True)
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE bookings SET booking_mode = CASE payment_mode "
            "WHEN 'FULL_PAYMENT' THEN 'DIRECT_BOOKING' "
            "WHEN 'SPLIT_OPPONENT' THEN 'FIND_OPPONENT' "
            "WHEN 'SPLIT_PLAYERS' THEN 'FIND_PLAYERS' END, "
            "requested_players = CASE WHEN payment_mode = 'SPLIT_PLAYERS' "
            "THEN split_required_players ELSE NULL END, "
            "payment_policy = 'LEGACY_FULL_ONLINE', "
            "deposit_rate = 1.0000, deposit_amount = total_amount, "
            "matchmaking_deadline = CASE WHEN payment_mode = 'SPLIT_OPPONENT' "
            "THEN funding_deadline ELSE NULL END"
        )
    )
    unmapped = connection.scalar(
        sa.text("SELECT COUNT(*) FROM bookings WHERE booking_mode IS NULL")
    )
    if unmapped:
        raise RuntimeError(
            "Deposit migration stopped because a legacy payment_mode "
            "could not be mapped."
        )

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.drop_constraint("ck_bookings_payment_mode", type_="check")
        batch_op.drop_constraint(
            "ck_bookings_split_player_configuration",
            type_="check",
        )
        batch_op.drop_constraint("ck_bookings_paid_amount_range", type_="check")
        batch_op.alter_column(
            "booking_mode",
            existing_type=sa.String(30),
            nullable=False,
        )
        batch_op.alter_column(
            "payment_policy",
            existing_type=sa.String(30),
            nullable=False,
        )
        batch_op.alter_column(
            "deposit_rate",
            existing_type=sa.Numeric(precision=5, scale=4),
            nullable=False,
        )
        batch_op.alter_column(
            "deposit_amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_bookings_booking_mode",
            "booking_mode IN ('DIRECT_BOOKING', 'FIND_OPPONENT', 'FIND_PLAYERS')",
        )
        batch_op.create_check_constraint(
            "ck_bookings_play_format",
            "play_format IS NULL OR play_format IN ('SINGLES', 'DOUBLES')",
        )
        batch_op.create_check_constraint(
            "ck_bookings_payment_policy",
            "payment_policy IN ('LEGACY_FULL_ONLINE', 'DEPOSIT_30')",
        )
        batch_op.create_check_constraint(
            "ck_bookings_deposit_rate",
            "deposit_rate > 0 AND deposit_rate <= 1",
        )
        batch_op.create_check_constraint(
            "ck_bookings_deposit_amount_range",
            "deposit_amount > 0 AND deposit_amount <= total_amount",
        )
        batch_op.create_check_constraint(
            "ck_bookings_paid_amount_range",
            "paid_amount >= 0 AND paid_amount <= deposit_amount",
        )
        batch_op.create_check_constraint(
            "ck_bookings_requested_players",
            "((booking_mode = 'FIND_PLAYERS' "
            "AND requested_players IS NOT NULL AND requested_players > 0) "
            "OR (booking_mode <> 'FIND_PLAYERS' AND requested_players IS NULL))",
        )
        batch_op.create_index(
            "ix_bookings_status_matchmaking_deadline",
            ["status", "matchmaking_deadline"],
            unique=False,
        )
        batch_op.drop_column("split_required_players")
        batch_op.drop_column("split_total_players")
        batch_op.drop_column("payment_mode")

    with op.batch_alter_table("match_participants", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contact_phone", sa.String(20), nullable=True))


def downgrade():
    connection = op.get_bind()
    new_bookings = connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM bookings "
            "WHERE payment_policy = 'DEPOSIT_30'"
        )
    )
    if new_bookings:
        raise RuntimeError(
            "Cannot downgrade after DEPOSIT_30 bookings exist because doing so "
            "would reinterpret deposit history as full online payment."
        )

    with op.batch_alter_table("match_participants", schema=None) as batch_op:
        batch_op.drop_column("contact_phone")

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_mode", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("split_total_players", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("split_required_players", sa.Integer(), nullable=True)
        )

    connection.execute(
        sa.text(
            "UPDATE bookings SET payment_mode = CASE booking_mode "
            "WHEN 'DIRECT_BOOKING' THEN 'FULL_PAYMENT' "
            "WHEN 'FIND_OPPONENT' THEN 'SPLIT_OPPONENT' "
            "WHEN 'FIND_PLAYERS' THEN 'SPLIT_PLAYERS' END, "
            "split_required_players = CASE WHEN booking_mode = 'FIND_PLAYERS' "
            "THEN requested_players ELSE NULL END, "
            "split_total_players = CASE WHEN booking_mode = 'FIND_PLAYERS' "
            "THEN (SELECT capacity FROM fields WHERE fields.id = bookings.field_id) "
            "ELSE NULL END"
        )
    )

    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.drop_index("ix_bookings_status_matchmaking_deadline")
        batch_op.drop_constraint("ck_bookings_requested_players", type_="check")
        batch_op.drop_constraint("ck_bookings_paid_amount_range", type_="check")
        batch_op.drop_constraint("ck_bookings_deposit_amount_range", type_="check")
        batch_op.drop_constraint("ck_bookings_deposit_rate", type_="check")
        batch_op.drop_constraint("ck_bookings_payment_policy", type_="check")
        batch_op.drop_constraint("ck_bookings_play_format", type_="check")
        batch_op.drop_constraint("ck_bookings_booking_mode", type_="check")
        batch_op.alter_column(
            "payment_mode",
            existing_type=sa.String(30),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_bookings_payment_mode",
            "payment_mode IN ('FULL_PAYMENT', 'SPLIT_OPPONENT', 'SPLIT_PLAYERS')",
        )
        batch_op.create_check_constraint(
            "ck_bookings_paid_amount_range",
            "paid_amount >= 0 AND paid_amount <= total_amount",
        )
        batch_op.create_check_constraint(
            "ck_bookings_split_player_configuration",
            "((payment_mode = 'SPLIT_PLAYERS' "
            "AND split_total_players IS NOT NULL "
            "AND split_required_players IS NOT NULL "
            "AND split_total_players > 1 "
            "AND split_required_players > 0 "
            "AND split_required_players < split_total_players) "
            "OR (payment_mode <> 'SPLIT_PLAYERS' "
            "AND split_total_players IS NULL "
            "AND split_required_players IS NULL))",
        )
        batch_op.drop_column("matchmaking_deadline")
        batch_op.drop_column("deposit_amount")
        batch_op.drop_column("deposit_rate")
        batch_op.drop_column("payment_policy")
        batch_op.drop_column("requested_players")
        batch_op.drop_column("play_format")
        batch_op.drop_column("booking_mode")
