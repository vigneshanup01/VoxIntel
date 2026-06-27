"""Tiny audio helpers, independent of Whisper/Pyannote.

Shells out to `ffmpeg`/`ffprobe` (bundled with the `ffmpeg` package already
required for Whisper) rather than pulling in another Python audio library.
"""

import subprocess


def get_audio_duration_seconds(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def convert_to_wav(input_path: str, output_path: str) -> None:
    """Transcode any ffmpeg-readable file to mono 16kHz PCM WAV.

    Whisper decodes any container/codec itself by always shelling out to
    ffmpeg internally -- but Pyannote's audio loading goes through
    `soundfile`, which only understands raw containers like WAV/FLAC, not
    video containers (mp4/mov/mkv/webm) or the compressed codecs inside
    them. Without this conversion, diarization fails with "Format not
    recognised" on exactly the upload formats Phase 1 advertises support
    for, even though transcription of the same file already succeeded.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "16000", output_path],
        capture_output=True,
        text=True,
        check=True,
    )
