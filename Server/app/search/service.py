import uuid

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.transcript_segment import TranscriptSegment


def search_transcripts(
    db: Session,
    *,
    owner_id: uuid.UUID,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[TranscriptSegment, str]], int]:
    """Search transcript content across all of the owner's meetings.

    Postgres: matches via the `text_search` generated tsvector column (see
    migration 0006), which the GIN index makes fast at any real scale.
    Other dialects (SQLite, used by the test suite): falls back to a plain
    ILIKE substring match -- migration 0006's tsvector column is
    Postgres-only DDL and was never applied there, so this keeps the
    *behavior* (and therefore the tests) portable even though the
    *performance characteristics* aren't.
    """
    base = (
        db.query(TranscriptSegment, Meeting.title)
        .join(Meeting, Meeting.id == TranscriptSegment.meeting_id)
        .filter(Meeting.owner_id == owner_id)
    )

    if db.get_bind().dialect.name == "postgresql":
        base = base.filter(
            sa_text("transcript_segments.text_search @@ websearch_to_tsquery('english', :search_q)")
        ).params(search_q=query)
    else:
        base = base.filter(TranscriptSegment.text.ilike(f"%{query}%"))

    total = base.count()
    rows = base.order_by(TranscriptSegment.start_time).offset(offset).limit(limit).all()
    return rows, total
