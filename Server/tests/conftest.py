from collections.abc import Generator
from typing import BinaryIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import _hits
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.storage.base import StorageClient
from app.storage.s3_client import get_storage_client


class FakeStorageClient(StorageClient):
    """In-memory stand-in for MinIO/S3 so tests don't need real object storage."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, fileobj: BinaryIO, key: str, content_type: str | None = None) -> None:
        self.objects[key] = fileobj.read()

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture()
def fake_storage() -> FakeStorageClient:
    return FakeStorageClient()


@pytest.fixture()
def client(fake_storage: FakeStorageClient) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_client] = lambda: fake_storage

    _hits.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def wav_bytes() -> bytes:
    """A minimal byte sequence with a valid RIFF/WAVE header."""
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + (b"\x00" * 100)
