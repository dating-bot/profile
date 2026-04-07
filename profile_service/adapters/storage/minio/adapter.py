import asyncio
import io
from dataclasses import dataclass
from datetime import timedelta
from typing import final, override

import structlog
from minio import Minio

from profile_service.protocols.storage.protocol import StorageProtocol

log = structlog.stdlib.get_logger("profile_service.adapters.storage.minio")


@final
@dataclass(slots=True)
class MinIOStorageAdapter(StorageProtocol):
    _client: Minio
    _bucket: str

    @override
    async def put(self, request: StorageProtocol.PutRequest) -> None:
        data_stream = io.BytesIO(request.data)
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            request.key,
            data_stream,
            length=len(request.data),
            content_type=request.content_type,
        )
        log.debug("object uploaded", bucket=self._bucket, key=request.key)

    @override
    async def get_presigned_url(self, key: str, ttl_seconds: int) -> str:
        url = await asyncio.to_thread(
            self._client.presigned_get_object,
            self._bucket,
            key,
            expires=timedelta(seconds=ttl_seconds),
        )
        log.debug("presigned url generated", key=key, ttl_seconds=ttl_seconds)
        return url

    @override
    async def ensure_bucket(self) -> None:
        exists = await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        if not exists:
            await asyncio.to_thread(self._client.make_bucket, self._bucket)
            log.info("bucket created", bucket=self._bucket)
