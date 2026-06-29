import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.speaker_stats import SpeakerStats
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def test_speaker_analytics_aggregates_named_speakers_across_meetings(
    client: TestClient, db_session: Session
) -> None:
    token = signup_and_get_token(client)
    m1 = upload_meeting(client, token, title="Meeting A").json()["id"]
    m2 = upload_meeting(client, token, title="Meeting B").json()["id"]

    db_session.add_all(
        [
            SpeakerStats(
                meeting_id=uuid.UUID(m1),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=300.0,
                speaking_percentage=60.0,
                turn_count=4,
                display_name="Priya",
            ),
            SpeakerStats(
                meeting_id=uuid.UUID(m2),
                speaker_label="SPEAKER_01",
                total_speaking_seconds=200.0,
                speaking_percentage=40.0,
                turn_count=3,
                display_name="Priya",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/analytics/speakers", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["speakers"]) == 1
    assert body["speakers"][0]["display_name"] == "Priya"
    assert body["speakers"][0]["total_speaking_seconds"] == 500.0
    assert body["speakers"][0]["meeting_count"] == 2


def test_speaker_analytics_excludes_unnamed_speakers_from_aggregation(
    client: TestClient, db_session: Session
) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    db_session.add(
        SpeakerStats(
            meeting_id=uuid.UUID(meeting_id),
            speaker_label="SPEAKER_00",
            total_speaking_seconds=300.0,
            speaking_percentage=100.0,
            turn_count=5,
            display_name=None,
        )
    )
    db_session.commit()

    response = client.get("/analytics/speakers", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["speakers"] == []
    assert body["unnamed_speaker_rows_excluded"] == 1


def test_speaker_analytics_does_not_merge_different_unnamed_speakers(
    client: TestClient, db_session: Session
) -> None:
    """SPEAKER_00 in meeting A and SPEAKER_00 in meeting B aren't
    necessarily the same person -- confirm they're never silently summed
    together just because the label happens to match."""
    token = signup_and_get_token(client)
    m1 = upload_meeting(client, token, title="Meeting A").json()["id"]
    m2 = upload_meeting(client, token, title="Meeting B").json()["id"]

    db_session.add_all(
        [
            SpeakerStats(
                meeting_id=uuid.UUID(m1),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=100.0,
                speaking_percentage=50.0,
                turn_count=2,
                display_name=None,
            ),
            SpeakerStats(
                meeting_id=uuid.UUID(m2),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=200.0,
                speaking_percentage=50.0,
                turn_count=2,
                display_name=None,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/analytics/speakers", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["speakers"] == []
    assert body["unnamed_speaker_rows_excluded"] == 2


def test_speaker_analytics_date_range_filters_meetings(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    old_id = upload_meeting(client, token, title="Old").json()["id"]
    new_id = upload_meeting(client, token, title="New").json()["id"]

    db_session.query(Meeting).filter(Meeting.id == uuid.UUID(old_id)).update(
        {"uploaded_at": datetime.now(timezone.utc) - timedelta(days=60)}
    )
    db_session.add_all(
        [
            SpeakerStats(
                meeting_id=uuid.UUID(old_id),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=999.0,
                speaking_percentage=100.0,
                turn_count=1,
                display_name="Old Speaker",
            ),
            SpeakerStats(
                meeting_id=uuid.UUID(new_id),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=50.0,
                speaking_percentage=100.0,
                turn_count=1,
                display_name="New Speaker",
            ),
        ]
    )
    db_session.commit()

    today = datetime.now(timezone.utc).date()
    response = client.get(
        "/analytics/speakers",
        params={"from": (today - timedelta(days=7)).isoformat(), "to": today.isoformat()},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    names = [s["display_name"] for s in response.json()["speakers"]]
    assert names == ["New Speaker"]


def test_speaker_analytics_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    db_session.add(
        SpeakerStats(
            meeting_id=uuid.UUID(meeting_id),
            speaker_label="SPEAKER_00",
            total_speaking_seconds=100.0,
            speaking_percentage=100.0,
            turn_count=1,
            display_name="Alice Friend",
        )
    )
    db_session.commit()

    response = client.get("/analytics/speakers", headers=auth_headers(bob_token))

    assert response.status_code == 200
    assert response.json()["speakers"] == []
