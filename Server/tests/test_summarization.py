import pytest

from app.worker import summarization
from app.worker.summarization import (
    ActionItemPayload,
    ChunkPayload,
    DecisionPayload,
    QuotePayload,
    ReducePayload,
    SummaryPayload,
    build_chunk_prompt,
    build_reduce_prompt,
    build_summary_prompt,
    build_transcript_text,
    chunk_segments,
    summarize_transcript,
)


def segment(start: float, text: str, speaker_label: str | None = "SPEAKER_00") -> dict:
    return {"start_time": start, "text": text, "speaker_label": speaker_label}


# --- build_transcript_text --------------------------------------------------


def test_build_transcript_text_formats_timestamp_and_speaker() -> None:
    text = build_transcript_text([segment(65.0, "Let's get started.")])

    assert text == "[1:05] SPEAKER_00: Let's get started."


def test_build_transcript_text_resolves_display_name() -> None:
    text = build_transcript_text([segment(0.0, "Hello")], {"SPEAKER_00": "Alice"})

    assert text == "[0:00] Alice: Hello"


def test_build_transcript_text_handles_missing_speaker_label() -> None:
    text = build_transcript_text([segment(0.0, "Hello", speaker_label=None)])

    assert text == "[0:00] Unknown speaker: Hello"


def test_build_transcript_text_joins_multiple_lines() -> None:
    text = build_transcript_text([segment(0.0, "Hi"), segment(2.0, "Hey")])

    assert text == "[0:00] SPEAKER_00: Hi\n[0:02] SPEAKER_00: Hey"


# --- chunk_segments ----------------------------------------------------------


def test_chunk_segments_single_chunk_when_under_limit() -> None:
    segments = [segment(0.0, "short"), segment(1.0, "also short")]

    assert chunk_segments(segments, max_chars=1000) == [segments]


def test_chunk_segments_splits_once_limit_exceeded() -> None:
    segments = [segment(0.0, "a" * 50), segment(1.0, "b" * 50), segment(2.0, "c" * 50)]

    chunks = chunk_segments(segments, max_chars=80)

    assert chunks == [[segments[0]], [segments[1]], [segments[2]]]


def test_chunk_segments_packs_multiple_segments_per_chunk() -> None:
    segments = [segment(0.0, "a" * 30), segment(1.0, "b" * 30), segment(2.0, "c" * 30)]

    chunks = chunk_segments(segments, max_chars=70)

    assert chunks == [[segments[0], segments[1]], [segments[2]]]


def test_chunk_segments_oversized_single_segment_gets_its_own_chunk() -> None:
    segments = [segment(0.0, "x" * 200)]

    assert chunk_segments(segments, max_chars=50) == [segments]


def test_chunk_segments_empty_input() -> None:
    assert chunk_segments([], max_chars=100) == []


# --- prompt builders (assert key content/ordering is present) ---------------


def test_build_summary_prompt_includes_transcript() -> None:
    prompt = build_summary_prompt("[0:00] Alice: hello")

    assert "[0:00] Alice: hello" in prompt
    assert "executive_summary" in prompt


def test_build_chunk_prompt_includes_part_numbers() -> None:
    prompt = build_chunk_prompt("[0:00] Alice: hello", chunk_index=1, chunk_count=3)

    assert "part 2 of 3" in prompt
    assert "[0:00] Alice: hello" in prompt


def test_build_reduce_prompt_includes_all_parts_in_order() -> None:
    prompt = build_reduce_prompt(["first part", "second part"])

    assert "Part 1: first part" in prompt
    assert "Part 2: second part" in prompt
    assert prompt.index("Part 1") < prompt.index("Part 2")


# --- _request_validated: defensive JSON parsing + retry-once ----------------


def test_request_validated_returns_on_first_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        summarization, "_request_json", lambda prompt, schema, max_tokens: '{"description": "Ship the report"}'
    )

    result = summarization._request_validated(
        "prompt", summarization.DECISION_SCHEMA, DecisionPayload, max_tokens=10
    )

    assert isinstance(result, DecisionPayload)
    assert result.description == "Ship the report"


def test_request_validated_retries_once_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_request(prompt: str, schema: dict, max_tokens: int) -> str:
        calls["count"] += 1
        return "not json at all" if calls["count"] == 1 else '{"description": "Ship the report"}'

    monkeypatch.setattr(summarization, "_request_json", fake_request)

    result = summarization._request_validated(
        "prompt", summarization.DECISION_SCHEMA, DecisionPayload, max_tokens=10
    )

    assert calls["count"] == 2
    assert result.description == "Ship the report"


def test_request_validated_retries_on_schema_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid JSON missing a required field should also trigger the retry path."""
    calls = {"count": 0}

    def fake_request(prompt: str, schema: dict, max_tokens: int) -> str:
        calls["count"] += 1
        return "{}" if calls["count"] == 1 else '{"description": "Ship the report"}'

    monkeypatch.setattr(summarization, "_request_json", fake_request)

    result = summarization._request_validated(
        "prompt", summarization.DECISION_SCHEMA, DecisionPayload, max_tokens=10
    )

    assert calls["count"] == 2
    assert result.description == "Ship the report"


def test_request_validated_raises_after_two_failed_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(summarization, "_request_json", lambda prompt, schema, max_tokens: "still not json")

    with pytest.raises(RuntimeError, match="did not return valid JSON"):
        summarization._request_validated("prompt", summarization.DECISION_SCHEMA, DecisionPayload, max_tokens=10)


def test_request_json_raises_clear_error_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        summarization._request_json("prompt", summarization.DECISION_SCHEMA, max_tokens=10)


# --- summarize_transcript orchestration -------------------------------------


def test_summarize_transcript_returns_placeholder_for_empty_transcript() -> None:
    result = summarize_transcript([])

    assert isinstance(result, SummaryPayload)
    assert result.action_items == []
    assert result.detailed_summary == ""


def test_summarize_transcript_single_pass_for_short_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_validated(prompt, schema, model, *, max_tokens):
        captured["model"] = model
        return SummaryPayload(
            executive_summary="Exec summary",
            detailed_summary="Detailed summary",
            action_items=[ActionItemPayload(description="Do X")],
            decisions=[DecisionPayload(description="Decided Y")],
            quotes=[QuotePayload(quote_text="quote", category="risk")],
        )

    monkeypatch.setattr(summarization, "_request_validated", fake_validated)

    result = summarize_transcript([segment(0.0, "short meeting")])

    assert captured["model"] is SummaryPayload
    assert result.executive_summary == "Exec summary"
    assert result.action_items[0].description == "Do X"


def test_summarize_transcript_chunks_long_transcript_and_reduces(monkeypatch: pytest.MonkeyPatch) -> None:
    long_segments = [segment(float(i), "x" * 100) for i in range(5)]
    monkeypatch.setattr(summarization, "SINGLE_PASS_CHAR_LIMIT", 150)

    calls = []

    def fake_validated(prompt, schema, model, *, max_tokens):
        calls.append(model)
        if model is ChunkPayload:
            return ChunkPayload(
                chunk_summary="partial",
                action_items=[ActionItemPayload(description="task")],
                decisions=[DecisionPayload(description="decision")],
                quotes=[QuotePayload(quote_text="q")],
            )
        if model is ReducePayload:
            return ReducePayload(executive_summary="combined exec", detailed_summary="combined detail")
        raise AssertionError(f"unexpected model {model}")

    monkeypatch.setattr(summarization, "_request_validated", fake_validated)

    result = summarize_transcript(long_segments)

    assert calls.count(ChunkPayload) == 5  # one call per chunk (5 oversized segments -> 5 chunks)
    assert calls[-1] is ReducePayload
    assert result.executive_summary == "combined exec"
    assert result.detailed_summary == "combined detail"
    assert len(result.action_items) == 5
    assert all(item.description == "task" for item in result.action_items)


def test_summarize_transcript_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        summarization,
        "_request_validated",
        lambda prompt, schema, model, *, max_tokens: SummaryPayload(executive_summary="e", detailed_summary="d"),
    )
    progress_messages: list[str] = []

    summarize_transcript([segment(0.0, "hi")], on_progress=progress_messages.append)

    assert any("Summarizing" in msg for msg in progress_messages)
