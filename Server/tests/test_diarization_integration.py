"""Real end-to-end diarization test against a checked-in multi-speaker
sample (two different synthesized voices taking turns).

Mirrors test_whisper_integration.py: this is the ONE test that loads the
actual Pyannote pipeline and runs real inference. It auto-skips wherever
`pyannote.audio` isn't installed, `ffmpeg` isn't on PATH, or HF_TOKEN isn't
set -- pyannote/speaker-diarization-3.1 is a gated model and there is no
way around providing your own token (see Server/.env.example).
"""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pyannote.audio", reason="pyannote.audio is a worker-only dependency, not installed here")

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not available on PATH", allow_module_level=True)

from app.core.config import get_settings  # noqa: E402
from app.worker.alignment import compute_speaker_stats  # noqa: E402
from app.worker.diarization import diarize_audio_file  # noqa: E402

if not get_settings().hf_token:
    pytest.skip(
        "HF_TOKEN is not set -- pyannote/speaker-diarization-3.1 is a gated model, "
        "see Server/.env.example for setup steps",
        allow_module_level=True,
    )

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multi_speaker_sample.wav"


def test_diarizes_real_multi_speaker_sample_end_to_end() -> None:
    turns = diarize_audio_file(str(FIXTURE_PATH))
    assert len(turns) >= 1

    speaker_rows = [{"start_time": s, "end_time": e, "speaker_label": label} for s, e, label in turns]
    distinct_speakers = {row["speaker_label"] for row in speaker_rows}

    # The fixture has two distinct synthesized voices taking turns -- a
    # working pipeline should find more than one.
    assert len(distinct_speakers) > 1

    stats = compute_speaker_stats(speaker_rows, meeting_duration=turns[-1][1])
    total_percentage = sum(s["speaking_percentage"] for s in stats)
    assert 0 < total_percentage <= 100.0
