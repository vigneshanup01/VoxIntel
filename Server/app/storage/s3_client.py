from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.storage.base import StorageClient


class S3StorageClient(StorageClient):
    """Thin wrapper around boto3's S3 client, pointed at MinIO in dev.

    Because MinIO speaks the S3 API, this same client works unmodified
    against real AWS S3 in production -- only the endpoint/credentials
    in config change.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            region_name=settings.storage_region,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as e:
            raise RuntimeError(
                f"Bucket '{self._bucket}' does not exist or is not accessible."
            ) from e

    def upload(self, fileobj: BinaryIO, key: str, content_type: str | None = None) -> None:
        extra_args = {"ContentType": content_type} if content_type else {}
        self._client.upload_fileobj(fileobj, self._bucket, key, ExtraArgs=extra_args)

    def download(self, key: str, destination: BinaryIO) -> None:
        self._client.download_fileobj(self._bucket, key, destination)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


@lru_cache
def get_storage_client() -> StorageClient:
    return S3StorageClient()
