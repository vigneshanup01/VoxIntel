import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class MeetingSummary(Base):
    """One row per meeting. Regenerating replaces this row (and the
    associated action_items/decisions/quotes) rather than appending to it --
    see `summarize_meeting` in app/worker/tasks.py."""

    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_summary: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="summary")
