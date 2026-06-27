import os
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from app.db.session import SessionLocal
from app.models.meeting import Meeting, MeetingStatus
from app.models.speaker_segment import SpeakerSegment
from app.models.speaker_stats import SpeakerStats
from app.models.transcript_segment import TranscriptSegment
from app.storage.s3_client import get_storage_client
from app.worker.alignment import assign_speaker_labels, compute_speaker_stats
from app.worker.audio import convert_to_wav, get_audio_duration_seconds
from app.worker.celery_app import celery_app
from app.worker.diarization import diarize_audio_file
from app.worker.transcription import segments_from_whisper_result, transcribe_audio_file

# Floor between progress writes: Whisper's tqdm hook can fire many times a
# second, and every call here is its own short-lived DB connection+commit.
_PROGRESS_WRITE_INTERVAL_SECONDS = 1.0


def _make_progress_reporter(meeting_id: str) -> Callable[[str], None]:
    """Best-effort, throttled progress text writer.

    Uses its own short-lived session rather than the calling task's --
    the callback fires synchronously from deep inside a blocking
    Whisper/Pyannote call, so it must not interact with whatever
    transaction state the main session happens to be in at that moment.
    """
    state = {"last_text": None, "last_time": 0.0}

    def report(text: str) -> None:
        now = time.monotonic()
        if text == state["last_text"] or now - state["last_time"] < _PROGRESS_WRITE_INTERVAL_SECONDS:
            return
        state["last_text"] = text
        state["last_time"] = now
        progress_db = SessionLocal()
        try:
            progress_db.query(Meeting).filter(Meeting.id == uuid.UUID(meeting_id)).update(
                {"processing_progress": text}
            )
            progress_db.commit()
        finally:
            progress_db.close()

    return report


def _fail(db, meeting_id: str, error_message: str) -> None:
    db.rollback()
    meeting = db.get(Meeting, uuid.UUID(meeting_id))
    if meeting is not None:
        meeting.status = MeetingStatus.FAILED
        meeting.processing_progress = None
        # Keep the tail, not the head: tools like ffmpeg dump a verbose
        # build banner before the actual error, which lands at the end.
        meeting.processing_error = error_message[-2000:]
        db.commit()


@celery_app.task(name="transcribe_meeting")
def transcribe_meeting(meeting_id: str) -> None:
    db = SessionLocal()
    failed = False
    try:
        meeting = db.get(Meeting, uuid.UUID(meeting_id))
        if meeting is None:
            return

        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_error = None
        meeting.processing_progress = None
        db.commit()

        storage = get_storage_client()
        suffix = Path(meeting.original_filename).suffix
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_path = tmp_file.name
                storage.download(meeting.storage_path, tmp_file)

            report_progress = _make_progress_reporter(meeting_id)
            report_progress("Transcribing audio: 0%")
            result = transcribe_audio_file(
                tmp_path, on_progress=lambda pct: report_progress(f"Transcribing audio: {pct}%")
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        # The progress reporter above writes through its own short-lived
        # sessions (see _make_progress_reporter) -- this session's cached
        # copy of `meeting` doesn't know about those external commits.
        # Without refreshing, `meeting.processing_progress = None` below
        # looks like a no-op change to SQLAlchemy (its last-known value was
        # already None) and the column silently keeps whatever the last
        # progress write left it as.
        db.refresh(meeting)

        rows = segments_from_whisper_result(result)
        for row in rows:
            db.add(TranscriptSegment(meeting_id=meeting.id, **row))

        meeting.language_detected = result.get("language")
        meeting.status = MeetingStatus.TRANSCRIBED
        meeting.processing_progress = None
        db.commit()
    except Exception as exc:
        # Worker boundary: never leave a meeting stuck at "processing" --
        # surface the failure on the row itself so the frontend can show it.
        _fail(db, meeting_id, str(exc))
        failed = True
    finally:
        db.close()

    if failed:
        return

    # Transcription and diarization are two independent pipelines over the
    # same audio, chained as separate tasks (not one giant function) so
    # each can fail/retry on its own.
    try:
        diarize_meeting.delay(meeting_id)
    except Exception as exc:
        db = SessionLocal()
        try:
            _fail(db, meeting_id, f"Could not queue for diarization: {exc}")
        finally:
            db.close()


@celery_app.task(name="diarize_meeting")
def diarize_meeting(meeting_id: str) -> None:
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, uuid.UUID(meeting_id))
        if meeting is None:
            return

        meeting.status = MeetingStatus.DIARIZING
        meeting.processing_progress = None
        db.commit()

        storage = get_storage_client()
        suffix = Path(meeting.original_filename).suffix
        tmp_path = None
        wav_path = None
        report_progress = _make_progress_reporter(meeting_id)
        try:
            report_progress("Diarization: downloading audio")
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_path = tmp_file.name
                storage.download(meeting.storage_path, tmp_file)

            duration = get_audio_duration_seconds(tmp_path)

            # Pyannote can't read most upload formats directly (see
            # convert_to_wav's docstring) -- always hand it a clean WAV.
            report_progress("Diarization: converting audio format")
            wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(wav_fd)
            convert_to_wav(tmp_path, wav_path)

            raw_turns = diarize_audio_file(wav_path, on_progress=report_progress)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)

        # See the matching comment in transcribe_meeting: the progress
        # reporter wrote through separate sessions, so this session's
        # cached `meeting` needs a refresh before we touch it again.
        db.refresh(meeting)

        report_progress("Diarization: saving results")
        speaker_rows = [
            {"start_time": start, "end_time": end, "speaker_label": label} for start, end, label in raw_turns
        ]
        for row in speaker_rows:
            db.add(SpeakerSegment(meeting_id=meeting.id, **row))

        for stat in compute_speaker_stats(speaker_rows, duration):
            db.add(SpeakerStats(meeting_id=meeting.id, **stat))

        transcript_segments = (
            db.query(TranscriptSegment)
            .filter(TranscriptSegment.meeting_id == meeting.id)
            .order_by(TranscriptSegment.start_time)
            .all()
        )
        transcript_rows = [{"start_time": t.start_time, "end_time": t.end_time} for t in transcript_segments]
        labels = assign_speaker_labels(transcript_rows, speaker_rows)
        for segment, label in zip(transcript_segments, labels):
            segment.speaker_label = label

        if meeting.duration_seconds is None:
            meeting.duration_seconds = duration

        meeting.status = MeetingStatus.COMPLETED
        meeting.processing_progress = None
        db.commit()
    except Exception as exc:
        _fail(db, meeting_id, str(exc))
    finally:
        db.close()
