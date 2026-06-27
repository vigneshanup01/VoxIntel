"""Pyannote speaker diarization.

`pyannote.audio`/`torch` are only imported inside the functions below
(never at module load time), matching `app/worker/transcription.py`.

Important: diarization tells you "there are N distinct voices, and here's
when each one talks" -- it has no idea who any of them actually are. Labels
like SPEAKER_00 are consistent *within* one meeting and meaningless across
meetings. Naming an actual person is speaker recognition/enrollment, a
separate and harder feature this module deliberately does not attempt; see
`speaker_stats.display_name` for the (manual, user-driven) alternative.
"""

from collections.abc import Callable
from typing import Any

from app.core.config import get_settings

_pipeline = None

_STEP_LABELS = {
    "segmentation": "detecting speech segments",
    "speaker_counting": "estimating speaker count",
    "embeddings": "extracting voice embeddings",
    "discrete_diarization": "assigning speakers",
}


def _make_hook(on_progress: Callable[[str], None]) -> Callable:
    def hook(step_name: str, _step_artifact: Any, file: Any = None, total: int | None = None, completed: int | None = None) -> None:
        label = _STEP_LABELS.get(step_name, step_name.replace("_", " "))
        if completed is not None and total:
            on_progress(f"Diarization: {label} ({completed}/{total})")
        else:
            on_progress(f"Diarization: {label}")

    return hook


def get_diarization_pipeline() -> Any:
    """Load the Pyannote pipeline once per worker process and reuse it."""
    global _pipeline
    if _pipeline is None:
        settings = get_settings()
        if not settings.hf_token:
            raise RuntimeError(
                "HF_TOKEN is not set. pyannote/speaker-diarization-3.1 is a gated "
                "model: create a free Hugging Face account, accept the model's "
                "terms at https://huggingface.co/pyannote/speaker-diarization-3.1, "
                "generate an access token at https://huggingface.co/settings/tokens, "
                "and set HF_TOKEN to it."
            )

        import torch
        from pyannote.audio import Pipeline

        # torch>=2.6 defaults torch.load to weights_only=True, which rejects
        # the several custom pyannote classes (TorchVersion, Specifications,
        # ...) its pretrained checkpoint pickles in as metadata.
        # Allowlisting them one at a time is an open-ended chase; instead,
        # scope weights_only=False (full trust) to just this one load of an
        # official, known model repo, then restore the safe default
        # immediately after so nothing else in the process is affected.
        _original_torch_load = torch.load

        def _trusted_load(*args: Any, **kwargs: Any) -> Any:
            kwargs["weights_only"] = False
            return _original_torch_load(*args, **kwargs)

        torch.load = _trusted_load
        try:
            _pipeline = Pipeline.from_pretrained(settings.pyannote_pipeline_name, use_auth_token=settings.hf_token)
        finally:
            torch.load = _original_torch_load
    return _pipeline


def diarize_audio_file(path: str, on_progress: Callable[[str], None] | None = None) -> list[tuple[float, float, str]]:
    """Returns a list of (start_time, end_time, speaker_label) turns."""
    pipeline = get_diarization_pipeline()
    hook = _make_hook(on_progress) if on_progress else None
    diarization = pipeline(path, hook=hook)
    return [
        (float(turn.start), float(turn.end), str(speaker))
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
