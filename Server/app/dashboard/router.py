from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dashboard import service
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryOut
from app.schemas.meeting import MeetingOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryOut:
    data = service.get_dashboard_summary(db, owner_id=current_user.id)
    return DashboardSummaryOut(
        total_meetings=data["total_meetings"],
        total_hours=data["total_hours"],
        meetings_this_week=data["meetings_this_week"],
        most_active_speaker=data["most_active_speaker"],
        recent_meetings=[MeetingOut.model_validate(m) for m in data["recent_meetings"]],
    )
