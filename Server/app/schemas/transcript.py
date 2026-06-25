import uuid

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    start_time: float
    end_time: float
    text: str
    speaker_label: str | None
    confidence: float | None


class TranscriptResponse(BaseModel):
    segments: list[TranscriptSegmentOut]
