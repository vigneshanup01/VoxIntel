import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeetingSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    executive_summary: str
    detailed_summary: str
    model_used: str
    generated_at: datetime


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    owner: str | None
    due_date: str | None
    is_completed: bool


class ActionItemListResponse(BaseModel):
    action_items: list[ActionItemOut]


class ActionItemUpdateRequest(BaseModel):
    is_completed: bool


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str


class DecisionListResponse(BaseModel):
    decisions: list[DecisionOut]


class MeetingQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quote_text: str
    speaker_label: str | None
    timestamp_seconds: float | None
    category: str


class MeetingQuoteListResponse(BaseModel):
    quotes: list[MeetingQuoteOut]
