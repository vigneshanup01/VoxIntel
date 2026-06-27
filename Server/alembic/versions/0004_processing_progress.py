"""add processing_progress column to meetings

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("processing_progress", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "processing_progress")
