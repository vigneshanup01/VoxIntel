from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import service
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.analytics import SpeakerAnalyticsEntry, SpeakerAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/speakers", response_model=SpeakerAnalyticsResponse)
def get_speaker_analytics(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakerAnalyticsResponse:
    data = service.get_speaker_analytics(db, owner_id=current_user.id, date_from=date_from, date_to=date_to)
    return SpeakerAnalyticsResponse(
        speakers=[SpeakerAnalyticsEntry(**s) for s in data["speakers"]],
        unnamed_speaker_rows_excluded=data["unnamed_speaker_rows_excluded"],
    )
