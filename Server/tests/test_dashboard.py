import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.speaker_stats import SpeakerStats
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def _set_meeting_fields(db_session: Session, meeting_id: str, **fields) -> None:
    db_session.query(Meeting).filter(Meeting.id == uuid.UUID(meeting_id)).update(fields)
    db_session.commit()


def test_dashboard_summary_empty_for_new_user(client: TestClient) -> None:
    token = signup_and_get_token(client)

    response = client.get("/dashboard/summary", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_meetings"] == 0
    assert body["total_hours"] == 0
    assert body["meetings_this_week"] == 0
    assert body["most_active_speaker"] is None
    assert body["recent_meetings"] == []


def test_dashboard_summary_computes_totals(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    old_id = upload_meeting(client, token, title="Old Meeting").json()["id"]
    new_id = upload_meeting(client, token, title="Recent Meeting").json()["id"]

    _set_meeting_fields(
        db_session, old_id, duration_seconds=3600.0, uploaded_at=datetime.now(timezone.utc) - timedelta(days=30)
    )
    _set_meeting_fields(
        db_session, new_id, duration_seconds=1800.0, uploaded_at=datetime.now(timezone.utc) - timedelta(days=1)
    )

    response = client.get("/dashboard/summary", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_meetings"] == 2
    assert body["total_hours"] == 1.5
    assert body["meetings_this_week"] == 1
    assert [m["id"] for m in body["recent_meetings"]] == [new_id, old_id]


def test_dashboard_summary_most_active_speaker_ignores_unnamed(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    db_session.add_all(
        [
            SpeakerStats(
                meeting_id=uuid.UUID(meeting_id),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=500.0,
                speaking_percentage=80.0,
                turn_count=5,
                display_name=None,
            ),
            SpeakerStats(
                meeting_id=uuid.UUID(meeting_id),
                speaker_label="SPEAKER_01",
                total_speaking_seconds=100.0,
                speaking_percentage=20.0,
                turn_count=2,
                display_name="Alice",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/dashboard/summary", headers=auth_headers(token))

    assert response.status_code == 200
    # Not SPEAKER_00, despite more talk time -- it has no display_name set.
    assert response.json()["most_active_speaker"] == "Alice"


def test_dashboard_summary_only_includes_current_users_data(client: TestClient) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    upload_meeting(client, alice_token, title="Alice's Meeting")

    response = client.get("/dashboard/summary", headers=auth_headers(bob_token))

    assert response.status_code == 200
    assert response.json()["total_meetings"] == 0
