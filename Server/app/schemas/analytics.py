from pydantic import BaseModel


class SpeakerAnalyticsEntry(BaseModel):
    display_name: str
    total_speaking_seconds: float
    meeting_count: int


class SpeakerAnalyticsResponse(BaseModel):
    speakers: list[SpeakerAnalyticsEntry]
    # Speaker rows with no display_name set -- SPEAKER_00 in one meeting and
    # SPEAKER_00 in another are not the same person, so they can't be merged
    # into a cross-meeting total. This is a count of how many such rows were
    # left out, surfaced so the UI/report can say so explicitly rather than
    # silently under-reporting.
    unnamed_speaker_rows_excluded: int
