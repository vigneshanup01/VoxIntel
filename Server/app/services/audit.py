import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    meeting_id: uuid.UUID | None = None,
) -> None:
    entry = AuditLog(user_id=user_id, action=action, meeting_id=meeting_id)
    db.add(entry)
    db.commit()
