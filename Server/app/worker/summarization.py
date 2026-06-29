"""LLM-based meeting summarization.

`anthropic` is only imported inside `_request_json` (never at module load
time), matching `app/worker/transcription.py` and `app/worker/diarization.py`
-- the prompt-building, chunking, and JSON-validation logic below has no ML/
network dependency and is fully unit-testable without it installed.

Structured output (`output_config.format` with a JSON schema) guarantees the
*shape* of a successful response, but a refusal or a `max_tokens` cutoff can
still leave the response text empty or truncated -- `_request_validated`
retries once with a stricter nudge before giving up, rather than failing the
whole summarization job over one bad response.
"""

import json
from collections.abc import Callable

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings

# Above this many transcript characters, summarize in chunks (map) and
# combine the partial summaries afterward (reduce) instead of one shot.
# There's no hard context-window reason for this -- Claude's context window
# comfortably fits an entire meeting transcript -- but a single very long
# prompt produces shallower, less-grounded summaries than several focused
# passes, and bounds the cost/latency of any one call.
SINGLE_PASS_CHAR_LIMIT = 60_000

DEFAULT_MAX_TOKENS = 8000
CHUNK_MAX_TOKENS = 4000
REDUCE_MAX_TOKENS = 4000


# --- JSON schemas (passed to output_config.format for structured output) ---

ACTION_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "owner": {"type": ["string", "null"]},
        "due_date": {"type": ["string", "null"]},
    },
    "required": ["description", "owner", "due_date"],
    "additionalProperties": False,
}

DECISION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
    "additionalProperties": False,
}

QUOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "quote_text": {"type": "string"},
        "speaker_label": {"type": ["string", "null"]},
        "timestamp_seconds": {"type": ["number", "null"]},
        "category": {"type": "string", "enum": ["notable", "risk"]},
    },
    "required": ["quote_text", "speaker_label", "timestamp_seconds", "category"],
    "additionalProperties": False,
}

SUMMARY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "detailed_summary": {"type": "string"},
        "action_items": {"type": "array", "items": ACTION_ITEM_SCHEMA},
        "decisions": {"type": "array", "items": DECISION_SCHEMA},
        "quotes": {"type": "array", "items": QUOTE_SCHEMA},
    },
    "required": ["executive_summary", "detailed_summary", "action_items", "decisions", "quotes"],
    "additionalProperties": False,
}

CHUNK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "chunk_summary": {"type": "string"},
        "action_items": {"type": "array", "items": ACTION_ITEM_SCHEMA},
        "decisions": {"type": "array", "items": DECISION_SCHEMA},
        "quotes": {"type": "array", "items": QUOTE_SCHEMA},
    },
    "required": ["chunk_summary", "action_items", "decisions", "quotes"],
    "additionalProperties": False,
}

REDUCE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "detailed_summary": {"type": "string"},
    },
    "required": ["executive_summary", "detailed_summary"],
    "additionalProperties": False,
}


# --- Pydantic models the JSON responses above are validated against -------


class ActionItemPayload(BaseModel):
    description: str
    owner: str | None = None
    due_date: str | None = None


class DecisionPayload(BaseModel):
    description: str


class QuotePayload(BaseModel):
    quote_text: str
    speaker_label: str | None = None
    timestamp_seconds: float | None = None
    category: str = "notable"


class ChunkPayload(BaseModel):
    chunk_summary: str
    action_items: list[ActionItemPayload] = Field(default_factory=list)
    decisions: list[DecisionPayload] = Field(default_factory=list)
    quotes: list[QuotePayload] = Field(default_factory=list)


class ReducePayload(BaseModel):
    executive_summary: str
    detailed_summary: str


class SummaryPayload(BaseModel):
    executive_summary: str
    detailed_summary: str
    action_items: list[ActionItemPayload] = Field(default_factory=list)
    decisions: list[DecisionPayload] = Field(default_factory=list)
    quotes: list[QuotePayload] = Field(default_factory=list)


# --- Pure prompt-building / chunking logic (no network, fully testable) ---


def _format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def build_transcript_text(segments: list[dict], display_names: dict[str, str] | None = None) -> str:
    """Render transcript_segments rows as "[mm:ss] Speaker: text" lines,
    resolving each speaker_label to its user-set display_name when one
    exists (falling back to the raw label, e.g. "SPEAKER_00")."""
    display_names = display_names or {}
    lines = []
    for segment in segments:
        label = segment.get("speaker_label")
        speaker = display_names.get(label, label) if label else "Unknown speaker"
        timestamp = _format_timestamp(segment.get("start_time", 0.0))
        lines.append(f"[{timestamp}] {speaker}: {segment.get('text', '').strip()}")
    return "\n".join(lines)


def chunk_segments(segments: list[dict], max_chars: int) -> list[list[dict]]:
    """Greedily group consecutive segments into chunks of roughly
    `max_chars` of transcript text each. Never splits a single segment --
    an oversized one gets its own (over-limit) chunk rather than being cut
    mid-sentence."""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_len = 0
    for segment in segments:
        text_len = len(segment.get("text", ""))
        if current and current_len + text_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(segment)
        current_len += text_len
    if current:
        chunks.append(current)
    return chunks


def build_summary_prompt(transcript_text: str) -> str:
    return (
        "You are an assistant that produces structured meeting summaries from a "
        'timestamped transcript. Each line is formatted as "[mm:ss] Speaker: text".\n\n'
        "Read the transcript below and produce:\n"
        "- executive_summary: 2-4 sentences a busy exec could read in 10 seconds.\n"
        "- detailed_summary: a thorough multi-paragraph account of what was discussed.\n"
        "- action_items: concrete follow-up tasks, with an owner (the speaker who "
        "committed to it, if stated) and a due date if one was mentioned (write it "
        'exactly as said, e.g. "next Friday" -- never invent a date).\n'
        "- decisions: concrete decisions the group reached.\n"
        "- quotes: notable or risky verbatim quotes worth flagging, each tagged "
        '"notable" or "risk", with the speaker and the timestamp in seconds it came '
        "from.\n\n"
        "Only use information present in the transcript. If a field has nothing to "
        "report, return an empty list for it.\n\n"
        f"Transcript:\n{transcript_text}"
    )


def build_chunk_prompt(transcript_text: str, chunk_index: int, chunk_count: int) -> str:
    return (
        f"This is part {chunk_index + 1} of {chunk_count} of a meeting transcript, "
        'split because the full meeting is long. Each line is formatted as "[mm:ss] '
        'Speaker: text".\n\n'
        "Summarize ONLY this part in chunk_summary (a few sentences), and extract any "
        "action_items, decisions, and notable/risk quotes mentioned in this part. "
        "Only use information present in this part of the transcript -- if a field has "
        "nothing to report, return an empty list for it.\n\n"
        f"Transcript (part {chunk_index + 1} of {chunk_count}):\n{transcript_text}"
    )


def build_reduce_prompt(chunk_summaries: list[str]) -> str:
    joined = "\n\n".join(f"Part {i + 1}: {summary}" for i, summary in enumerate(chunk_summaries))
    return (
        "Below are summaries of consecutive parts of one long meeting, in order. "
        "Combine them into a single coherent summary of the whole meeting:\n"
        "- executive_summary: 2-4 sentences a busy exec could read in 10 seconds.\n"
        "- detailed_summary: a thorough multi-paragraph account of the whole meeting, "
        "synthesized across all parts (not just concatenated).\n\n"
        f"{joined}"
    )


# --- Anthropic API call + defensive parsing --------------------------------


def _request_json(prompt: str, schema: dict, *, max_tokens: int) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Generate a key at "
            "https://console.anthropic.com/settings/keys and set it -- see "
            "Server/.env.example."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to summarize this meeting (safety refusal).")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise RuntimeError("Claude returned no text content for the summarization request.")
    return text


def _request_validated(prompt: str, schema: dict, model: type[BaseModel], *, max_tokens: int) -> BaseModel:
    last_error: Exception | None = None
    current_prompt = prompt
    for _attempt in range(2):
        try:
            text = _request_json(current_prompt, schema, max_tokens=max_tokens)
            return model.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            current_prompt = (
                f"{prompt}\n\nYour previous response was not valid JSON matching the "
                "required schema. Respond again with ONLY the JSON object, no other text."
            )
    raise RuntimeError(f"Claude did not return valid JSON after a retry: {last_error}")


# --- Orchestration ----------------------------------------------------------


def summarize_transcript(
    segments: list[dict],
    display_names: dict[str, str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> SummaryPayload:
    """Single entry point used by the `summarize_meeting` Celery task.

    Dispatches to a single LLM call for ordinary-length meetings, or a
    map-reduce pass (per-chunk extraction, then a final pass that combines
    the partial summaries) once the transcript exceeds `SINGLE_PASS_CHAR_LIMIT`.
    """
    display_names = display_names or {}
    report = on_progress or (lambda _text: None)

    if not segments:
        return SummaryPayload(
            executive_summary="No speech was detected in this recording.",
            detailed_summary="",
        )

    transcript_text = build_transcript_text(segments, display_names)

    if len(transcript_text) <= SINGLE_PASS_CHAR_LIMIT:
        report("Summarizing: analyzing transcript")
        prompt = build_summary_prompt(transcript_text)
        result = _request_validated(prompt, SUMMARY_JSON_SCHEMA, SummaryPayload, max_tokens=DEFAULT_MAX_TOKENS)
        assert isinstance(result, SummaryPayload)
        return result

    chunks = chunk_segments(segments, SINGLE_PASS_CHAR_LIMIT)
    chunk_summaries: list[str] = []
    action_items: list[ActionItemPayload] = []
    decisions: list[DecisionPayload] = []
    quotes: list[QuotePayload] = []

    for index, chunk in enumerate(chunks):
        report(f"Summarizing: analyzing part {index + 1}/{len(chunks)}")
        chunk_text = build_transcript_text(chunk, display_names)
        prompt = build_chunk_prompt(chunk_text, index, len(chunks))
        chunk_result = _request_validated(prompt, CHUNK_JSON_SCHEMA, ChunkPayload, max_tokens=CHUNK_MAX_TOKENS)
        assert isinstance(chunk_result, ChunkPayload)
        chunk_summaries.append(chunk_result.chunk_summary)
        action_items.extend(chunk_result.action_items)
        decisions.extend(chunk_result.decisions)
        quotes.extend(chunk_result.quotes)

    report("Summarizing: combining parts")
    reduce_prompt = build_reduce_prompt(chunk_summaries)
    reduced = _request_validated(reduce_prompt, REDUCE_JSON_SCHEMA, ReducePayload, max_tokens=REDUCE_MAX_TOKENS)
    assert isinstance(reduced, ReducePayload)

    return SummaryPayload(
        executive_summary=reduced.executive_summary,
        detailed_summary=reduced.detailed_summary,
        action_items=action_items,
        decisions=decisions,
        quotes=quotes,
    )
