from dataclasses import dataclass
from typing import Protocol


class StorageError(Exception):
    """Raised when object storage operation fails."""


class StorageProtocol(Protocol):
    @dataclass
    class PutRequest:
        key: str
        data: bytes
        content_type: str

    async def put(self, request: PutRequest) -> None: ...

    async def delete_object(self, key: str) -> None: ...

    async def get_presigned_url(self, key: str, ttl_seconds: int) -> str: ...

    async def ensure_bucket(self) -> None: ...
