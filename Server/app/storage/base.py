from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageClient(ABC):
    @abstractmethod
    def upload(self, fileobj: BinaryIO, key: str, content_type: str | None = None) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...
