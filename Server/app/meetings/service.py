import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import exists, or_
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.action_item import ActionItem
from app.models.decision import Decision
from app.models.meeting import Meeting, MeetingStatus
from app.models.meeting_quote import MeetingQuote
from app.models.meeting_summary import MeetingSummary
from app.models.speaker_stats import SpeakerStats
from app.models.transcript_segment import TranscriptSegment
from app.storage.base import StorageClient
from app.storage.validation import SNIFF_BYTES, has_allowed_extension, sniff_media_signature
from app.worker.celery_app import celery_app


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required")
    if not has_allowed_extension(file.filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    header = file.file.read(SNIFF_BYTES)
    file.file.seek(0)
    if not sniff_media_signature(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a supported audio/video format",
        )


def _validated_size(file: UploadFile) -> int:
    settings = get_settings()
    file.file.seek(0, 2)  # SEEK_END
    size = file.file.tell()
    file.file.seek(0)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the maximum allowed size",
        )
    return size


def create_meeting(
    db: Session,
    storage: StorageClient,
    *,
    owner_id: uuid.UUID,
    title: str,
    file: UploadFile,
) -> Meeting:
    _validate_upload(file)
    _validated_size(file)

    meeting_id = uuid.uuid4()
    safe_filename = Path(file.filename).name
    storage_path = f"{owner_id}/{meeting_id}/{safe_filename}"

    storage.upload(file.file, storage_path, content_type=file.content_type)

    meeting = Meeting(
        id=meeting_id,
        owner_id=owner_id,
        title=title,
        original_filename=safe_filename,
        storage_path=storage_path,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def list_meetings(db: Session, *, owner_id: uuid.UUID) -> list[Meeting]:
    return (
        db.query(Meeting)
        .filter(Meeting.owner_id == owner_id)
        .order_by(Meeting.uploaded_at.desc())
        .all()
    )


def search_meetings(
    db: Session,
    *,
    owner_id: uuid.UUID,
    q: str | None = None,
    speaker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Meeting], int]:
    """A meeting matches `q` if it's in the title OR anywhere in its
    transcript; matches `speaker` if any of its speaker_stats rows' label or
    display_name contains it. See app/search/service.py for the dialect
    split (Postgres tsvector vs. portable ILIKE) -- same reasoning applies
    here for the transcript half of `q`."""
    query = db.query(Meeting).filter(Meeting.owner_id == owner_id)

    if q:
        transcript_exists = exists().where(TranscriptSegment.meeting_id == Meeting.id)
        if db.get_bind().dialect.name == "postgresql":
            transcript_exists = transcript_exists.where(
                sa_text("transcript_segments.text_search @@ websearch_to_tsquery('english', :search_q)")
            )
            query = query.filter(or_(Meeting.title.ilike(f"%{q}%"), transcript_exists)).params(search_q=q)
        else:
            transcript_exists = transcript_exists.where(TranscriptSegment.text.ilike(f"%{q}%"))
            query = query.filter(or_(Meeting.title.ilike(f"%{q}%"), transcript_exists))

    if speaker:
        speaker_exists = exists().where(
            SpeakerStats.meeting_id == Meeting.id,
            or_(
                SpeakerStats.display_name.ilike(f"%{speaker}%"),
                SpeakerStats.speaker_label.ilike(f"%{speaker}%"),
            ),
        )
        query = query.filter(speaker_exists)

    if date_from is not None:
        query = query.filter(Meeting.uploaded_at >= date_from)
    if date_to is not None:
        query = query.filter(Meeting.uploaded_at < date_to + timedelta(days=1))

    total = query.count()
    rows = query.order_by(Meeting.uploaded_at.desc()).offset(offset).limit(limit).all()
    return rows, total


def get_owned_meeting(db: Session, *, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> Meeting:
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
        .first()
    )
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


def delete_meeting(db: Session, storage: StorageClient, *, meeting: Meeting) -> None:
    storage.delete(meeting.storage_path)
    db.delete(meeting)
    db.commit()


def enqueue_transcription(meeting_id: uuid.UUID) -> None:
    celery_app.send_task("transcribe_meeting", args=[str(meeting_id)])


def mark_meeting_failed(db: Session, *, meeting: Meeting, error_message: str) -> None:
    meeting.status = MeetingStatus.FAILED
    meeting.processing_error = error_message[:2000]
    db.commit()
    db.refresh(meeting)


def list_transcript_segments(db: Session, *, meeting_id: uuid.UUID) -> list[TranscriptSegment]:
    return (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )


def list_speaker_stats(db: Session, *, meeting_id: uuid.UUID) -> list[SpeakerStats]:
    return (
        db.query(SpeakerStats)
        .filter(SpeakerStats.meeting_id == meeting_id)
        .order_by(SpeakerStats.total_speaking_seconds.desc())
        .all()
    )


def get_owned_speaker_stat(db: Session, *, meeting_id: uuid.UUID, speaker_label: str) -> SpeakerStats:
    """Caller must already have verified meeting ownership (e.g. via
    `get_owned_meeting`) -- this only scopes by meeting_id + label."""
    stat = (
        db.query(SpeakerStats)
        .filter(SpeakerStats.meeting_id == meeting_id, SpeakerStats.speaker_label == speaker_label)
        .first()
    )
    if stat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found")
    return stat


def rename_speaker(db: Session, *, stat: SpeakerStats, display_name: str | None) -> SpeakerStats:
    cleaned = display_name.strip() if display_name else None
    stat.display_name = cleaned or None
    db.commit()
    db.refresh(stat)
    return stat


def enqueue_summarization(meeting_id: uuid.UUID) -> None:
    celery_app.send_task("summarize_meeting", args=[str(meeting_id)])


def trigger_summarization(db: Session, *, meeting: Meeting) -> Meeting:
    """Manual "(Re)generate summary" trigger -- usable any time a transcript
    exists, not just once the meeting has fully completed. Mirrors
    create_meeting's status update; the router owns enqueueing + the
    enqueue-failure fallback, same as upload_meeting does for transcription."""
    has_transcript = (
        db.query(TranscriptSegment.id).filter(TranscriptSegment.meeting_id == meeting.id).first() is not None
    )
    if not has_transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This meeting has no transcript yet -- wait for transcription to finish first.",
        )

    meeting.status = MeetingStatus.SUMMARIZING
    meeting.processing_progress = None
    meeting.processing_error = None
    db.commit()
    db.refresh(meeting)
    return meeting


def get_meeting_summary(db: Session, *, meeting_id: uuid.UUID) -> MeetingSummary:
    summary = db.query(MeetingSummary).filter(MeetingSummary.meeting_id == meeting_id).first()
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary has not been generated yet")
    return summary


def get_meeting_summary_or_none(db: Session, *, meeting_id: uuid.UUID) -> MeetingSummary | None:
    """Same lookup as get_meeting_summary, without the 404 -- the report
    endpoint wants to raise its own (400, "generate a summary first")
    instead of a generic not-found."""
    return db.query(MeetingSummary).filter(MeetingSummary.meeting_id == meeting_id).first()


def list_action_items(db: Session, *, meeting_id: uuid.UUID) -> list[ActionItem]:
    return (
        db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting_id)
        .order_by(ActionItem.created_at)
        .all()
    )


def get_owned_action_item(db: Session, *, meeting_id: uuid.UUID, action_item_id: uuid.UUID) -> ActionItem:
    """Caller must already have verified meeting ownership (e.g. via
    `get_owned_meeting`) -- this only scopes by meeting_id + id."""
    item = (
        db.query(ActionItem)
        .filter(ActionItem.meeting_id == meeting_id, ActionItem.id == action_item_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")
    return item


def set_action_item_completed(db: Session, *, item: ActionItem, is_completed: bool) -> ActionItem:
    item.is_completed = is_completed
    db.commit()
    db.refresh(item)
    return item


def list_decisions(db: Session, *, meeting_id: uuid.UUID) -> list[Decision]:
    return db.query(Decision).filter(Decision.meeting_id == meeting_id).order_by(Decision.created_at).all()


def list_meeting_quotes(db: Session, *, meeting_id: uuid.UUID) -> list[MeetingQuote]:
    return (
        db.query(MeetingQuote)
        .filter(MeetingQuote.meeting_id == meeting_id)
        .order_by(MeetingQuote.timestamp_seconds)
        .all()
    )
