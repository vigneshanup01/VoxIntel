import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.speaker_stats import SpeakerStats
from app.models.transcript_segment import TranscriptSegment
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def seed_transcript(
    db_session: Session, meeting_id: str, *, text: str, start_time: float = 0.0, speaker_label: str | None = None
) -> None:
    db_session.add(
        TranscriptSegment(
            meeting_id=uuid.UUID(meeting_id),
            start_time=start_time,
            end_time=start_time + 2.0,
            text=text,
            speaker_label=speaker_label,
        )
    )
    db_session.commit()


# --- GET /meetings/search ----------------------------------------------------


def test_search_meetings_by_title(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    sprint_id = upload_meeting(client, token, title="Sprint Planning").json()["id"]
    upload_meeting(client, token, title="Budget Review")

    response = client.get("/meetings/search", params={"q": "sprint"}, headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [m["id"] for m in body["meetings"]] == [sprint_id]


def test_search_meetings_by_transcript_content(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    budget_id = upload_meeting(client, token, title="Meeting A").json()["id"]
    hiring_id = upload_meeting(client, token, title="Meeting B").json()["id"]
    seed_transcript(db_session, budget_id, text="we need to finalize the Q3 budget numbers")
    seed_transcript(db_session, hiring_id, text="let's talk about the new hire onboarding")

    response = client.get("/meetings/search", params={"q": "budget"}, headers=auth_headers(token))

    assert response.status_code == 200
    assert [m["id"] for m in response.json()["meetings"]] == [budget_id]


def test_search_meetings_absent_phrase_returns_empty(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token, title="Meeting A").json()["id"]
    seed_transcript(db_session, meeting_id, text="just a regular discussion")

    response = client.get("/meetings/search", params={"q": "spaceship"}, headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["meetings"] == []
    assert body["total"] == 0


def test_search_meetings_by_speaker_display_name(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    named_id = upload_meeting(client, token, title="Meeting A").json()["id"]
    upload_meeting(client, token, title="Meeting B")
    db_session.add(
        SpeakerStats(
            meeting_id=uuid.UUID(named_id),
            speaker_label="SPEAKER_00",
            total_speaking_seconds=10.0,
            speaking_percentage=100.0,
            turn_count=1,
            display_name="Priya",
        )
    )
    db_session.commit()

    response = client.get("/meetings/search", params={"speaker": "priya"}, headers=auth_headers(token))

    assert response.status_code == 200
    assert [m["id"] for m in response.json()["meetings"]] == [named_id]


def test_search_meetings_by_speaker_label_when_unnamed(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    db_session.add(
        SpeakerStats(
            meeting_id=uuid.UUID(meeting_id),
            speaker_label="SPEAKER_02",
            total_speaking_seconds=10.0,
            speaking_percentage=100.0,
            turn_count=1,
            display_name=None,
        )
    )
    db_session.commit()

    response = client.get("/meetings/search", params={"speaker": "SPEAKER_02"}, headers=auth_headers(token))

    assert response.status_code == 200
    assert len(response.json()["meetings"]) == 1


def test_search_meetings_date_range(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    old_id = upload_meeting(client, token, title="Old").json()["id"]
    new_id = upload_meeting(client, token, title="New").json()["id"]
    db_session.query(Meeting).filter(Meeting.id == uuid.UUID(old_id)).update(
        {"uploaded_at": datetime.now(timezone.utc) - timedelta(days=60)}
    )
    db_session.commit()

    today = datetime.now(timezone.utc).date()
    response = client.get(
        "/meetings/search",
        params={"from": (today - timedelta(days=7)).isoformat(), "to": today.isoformat()},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert [m["id"] for m in response.json()["meetings"]] == [new_id]


def test_search_meetings_pagination(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    for i in range(5):
        upload_meeting(client, token, title=f"Meeting {i}")

    response = client.get("/meetings/search", params={"limit": 2, "offset": 0}, headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["meetings"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_search_meetings_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    upload_meeting(client, alice_token, title="Alice Private")

    response = client.get("/meetings/search", params={"q": "alice"}, headers=auth_headers(bob_token))

    assert response.status_code == 200
    assert response.json()["meetings"] == []


# --- GET /search/transcripts ---------------------------------------------


def test_search_transcripts_returns_matching_segments(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token, title="Standup").json()["id"]
    seed_transcript(
        db_session, meeting_id, text="the deployment broke production again", start_time=42.0, speaker_label="SPEAKER_00"
    )

    response = client.get("/search/transcripts", params={"q": "production"}, headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    result = body["results"][0]
    assert result["meeting_id"] == meeting_id
    assert result["meeting_title"] == "Standup"
    assert result["start_time"] == 42.0
    assert "production" in result["snippet"]


def test_search_transcripts_absent_phrase_returns_empty(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_transcript(db_session, meeting_id, text="nothing interesting here")

    response = client.get("/search/transcripts", params={"q": "spaceship"}, headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_transcripts_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_transcript(db_session, meeting_id, text="alice secret budget plan")

    response = client.get("/search/transcripts", params={"q": "budget"}, headers=auth_headers(bob_token))

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_transcripts_requires_nonempty_query(client: TestClient) -> None:
    token = signup_and_get_token(client)

    response = client.get("/search/transcripts", params={"q": ""}, headers=auth_headers(token))

    assert response.status_code == 422
