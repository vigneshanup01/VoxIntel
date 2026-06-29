import uuid

from pydantic import BaseModel


class TranscriptSearchResult(BaseModel):
    meeting_id: uuid.UUID
    meeting_title: str
    segment_id: uuid.UUID
    start_time: float
    speaker_label: str | None
    snippet: str


class TranscriptSearchResponse(BaseModel):
    results: list[TranscriptSearchResult]
    total: int
    limit: int
    offset: int
