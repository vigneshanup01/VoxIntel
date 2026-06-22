from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    password = "correct-horse-battery-9"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_password_hash_is_salted() -> None:
    password = "correct-horse-battery-9"
    assert hash_password(password) != hash_password(password)


def test_jwt_encode_decode_roundtrip() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user-123"


def test_jwt_decode_rejects_tampered_token() -> None:
    token = create_access_token(subject="user-123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    assert decode_access_token(tampered) is None


def test_jwt_decode_rejects_garbage() -> None:
    assert decode_access_token("not-a-real-token") is None
