import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.meetings import service
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.meeting import MeetingListResponse, MeetingOut
from app.services.audit import log_action
from app.storage.base import StorageClient
from app.storage.s3_client import get_storage_client

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def upload_meeting(
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> MeetingOut:
    meeting = service.create_meeting(db, storage, owner_id=current_user.id, title=title, file=file)
    log_action(db, user_id=current_user.id, action=AuditAction.UPLOAD_MEETING, meeting_id=meeting.id)
    return MeetingOut.model_validate(meeting)


@router.get("", response_model=MeetingListResponse)
def list_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingListResponse:
    meetings = service.list_meetings(db, owner_id=current_user.id)
    return MeetingListResponse(meetings=[MeetingOut.model_validate(m) for m in meetings])


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingOut:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    return MeetingOut.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> None:
    meeting = service.get_owned_meeting(db, meeting_id=meeting_id, owner_id=current_user.id)
    # Log before deleting: the FK must point at a row that still exists at
    # insert time. The meeting's own ON DELETE SET NULL then clears this
    # log entry's meeting_id (and any earlier ones) once it's gone.
    log_action(db, user_id=current_user.id, action=AuditAction.DELETE_MEETING, meeting_id=meeting_id)
    service.delete_meeting(db, storage, meeting=meeting)
