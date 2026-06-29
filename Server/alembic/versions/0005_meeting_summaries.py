"""add meeting_summaries, action_items, decisions, and meeting_quotes tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("detailed_summary", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", name="uq_meeting_summaries_meeting_id"),
    )

    op.create_table(
        "action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("due_date", sa.String(length=100), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_action_items_meeting", "action_items", ["meeting_id"])

    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_decisions_meeting", "decisions", ["meeting_id"])

    op.create_table(
        "meeting_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=True),
        sa.Column("timestamp_seconds", sa.Float(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="notable"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_meeting_quotes_meeting", "meeting_quotes", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("idx_meeting_quotes_meeting", table_name="meeting_quotes")
    op.drop_table("meeting_quotes")
    op.drop_index("idx_decisions_meeting", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("idx_action_items_meeting", table_name="action_items")
    op.drop_table("action_items")
    op.drop_table("meeting_summaries")
