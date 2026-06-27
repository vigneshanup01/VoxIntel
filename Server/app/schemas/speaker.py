from pydantic import BaseModel, ConfigDict, Field


class SpeakerStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    speaker_label: str
    display_name: str | None
    total_speaking_seconds: float
    speaking_percentage: float
    turn_count: int


class SpeakerStatsListResponse(BaseModel):
    speakers: list[SpeakerStatsOut]


class RenameSpeakerRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
