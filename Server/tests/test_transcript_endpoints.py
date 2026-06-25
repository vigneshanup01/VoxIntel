import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.meetings import service as meetings_service
from app.models.meeting import MeetingStatus
from app.models.transcript_segment import TranscriptSegment
from tests.test_meetings import auth_headers, signup_and_get_token, upload_meeting


def test_status_endpoint_reflects_uploaded_status(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/status", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["processing_error"] is None


def test_status_endpoint_requires_ownership(client: TestClient) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/status", headers=auth_headers(bob_token))

    assert response.status_code == 404


def test_transcript_endpoint_returns_empty_before_transcription(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}/transcript", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["segments"] == []


def test_transcript_endpoint_returns_segments_ordered_by_start_time(
    client: TestClient, db_session: Session
) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    db_session.add_all(
        [
            TranscriptSegment(
                meeting_id=uuid.UUID(meeting_id), start_time=5.0, end_time=8.0, text="Second segment"
            ),
            TranscriptSegment(
                meeting_id=uuid.UUID(meeting_id), start_time=0.0, end_time=4.5, text="First segment"
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/meetings/{meeting_id}/transcript", headers=auth_headers(token))

    assert response.status_code == 200
    segments = response.json()["segments"]
    assert [s["text"] for s in segments] == ["First segment", "Second segment"]
    assert segments[0]["speaker_label"] is None


def test_transcript_endpoint_requires_ownership(client: TestClient, db_session: Session) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]

    db_session.add(
        TranscriptSegment(meeting_id=uuid.UUID(meeting_id), start_time=0.0, end_time=1.0, text="Secret")
    )
    db_session.commit()

    response = client.get(f"/meetings/{meeting_id}/transcript", headers=auth_headers(bob_token))

    assert response.status_code == 404


def test_upload_marks_meeting_failed_if_enqueue_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(meeting_id: uuid.UUID) -> None:
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(meetings_service, "enqueue_transcription", boom)

    token = signup_and_get_token(client)
    response = upload_meeting(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == MeetingStatus.FAILED
    assert "redis unreachable" in body["processing_error"]


def test_meeting_detail_exposes_language_and_error_fields(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}", headers=auth_headers(token))

    body = response.json()
    assert "language_detected" in body
    assert "processing_error" in body
