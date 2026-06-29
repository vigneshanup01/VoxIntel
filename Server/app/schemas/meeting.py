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
    language_detected: str | None
    processing_error: str | None
    processing_progress: str | None
    uploaded_at: datetime


class MeetingListResponse(BaseModel):
    meetings: list[MeetingOut]


class MeetingSearchResponse(BaseModel):
    meetings: list[MeetingOut]
    total: int
    limit: int
    offset: int


class MeetingStatusOut(BaseModel):
    status: str
    processing_error: str | None
    processing_progress: str | None
