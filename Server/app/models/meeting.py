import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class MeetingStatus:
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSCRIBED = "transcribed"
    DIARIZING = "diarizing"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=MeetingStatus.UPLOADED, server_default=MeetingStatus.UPLOADED
    )
    language_detected: Mapped[str | None] = mapped_column(String(10), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free-text, e.g. "Transcribing audio: 45%" or "Diarization: extracting
    # voice embeddings (3/12)". Best-effort progress for the UI -- cleared
    # whenever status moves to a new stage, never load-bearing for anything.
    processing_progress: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="meetings")
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="TranscriptSegment.start_time"
    )
    speaker_segments: Mapped[list["SpeakerSegment"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="SpeakerSegment.start_time"
    )
    speaker_stats: Mapped[list["SpeakerStats"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True
    )
