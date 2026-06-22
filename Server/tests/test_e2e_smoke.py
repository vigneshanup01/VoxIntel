"""One end-to-end smoke test covering the full Phase 1 happy path:
signup -> login -> upload -> list -> detail -> delete.
"""

from fastapi.testclient import TestClient

from tests.conftest import wav_bytes


def test_full_meeting_lifecycle(client: TestClient, fake_storage) -> None:
    signup_response = client.post(
        "/auth/signup",
        json={"email": "carol@example.com", "password": "correct-horse-9", "full_name": "Carol"},
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/auth/login", json={"email": "carol@example.com", "password": "correct-horse-9"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "carol@example.com"

    upload_response = client.post(
        "/meetings",
        headers=headers,
        data={"title": "Quarterly Planning"},
        files={"file": ("planning.wav", wav_bytes(), "audio/wav")},
    )
    assert upload_response.status_code == 201
    meeting = upload_response.json()
    assert meeting["status"] == "uploaded"
    meeting_id = meeting["id"]
    assert len(fake_storage.objects) == 1

    list_response = client.get("/meetings", headers=headers)
    assert list_response.status_code == 200
    titles = [m["title"] for m in list_response.json()["meetings"]]
    assert titles == ["Quarterly Planning"]

    detail_response = client.get(f"/meetings/{meeting_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["original_filename"] == "planning.wav"

    delete_response = client.delete(f"/meetings/{meeting_id}", headers=headers)
    assert delete_response.status_code == 204
    assert fake_storage.objects == {}

    final_list_response = client.get("/meetings", headers=headers)
    assert final_list_response.json()["meetings"] == []
