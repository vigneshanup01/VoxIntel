"""Real end-to-end summarization test against the live Claude API.

Mirrors test_whisper_integration.py / test_diarization_integration.py: this
is the ONE test that makes a real network call and spends real tokens. It
auto-skips wherever `anthropic` isn't installed or `ANTHROPIC_API_KEY` isn't
set -- see Server/.env.example for how to get a key.
"""

import pytest

pytest.importorskip("anthropic", reason="anthropic is a worker-only dependency, not installed here")

from app.core.config import get_settings  # noqa: E402
from app.worker.summarization import summarize_transcript  # noqa: E402

if not get_settings().anthropic_api_key:
    pytest.skip(
        "ANTHROPIC_API_KEY is not set -- see Server/.env.example for setup steps",
        allow_module_level=True,
    )

TRANSCRIPT = [
    {"start_time": 0.0, "speaker_label": "SPEAKER_00", "text": "Let's kick off the Q3 planning sync."},
    {"start_time": 4.0, "speaker_label": "SPEAKER_01", "text": "I'll have the budget numbers ready by Friday."},
    {
        "start_time": 9.0,
        "speaker_label": "SPEAKER_00",
        "text": "Great, let's go with the smaller office space then -- decision made.",
    },
    {
        "start_time": 14.0,
        "speaker_label": "SPEAKER_01",
        "text": "Honestly, if we don't ship this on time we're going to lose the client.",
    },
]


def test_summarizes_real_short_transcript_end_to_end() -> None:
    result = summarize_transcript(TRANSCRIPT, display_names={"SPEAKER_00": "Priya", "SPEAKER_01": "Sam"})

    assert result.executive_summary
    assert result.detailed_summary
    # Not asserting exact content (LLM output is non-deterministic) -- just
    # that the structured-output pipeline produced a sane, non-empty shape.
    assert isinstance(result.action_items, list)
    assert isinstance(result.decisions, list)
    assert isinstance(result.quotes, list)
