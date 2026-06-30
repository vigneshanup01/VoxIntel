"""Whisper integration.

`whisper`/`torch` are only imported inside the functions below (never at
module load time), so the pure result-mapping logic can be unit-tested
without those heavy, worker-only dependencies installed.
"""

import sys
import types
from collections.abc import Callable
from typing import Any

from app.core.config import get_settings

_model = None


def get_whisper_model() -> Any:
    """Load the Whisper model once per worker process and reuse it."""
    global _model
    if _model is None:
        import whisper

        _model = whisper.load_model(get_settings().whisper_model_size)
    return _model


def release_whisper_model() -> None:
    """Unload the Whisper model from RAM.

    Called after transcription completes and before diarization starts so
    both models (Whisper + pyannote) are not in memory at the same time.
    On a memory-constrained worker (e.g. Railway free tier) this is the
    difference between diarization fitting in RAM or hitting OOM.
    """
    global _model
    if _model is not None:
        import gc

        del _model
        _model = None
        gc.collect()


def transcribe_audio_file(path: str, on_progress: Callable[[int], None] | None = None) -> dict:
    model = get_whisper_model()

    if on_progress is None:
        return model.transcribe(path, verbose=False)

    # whisper.transcribe() always drives a `tqdm.tqdm(total=content_frames,
    # unit="frames", ...)` bar internally with no public callback hook, so
    # we report progress by swapping out the `tqdm` name *inside whisper's
    # own module namespace only* for a subclass that forwards `update()`
    # calls to `on_progress`. The real `tqdm` package elsewhere in the
    # process is untouched -- restored immediately after, regardless of
    # outcome, same pattern as the torch.load patch in diarization.py.
    import tqdm as real_tqdm
    import whisper  # noqa: F401 -- ensures whisper.transcribe is registered in sys.modules

    # NOT `import whisper.transcribe as X`: whisper/__init__.py does
    # `from .transcribe import transcribe`, which overwrites the
    # *package's* `transcribe` attribute with that function, shadowing the
    # submodule of the same name. `import ... as X` resolves through that
    # shadowed attribute and would hand us the function, not the module.
    # Going through sys.modules bypasses the shadowing entirely.
    whisper_transcribe_module = sys.modules["whisper.transcribe"]

    def _make_reporting_tqdm() -> type:
        class ReportingTqdm(real_tqdm.tqdm):
            def update(self, n: int = 1) -> None:
                super().update(n)
                if self.total:
                    on_progress(min(99, int(self.n / self.total * 100)))

        return ReportingTqdm

    original = whisper_transcribe_module.tqdm
    whisper_transcribe_module.tqdm = types.SimpleNamespace(tqdm=_make_reporting_tqdm())
    try:
        return model.transcribe(path, verbose=False)
    finally:
        whisper_transcribe_module.tqdm = original


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
