"""add full-text search column and dashboard/analytics indexes

Postgres-only DDL (generated tsvector column + GIN index) -- not mirrored in
the SQLAlchemy ORM models, since the test suite creates tables via
Base.metadata.create_all() against SQLite and never runs these migrations.
The search service falls back to a portable ILIKE query when the DB
dialect isn't postgresql (see app/search/service.py).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transcript_segments",
        sa.Column(
            "text_search",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_transcript_search", "transcript_segments", ["text_search"], postgresql_using="gin"
    )

    # Dashboard/search queries filter+sort by (owner_id, uploaded_at) and
    # join speaker_stats by meeting_id constantly -- these are the composite/
    # single-column indexes Phase 6's queries actually run against.
    op.create_index("idx_meetings_owner_date", "meetings", ["owner_id", sa.text("uploaded_at DESC")])
    op.create_index("idx_speaker_stats_meeting_id", "speaker_stats", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("idx_speaker_stats_meeting_id", table_name="speaker_stats")
    op.drop_index("idx_meetings_owner_date", table_name="meetings")
    op.drop_index("idx_transcript_search", table_name="transcript_segments")
    op.drop_column("transcript_segments", "text_search")
