from pydantic import BaseModel

from app.schemas.meeting import MeetingOut


class DashboardSummaryOut(BaseModel):
    total_meetings: int
    total_hours: float
    meetings_this_week: int
    most_active_speaker: str | None
    recent_meetings: list[MeetingOut]
