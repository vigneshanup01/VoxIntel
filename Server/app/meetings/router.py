import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.meetings import report, service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.meeting import MeetingListResponse, MeetingOut, MeetingSearchResponse, MeetingStatusOut
from app.schemas.speaker import RenameSpeakerRequest, SpeakerStatsListResponse, SpeakerStatsOut
from app.schemas.summary import (
    ActionItemListResponse,
    ActionItemOut,
    ActionItemUpdateRequest,
    DecisionListResponse,
    DecisionOut,
    MeetingQuoteListResponse,
    MeetingQuoteOut,
    MeetingSummaryOut,
)
from app.schemas.transcript import TranscriptResponse, TranscriptSegmentOut
from app.services.audit import log_action
from app.storage.base import StorageClient
from app.storage.s3_client import get_storage_client

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def upload_meeting(
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> MeetingOut:
    meeting = service.create_meeting(db, storage, owner_id=current_user.id, title=title, file=file)
    log_action(db, user_id=current_user.id, action=AuditAction.UPLOAD_MEETING, meeting_id=meeting.id)
    try:
        service.enqueue_transcription(meeting.id)
    except Exception as exc:
        # The upload itself succeeded -- don't fail the request over a
        # broker hiccup, surface it as a failed meeting instead.
        service.mark_meeting_failed(db, meeting=meeting, error_message=f"Could not queue for transcription: {exc}")
    return MeetingOut.model_validate(meeting)


@router.get("", response_model=MeetingListResponse)
def list_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingListResponse:
    meetings = service.list_meetings(db, owner_id=current_user.id)
    return MeetingListResponse(meetings=[MeetingOut.model_validate(m) for m in meetings])


@router.get("/search", response_model=MeetingSearchResponse)
def search_meetings(
    q: str | None = Query(default=None),
    speaker: str | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingSearchResponse:
    # Registered before /{meeting_id} -- a path param typed as uuid.UUID
    # would otherwise 422 on the literal segment "search" before ever
    # reaching this handler. Route registration order is matching priority.
    meetings, total = service.search_meetings(
        db,
        owner_id=current_user.id,
        q=q,
        speaker=speaker,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return MeetingSearchResponse(
        meetings=[MeetingOut.model_validate(m) for m in meetings], total=total, limit=limit, offset=offset
    )


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingOut:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    return MeetingOut.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    # Log before deleting: the FK must point at a row that still exists at
    # insert time. The meeting's own ON DELETE SET NULL then clears this
    # log entry's meeting_id (and any earlier ones) once it's gone.
    log_action(db, user_id=current_user.id, action=AuditAction.DELETE_MEETING, meeting_id=meeting_id)
    service.delete_meeting(db, meeting=meeting)


@router.get("/{meeting_id}/status", response_model=MeetingStatusOut)
def get_meeting_status(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingStatusOut:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    return MeetingStatusOut(
        status=meeting.status,
        processing_error=meeting.processing_error,
        processing_progress=meeting.processing_progress,
    )


@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse)
def get_meeting_transcript(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptResponse:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    segments = service.list_transcript_segments(db, meeting_id=meeting_id)
    return TranscriptResponse(segments=[TranscriptSegmentOut.model_validate(s) for s in segments])


@router.get("/{meeting_id}/speakers", response_model=SpeakerStatsListResponse)
def get_meeting_speakers(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakerStatsListResponse:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    stats = service.list_speaker_stats(db, meeting_id=meeting_id)
    return SpeakerStatsListResponse(speakers=[SpeakerStatsOut.model_validate(s) for s in stats])


@router.patch("/{meeting_id}/speakers/{speaker_label}", response_model=SpeakerStatsOut)
def rename_meeting_speaker(
    meeting_id: uuid.UUID,
    speaker_label: str,
    payload: RenameSpeakerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakerStatsOut:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    stat = service.get_owned_speaker_stat(db, meeting_id=meeting_id, speaker_label=speaker_label)
    updated = service.rename_speaker(db, stat=stat, display_name=payload.display_name)
    return SpeakerStatsOut.model_validate(updated)


@router.post("/{meeting_id}/summarize", response_model=MeetingOut, status_code=status.HTTP_202_ACCEPTED)
def trigger_meeting_summarization(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingOut:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    updated = service.trigger_summarization(db, meeting=meeting)
    try:
        service.enqueue_summarization(updated.id)
    except Exception as exc:
        service.mark_meeting_failed(db, meeting=updated, error_message=f"Could not queue for summarization: {exc}")
    return MeetingOut.model_validate(updated)


@router.get("/{meeting_id}/summary", response_model=MeetingSummaryOut)
def get_meeting_summary(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingSummaryOut:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    summary = service.get_meeting_summary(db, meeting_id=meeting_id)
    return MeetingSummaryOut.model_validate(summary)


@router.get("/{meeting_id}/action-items", response_model=ActionItemListResponse)
def get_meeting_action_items(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionItemListResponse:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    items = service.list_action_items(db, meeting_id=meeting_id)
    return ActionItemListResponse(action_items=[ActionItemOut.model_validate(i) for i in items])


@router.patch("/{meeting_id}/action-items/{action_item_id}", response_model=ActionItemOut)
def update_meeting_action_item(
    meeting_id: uuid.UUID,
    action_item_id: uuid.UUID,
    payload: ActionItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActionItemOut:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    item = service.get_owned_action_item(db, meeting_id=meeting_id, action_item_id=action_item_id)
    updated = service.set_action_item_completed(db, item=item, is_completed=payload.is_completed)
    return ActionItemOut.model_validate(updated)


@router.get("/{meeting_id}/decisions", response_model=DecisionListResponse)
def get_meeting_decisions(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DecisionListResponse:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    decisions = service.list_decisions(db, meeting_id=meeting_id)
    return DecisionListResponse(decisions=[DecisionOut.model_validate(d) for d in decisions])


@router.get("/{meeting_id}/quotes", response_model=MeetingQuoteListResponse)
def get_meeting_quotes(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingQuoteListResponse:
    service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    quotes = service.list_meeting_quotes(db, meeting_id=meeting_id)
    return MeetingQuoteListResponse(quotes=[MeetingQuoteOut.model_validate(q) for q in quotes])


def _safe_filename(title: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
    return cleaned or "meeting"


@router.get("/{meeting_id}/report.pdf")
def get_meeting_report(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    summary = service.get_meeting_summary_or_none(db, meeting_id=meeting_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Generate a summary before downloading a report"
        )

    action_items = service.list_action_items(db, meeting_id=meeting_id)
    decisions = service.list_decisions(db, meeting_id=meeting_id)
    quotes = service.list_meeting_quotes(db, meeting_id=meeting_id)
    speaker_stats = service.list_speaker_stats(db, meeting_id=meeting_id)

    html_doc = report.build_report_html(
        meeting_title=meeting.title,
        uploaded_at=meeting.uploaded_at.strftime("%Y-%m-%d %H:%M UTC"),
        duration_seconds=meeting.duration_seconds,
        executive_summary=summary.executive_summary,
        detailed_summary=summary.detailed_summary,
        action_items=[
            {"description": a.description, "owner": a.owner, "due_date": a.due_date} for a in action_items
        ],
        decisions=[{"description": d.description} for d in decisions],
        quotes=[
            {
                "quote_text": q.quote_text,
                "speaker_label": q.speaker_label,
                "timestamp_seconds": q.timestamp_seconds,
                "category": q.category,
            }
            for q in quotes
        ],
        speaker_stats=[
            {
                "speaker_label": s.speaker_label,
                "display_name": s.display_name,
                "total_speaking_seconds": s.total_speaking_seconds,
                "speaking_percentage": s.speaking_percentage,
                "turn_count": s.turn_count,
            }
            for s in speaker_stats
        ],
    )
    pdf_bytes = report.render_report_pdf(html_doc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(meeting.title)}.pdf"'},
    )
