"""Real end-to-end Whisper test against a checked-in sample audio file.

This is deliberately the ONE test in the suite that loads the actual model
and runs real inference -- everything else uses
`app.worker.transcription.segments_from_whisper_result` with fixture dicts,
which is fast and has no ML dependencies. This test is automatically skipped
wherever `openai-whisper` or `ffmpeg` aren't installed (e.g. the lean API
dev environment), so it only runs where the full worker stack is present.
"""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("whisper", reason="openai-whisper is a worker-only dependency, not installed here")

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available on PATH", allow_module_level=True)

from app.worker.transcription import segments_from_whisper_result, transcribe_audio_file  # noqa: E402

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_speech.wav"


def test_transcribes_real_sample_audio_end_to_end() -> None:
    result = transcribe_audio_file(str(FIXTURE_PATH))
    rows = segments_from_whisper_result(result)

    assert len(rows) >= 1
    full_text = " ".join(row["text"] for row in rows).lower()
    assert "meeting" in full_text or "voxintel" in full_text or "test" in full_text
