from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.search import TranscriptSearchResponse, TranscriptSearchResult
from app.search import service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/transcripts", response_model=TranscriptSearchResponse)
def search_transcripts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptSearchResponse:
    rows, total = service.search_transcripts(db, owner_id=current_user.id, query=q, limit=limit, offset=offset)
    results = [
        TranscriptSearchResult(
            meeting_id=segment.meeting_id,
            meeting_title=title,
            segment_id=segment.id,
            start_time=segment.start_time,
            speaker_label=segment.speaker_label,
            snippet=segment.text,
        )
        for segment, title in rows
    ]
    return TranscriptSearchResponse(results=results, total=total, limit=limit, offset=offset)
