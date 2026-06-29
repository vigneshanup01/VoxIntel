import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.speaker_stats import SpeakerStats

RECENT_MEETINGS_LIMIT = 5
THIS_WEEK_WINDOW = timedelta(days=7)


def _most_active_speaker(db: Session, *, owner_id: uuid.UUID) -> str | None:
    """Top speaker by total speaking time across all the owner's meetings.

    Only considers speaker_stats rows with a display_name set -- SPEAKER_00
    in one meeting and SPEAKER_00 in another aren't the same person, so an
    unnamed label can't be meaningfully summed across meetings (see
    app/analytics/service.py for the fuller version of this caveat).
    """
    row = (
        db.query(SpeakerStats.display_name, func.sum(SpeakerStats.total_speaking_seconds).label("total"))
        .join(Meeting, Meeting.id == SpeakerStats.meeting_id)
        .filter(Meeting.owner_id == owner_id, SpeakerStats.display_name.isnot(None))
        .group_by(SpeakerStats.display_name)
        .order_by(func.sum(SpeakerStats.total_speaking_seconds).desc())
        .first()
    )
    return row[0] if row else None


def get_dashboard_summary(db: Session, *, owner_id: uuid.UUID) -> dict:
    total_meetings = db.query(func.count(Meeting.id)).filter(Meeting.owner_id == owner_id).scalar() or 0

    total_seconds = (
        db.query(func.coalesce(func.sum(Meeting.duration_seconds), 0.0)).filter(Meeting.owner_id == owner_id).scalar()
        or 0.0
    )

    week_ago = datetime.now(timezone.utc) - THIS_WEEK_WINDOW
    meetings_this_week = (
        db.query(func.count(Meeting.id))
        .filter(Meeting.owner_id == owner_id, Meeting.uploaded_at >= week_ago)
        .scalar()
        or 0
    )

    recent_meetings = (
        db.query(Meeting)
        .filter(Meeting.owner_id == owner_id)
        .order_by(Meeting.uploaded_at.desc())
        .limit(RECENT_MEETINGS_LIMIT)
        .all()
    )

    return {
        "total_meetings": total_meetings,
        "total_hours": round(total_seconds / 3600, 2),
        "meetings_this_week": meetings_this_week,
        "most_active_speaker": _most_active_speaker(db, owner_id=owner_id),
        "recent_meetings": recent_meetings,
    }
