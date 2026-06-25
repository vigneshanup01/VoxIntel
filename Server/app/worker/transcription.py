"""Whisper integration.

`whisper`/`torch` are only imported inside the functions below (never at
module load time), so the pure result-mapping logic can be unit-tested
without those heavy, worker-only dependencies installed.
"""

from typing import Any

from app.core.config import get_settings

_model = None


def get_whisper_model() -> Any:
    """Load the Whisper model once per worker process and reuse it.

    Loading the model is the slow part -- reloading it per job would tank
    worker throughput, so this is cached as a module-level singleton.
    """
    global _model
    if _model is None:
        import whisper

        _model = whisper.load_model(get_settings().whisper_model_size)
    return _model


def transcribe_audio_file(path: str) -> dict:
    model = get_whisper_model()
    return model.transcribe(path, verbose=False)


def segments_from_whisper_result(result: dict) -> list[dict]:
    """Map Whisper's raw `segments` list to transcript_segments row dicts."""
    rows = []
    for segment in result.get("segments", []):
        rows.append(
            {
                "start_time": float(segment["start"]),
                "end_time": float(segment["end"]),
                "text": segment["text"].strip(),
                "confidence": segment.get("avg_logprob"),
            }
        )
    return rows
