"""Aligning Whisper transcript segments with Pyannote speaker segments.

These two pipelines know nothing about each other -- Whisper doesn't know
about speakers, Pyannote doesn't know about words. This module is the glue:
pure functions operating on plain dicts (no ORM, no ML imports), so the
alignment logic -- the actual hard part of this phase -- is fully
unit-testable without a database or any model loaded.
"""


def overlap_seconds(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def best_matching_speaker(segment: dict, speaker_segments: list[dict]) -> str | None:
    """Assign whichever speaker segment covers the most of this segment's
    duration -- NOT whichever starts closest. A transcript segment can
    straddle a speaker change, so "closest start" picks the wrong speaker
    at boundaries; "maximum overlap" doesn't.

    Ties (equal overlap) go to whichever speaker segment appears first in
    the input list.
    """
    best_label = None
    best_overlap = 0.0
    for sp in speaker_segments:
        overlap = overlap_seconds(segment["start_time"], segment["end_time"], sp["start_time"], sp["end_time"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = sp["speaker_label"]
    return best_label


def assign_speaker_labels(transcript_segments: list[dict], speaker_segments: list[dict]) -> list[str | None]:
    """Returns one speaker label (or None) per transcript segment, in order.

    None means no speaker segment overlapped at all -- Pyannote only emits
    segments where it detects speech, so silence/non-speech gaps are
    expected, not an error.
    """
    return [best_matching_speaker(segment, speaker_segments) for segment in transcript_segments]


def count_speaking_turns(speaker_segments: list[dict]) -> dict[str, int]:
    """A turn is a contiguous run (in time order) of segments from the same
    speaker. Two back-to-back segments from the same speaker count as one
    turn; a speaker change -- even after a silence gap -- starts a new one.
    """
    ordered = sorted(speaker_segments, key=lambda s: s["start_time"])
    counts: dict[str, int] = {}
    previous_label = None
    for seg in ordered:
        label = seg["speaker_label"]
        if label != previous_label:
            counts[label] = counts.get(label, 0) + 1
            previous_label = label
    return counts


def compute_speaker_stats(speaker_segments: list[dict], meeting_duration: float) -> list[dict]:
    """Per-speaker totals: speaking time, turn count, and share of the
    meeting. Returned sorted by speaking time descending (most talkative
    first) -- a reasonable default for display, not a semantic requirement.
    """
    ordered = sorted(speaker_segments, key=lambda s: s["start_time"])

    totals: dict[str, float] = {}
    for seg in ordered:
        duration = max(0.0, seg["end_time"] - seg["start_time"])
        totals[seg["speaker_label"]] = totals.get(seg["speaker_label"], 0.0) + duration

    turn_counts = count_speaking_turns(ordered)

    stats = [
        {
            "speaker_label": label,
            "total_speaking_seconds": total_seconds,
            "speaking_percentage": (total_seconds / meeting_duration * 100) if meeting_duration > 0 else 0.0,
            "turn_count": turn_counts.get(label, 0),
        }
        for label, total_seconds in totals.items()
    ]
    return sorted(stats, key=lambda s: -s["total_speaking_seconds"])
