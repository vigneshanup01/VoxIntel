"""add speaker_segments and speaker_stats tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speaker_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_speaker_seg_meeting", "speaker_segments", ["meeting_id"])

    op.create_table(
        "speaker_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=False),
        sa.Column("total_speaking_seconds", sa.Float(), nullable=False),
        sa.Column("speaking_percentage", sa.Float(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "speaker_label", name="uq_speaker_stats_meeting_label"),
    )


def downgrade() -> None:
    op.drop_table("speaker_stats")
    op.drop_index("idx_speaker_seg_meeting", table_name="speaker_segments")
    op.drop_table("speaker_segments")
