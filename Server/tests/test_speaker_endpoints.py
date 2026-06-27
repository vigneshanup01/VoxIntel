import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.speaker_stats import SpeakerStats
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def seed_speaker_stats(db_session: Session, meeting_id: str) -> None:
    db_session.add_all(
        [
            SpeakerStats(
                meeting_id=uuid.UUID(meeting_id),
                speaker_label="SPEAKER_00",
                total_speaking_seconds=70.0,
                speaking_percentage=70.0,
                turn_count=3,
            ),
            SpeakerStats(
                meeting_id=uuid.UUID(meeting_id),
                speaker_label="SPEAKER_01",
                total_speaking_seconds=30.0,
                speaking_percentage=30.0,
                turn_count=2,
            ),
        ]
    )
    db_session.commit()


def test_speakers_endpoint_returns_empty_before_diarization(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/speakers", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["speakers"] == []


def test_speakers_endpoint_returns_stats_sorted_by_speaking_time(
    client: TestClient, db_session: Session
) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/speakers", headers=auth_headers(token))

    assert response.status_code == 200
    speakers = response.json()["speakers"]
    assert [s["speaker_label"] for s in speakers] == ["SPEAKER_00", "SPEAKER_01"]
    assert speakers[0]["speaking_percentage"] == 70.0
    assert speakers[0]["turn_count"] == 3
    assert speakers[0]["display_name"] is None


def test_speakers_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    response = client.get(f"/meetings/{meeting_id}/speakers", headers=auth_headers(bob_token))

    assert response.status_code == 404


def test_rename_speaker_sets_display_name(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    response = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(token),
        json={"display_name": "John"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["speaker_label"] == "SPEAKER_00"
    assert body["display_name"] == "John"

    follow_up = client.get(f"/meetings/{meeting_id}/speakers", headers=auth_headers(token))
    by_label = {s["speaker_label"]: s for s in follow_up.json()["speakers"]}
    assert by_label["SPEAKER_00"]["display_name"] == "John"
    assert by_label["SPEAKER_01"]["display_name"] is None


def test_rename_speaker_with_null_clears_display_name(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(token),
        json={"display_name": "John"},
    )
    response = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(token),
        json={"display_name": None},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] is None


def test_rename_speaker_strips_whitespace_and_treats_blank_as_clear(
    client: TestClient, db_session: Session
) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    padded = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(token),
        json={"display_name": "  Jane  "},
    )
    assert padded.json()["display_name"] == "Jane"

    blanked = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(token),
        json={"display_name": "   "},
    )
    assert blanked.json()["display_name"] is None


def test_rename_unknown_speaker_label_returns_404(client: TestClient, db_session: Session) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    response = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_99",
        headers=auth_headers(token),
        json={"display_name": "Ghost"},
    )

    assert response.status_code == 404


def test_rename_speaker_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]
    seed_speaker_stats(db_session, meeting_id)

    response = client.patch(
        f"/meetings/{meeting_id}/speakers/SPEAKER_00",
        headers=auth_headers(bob_token),
        json={"display_name": "Hijacked"},
    )

    assert response.status_code == 404

    unchanged = client.get(f"/meetings/{meeting_id}/speakers", headers=auth_headers(alice_token))
    by_label = {s["speaker_label"]: s for s in unchanged.json()["speakers"]}
    assert by_label["SPEAKER_00"]["display_name"] is None
