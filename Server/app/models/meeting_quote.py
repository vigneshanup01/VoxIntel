import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class QuoteCategory:
    NOTABLE = "notable"
    RISK = "risk"


class MeetingQuote(Base):
    __tablename__ = "meeting_quotes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Seconds into the meeting -- lets the frontend jump the transcript view
    # to where the quote was said. Nullable since the LLM occasionally can't
    # pin a quote to one timestamp (e.g. a quote spanning two lines).
    timestamp_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuoteCategory.NOTABLE, server_default=QuoteCategory.NOTABLE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="quotes")
