import pytest
from fastapi.testclient import TestClient

from tests.conftest import wav_bytes


def signup_and_get_token(client: TestClient, email: str = "alice@example.com") -> str:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "correct-horse-9", "full_name": "Alice"},
    )
    return response.json()["token"]["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def upload_meeting(client: TestClient, token: str, title: str = "Team Sync") -> dict:
    return client.post(
        "/meetings",
        headers=auth_headers(token),
        data={"title": title},
        files={"file": ("meeting.wav", wav_bytes(), "audio/wav")},
    )


def test_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/meetings",
        data={"title": "Team Sync"},
        files={"file": ("meeting.wav", wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 401


def test_upload_creates_meeting_with_uploaded_status(client: TestClient, fake_storage) -> None:
    token = signup_and_get_token(client)

    response = upload_meeting(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Team Sync"
    assert body["original_filename"] == "meeting.wav"
    assert body["status"] == "uploaded"
    assert body["duration_seconds"] is None
    assert len(fake_storage.objects) == 1


def test_upload_rejects_disallowed_extension(client: TestClient) -> None:
    token = signup_and_get_token(client)

    response = client.post(
        "/meetings",
        headers=auth_headers(token),
        data={"title": "Not Audio"},
        files={"file": ("notes.txt", b"just plain text", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_rejects_content_that_does_not_match_extension(client: TestClient) -> None:
    token = signup_and_get_token(client)

    response = client.post(
        "/meetings",
        headers=auth_headers(token),
        data={"title": "Fake Audio"},
        files={"file": ("fake.wav", b"not actually a wav file" + b"\x00" * 20, "audio/wav")},
    )

    assert response.status_code == 400


def test_upload_rejects_oversized_file(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)

    token = signup_and_get_token(client)
    response = upload_meeting(client, token)

    assert response.status_code == 413


def test_list_returns_only_current_users_meetings(client: TestClient) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")

    upload_meeting(client, alice_token, title="Alice's Standup")
    upload_meeting(client, bob_token, title="Bob's Retro")

    response = client.get("/meetings", headers=auth_headers(alice_token))

    assert response.status_code == 200
    meetings = response.json()["meetings"]
    assert len(meetings) == 1
    assert meetings[0]["title"] == "Alice's Standup"


def test_get_meeting_by_owner_succeeds(client: TestClient) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == meeting_id


def test_get_meeting_owned_by_another_user_returns_404(client: TestClient) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]

    response = client.get(f"/meetings/{meeting_id}", headers=auth_headers(bob_token))

    assert response.status_code == 404


def test_delete_removes_meeting_and_file(client: TestClient, fake_storage) -> None:
    token = signup_and_get_token(client)
    meeting_id = upload_meeting(client, token).json()["id"]

    response = client.delete(f"/meetings/{meeting_id}", headers=auth_headers(token))

    assert response.status_code == 204
    assert fake_storage.objects == {}
    assert client.get(f"/meetings/{meeting_id}", headers=auth_headers(token)).status_code == 404


def test_delete_owned_by_another_user_returns_404_and_does_not_delete(client: TestClient) -> None:
    alice_token = signup_and_get_token(client, email="alice@example.com")
    bob_token = signup_and_get_token(client, email="bob@example.com")
    meeting_id = upload_meeting(client, alice_token).json()["id"]

    response = client.delete(f"/meetings/{meeting_id}", headers=auth_headers(bob_token))

    assert response.status_code == 404
    assert client.get(f"/meetings/{meeting_id}", headers=auth_headers(alice_token)).status_code == 200
