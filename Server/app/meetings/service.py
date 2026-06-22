import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.meeting import Meeting
from app.storage.base import StorageClient
from app.storage.validation import SNIFF_BYTES, has_allowed_extension, sniff_media_signature


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required")
    if not has_allowed_extension(file.filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    header = file.file.read(SNIFF_BYTES)
    file.file.seek(0)
    if not sniff_media_signature(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a supported audio/video format",
        )


def _validated_size(file: UploadFile) -> int:
    settings = get_settings()
    file.file.seek(0, 2)  # SEEK_END
    size = file.file.tell()
    file.file.seek(0)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the maximum allowed size",
        )
    return size


def create_meeting(
    db: Session,
    storage: StorageClient,
    *,
    owner_id: uuid.UUID,
    title: str,
    file: UploadFile,
) -> Meeting:
    _validate_upload(file)
    _validated_size(file)

    meeting_id = uuid.uuid4()
    safe_filename = Path(file.filename).name
    storage_path = f"{owner_id}/{meeting_id}/{safe_filename}"

    storage.upload(file.file, storage_path, content_type=file.content_type)

    meeting = Meeting(
        id=meeting_id,
        owner_id=owner_id,
        title=title,
        original_filename=safe_filename,
        storage_path=storage_path,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def list_meetings(db: Session, *, owner_id: uuid.UUID) -> list[Meeting]:
    return (
        db.query(Meeting)
        .filter(Meeting.owner_id == owner_id)
        .order_by(Meeting.uploaded_at.desc())
        .all()
    )


def get_owned_meeting(db: Session, *, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> Meeting:
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
        .first()
    )
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


def delete_meeting(db: Session, storage: StorageClient, *, meeting: Meeting) -> None:
    storage.delete(meeting.storage_path)
    db.delete(meeting)
    db.commit()
