import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class SpeakerSegment(Base):
    """Raw diarization output: 'someone spoke from start to end'.

    Distinct from `transcript_segments` -- this comes from Pyannote, not
    Whisper, and the two are aligned by timestamp overlap, not joined.
    """

    __tablename__ = "speaker_segments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="speaker_segments")
