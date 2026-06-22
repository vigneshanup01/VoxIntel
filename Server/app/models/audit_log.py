import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class AuditAction:
    SIGNUP = "signup"
    LOGIN = "login"
    UPLOAD_MEETING = "upload_meeting"
    DELETE_MEETING = "delete_meeting"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    # SET NULL (not CASCADE/RESTRICT): the audit trail must outlive the user/meeting
    # it references, and a stale FK must never block deleting either.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
