import os
import tempfile
import uuid
from pathlib import Path

from app.db.session import SessionLocal
from app.models.meeting import Meeting, MeetingStatus
from app.models.transcript_segment import TranscriptSegment
from app.storage.s3_client import get_storage_client
from app.worker.celery_app import celery_app
from app.worker.transcription import segments_from_whisper_result, transcribe_audio_file


@celery_app.task(name="transcribe_meeting")
def transcribe_meeting(meeting_id: str) -> None:
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, uuid.UUID(meeting_id))
        if meeting is None:
            return

        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_error = None
        db.commit()

        storage = get_storage_client()
        suffix = Path(meeting.original_filename).suffix
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_path = tmp_file.name
                storage.download(meeting.storage_path, tmp_file)

            result = transcribe_audio_file(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        rows = segments_from_whisper_result(result)
        for row in rows:
            db.add(TranscriptSegment(meeting_id=meeting.id, **row))

        meeting.language_detected = result.get("language")
        meeting.status = MeetingStatus.TRANSCRIBED
        db.commit()
    except Exception as exc:
        # Worker boundary: never leave a meeting stuck at "processing" --
        # surface the failure on the row itself so the frontend can show it.
        db.rollback()
        meeting = db.get(Meeting, uuid.UUID(meeting_id))
        if meeting is not None:
            meeting.status = MeetingStatus.FAILED
            # Keep the tail, not the head: tools like ffmpeg dump a verbose
            # build banner before the actual error, which lands at the end.
            meeting.processing_error = str(exc)[-2000:]
            db.commit()
    finally:
        db.close()
