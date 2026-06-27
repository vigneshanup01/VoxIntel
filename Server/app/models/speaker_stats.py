import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class SpeakerStats(Base):
    __tablename__ = "speaker_stats"
    __table_args__ = (UniqueConstraint("meeting_id", "speaker_label", name="uq_speaker_stats_meeting_label"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    total_speaking_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    speaking_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL until the user renames "SPEAKER_00" -> "John" -- anonymous
    # diarization, not speaker recognition (see app/worker/diarization.py).
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="speaker_stats")
