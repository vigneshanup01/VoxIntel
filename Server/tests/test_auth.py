from fastapi.testclient import TestClient


def signup(client: TestClient, email: str = "alice@example.com", password: str = "correct-horse-9") -> dict:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": password, "full_name": "Alice"},
    )
    return response


def test_signup_creates_user_and_returns_token(client: TestClient) -> None:
    response = signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["full_name"] == "Alice"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert body["token"]["access_token"]
    assert body["token"]["token_type"] == "bearer"


def test_signup_rejects_duplicate_email(client: TestClient) -> None:
    signup(client)
    response = signup(client)

    assert response.status_code == 409


def test_signup_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/auth/signup",
        json={"email": "bob@example.com", "password": "alllowercaseletters", "full_name": "Bob"},
    )

    assert response.status_code == 422


def test_login_with_correct_credentials_returns_token(client: TestClient) -> None:
    signup(client)

    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "correct-horse-9"})

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    signup(client)

    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrong-password-1"})

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever-123"})

    assert response.status_code == 401


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client: TestClient) -> None:
    token = signup(client).json()["token"]["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_rejects_garbage_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    from app.core.config import get_settings

    max_attempts = get_settings().auth_rate_limit_max_attempts

    for _ in range(max_attempts):
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})

    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})

    assert response.status_code == 429
