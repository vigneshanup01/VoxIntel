import uuid
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.speaker_stats import SpeakerStats


def get_speaker_analytics(
    db: Session,
    *,
    owner_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Per-speaker total speaking time across meetings, named speakers only.

    speaker_label (e.g. "SPEAKER_00") is a per-meeting diarization label,
    not a stable identity -- the same label in two different meetings can
    be two different people. Only rows with a user-set display_name
    (Phase 3's rename feature) can be meaningfully summed across meetings;
    everything else is counted and excluded here, never silently merged.
    """
    base_query = (
        db.query(SpeakerStats)
        .join(Meeting, Meeting.id == SpeakerStats.meeting_id)
        .filter(Meeting.owner_id == owner_id)
    )
    if date_from is not None:
        base_query = base_query.filter(Meeting.uploaded_at >= date_from)
    if date_to is not None:
        # Inclusive of the whole "to" day.
        base_query = base_query.filter(Meeting.uploaded_at < date_to + timedelta(days=1))

    unnamed_count = base_query.filter(SpeakerStats.display_name.is_(None)).count()

    rows = (
        base_query.filter(SpeakerStats.display_name.isnot(None))
        .with_entities(
            SpeakerStats.display_name,
            func.sum(SpeakerStats.total_speaking_seconds).label("total_seconds"),
            func.count(func.distinct(SpeakerStats.meeting_id)).label("meeting_count"),
        )
        .group_by(SpeakerStats.display_name)
        .order_by(func.sum(SpeakerStats.total_speaking_seconds).desc())
        .all()
    )

    speakers = [
        {
            "display_name": display_name,
            "total_speaking_seconds": float(total_seconds),
            "meeting_count": meeting_count,
        }
        for display_name, total_seconds, meeting_count in rows
    ]

    return {"speakers": speakers, "unnamed_speaker_rows_excluded": unnamed_count}
