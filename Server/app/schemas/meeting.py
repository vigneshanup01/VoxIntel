import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    original_filename: str
    duration_seconds: float | None
    status: str
    uploaded_at: datetime


class MeetingListResponse(BaseModel):
    meetings: list[MeetingOut]
