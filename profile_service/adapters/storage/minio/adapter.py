from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Protocol, cast, final, override

import aioboto3
import structlog
from botocore.exceptions import ClientError

from profile_service.infra.minio import MinIOConfig, create_s3_client
from profile_service.protocols.storage.protocol import StorageError, StorageProtocol

log = structlog.stdlib.get_logger("profile_service.adapters.MinIOStorageAdapter")

_BUCKET_MISSING_CODES = frozenset(("404", "NoSuchBucket", "NotFound"))
_HTTP_NOT_FOUND = 404


class _S3Client(Protocol):
    async def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> None: ...

    async def delete_object(self, *, Bucket: str, Key: str) -> None: ...

    async def generate_presigned_url(
        self,
        client_method: str,
        *,
        Params: dict[str, str],
        ExpiresIn: int,
    ) -> str: ...

    async def head_bucket(self, *, Bucket: str) -> None: ...

    async def create_bucket(self, *, Bucket: str) -> None: ...


def _is_bucket_missing(error: ClientError) -> bool:
    raw = error.response
    if not isinstance(raw, dict):
        return False
    response = cast("dict[str, object]", raw)
    err_obj = response.get("Error")
    code = ""
    if isinstance(err_obj, dict):
        err_dict = cast("dict[str, object]", err_obj)
        cv = err_dict.get("Code", "")
        code = str(cv) if cv is not None else ""
    meta_obj = response.get("ResponseMetadata")
    status = 0
    if isinstance(meta_obj, dict):
        meta_dict = cast("dict[str, object]", meta_obj)
        sv = meta_dict.get("HTTPStatusCode", 0)
        status = int(sv) if isinstance(sv, (int, float, str)) else 0
    return code in _BUCKET_MISSING_CODES or status == _HTTP_NOT_FOUND


@asynccontextmanager
async def _s3_op(operation: str) -> AsyncGenerator[None]:
    try:
        yield
    except StorageError:
        raise
    except Exception as e:
        msg = f"{operation} failed: {e}"
        raise StorageError(msg) from e


@final
@dataclass(slots=True)
class MinIOStorageAdapter(StorageProtocol):
    aioboto3_session: aioboto3.Session
    minio_config: MinIOConfig

    def _s3_client(self) -> AbstractAsyncContextManager[_S3Client]:
        return cast(
            "AbstractAsyncContextManager[_S3Client]",
            create_s3_client(session=self.aioboto3_session, config=self.minio_config),
        )

    @override
    async def put(self, request: StorageProtocol.PutRequest) -> None:
        async with _s3_op("put_object"), self._s3_client() as client:
            await client.put_object(
                Bucket=self.minio_config.bucket,
                Key=request.key,
                Body=request.data,
                ContentType=request.content_type,
            )
        log.debug("object uploaded", bucket=self.minio_config.bucket, key=request.key)

    @override
    async def delete_object(self, key: str) -> None:
        async with _s3_op("delete_object"), self._s3_client() as client:
            await client.delete_object(Bucket=self.minio_config.bucket, Key=key)
        log.debug("object deleted", bucket=self.minio_config.bucket, key=key)

    @override
    async def get_presigned_url(self, key: str, ttl_seconds: int) -> str:
        url: str
        async with _s3_op("generate_presigned_url"), self._s3_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.minio_config.bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        log.debug("presigned url generated", key=key, ttl_seconds=ttl_seconds)
        return url

    @override
    async def ensure_bucket(self) -> None:
        bucket = self.minio_config.bucket
        async with _s3_op("ensure_bucket"), self._s3_client() as client:
            try:
                await client.head_bucket(Bucket=bucket)
            except ClientError as e:
                if not _is_bucket_missing(e):
                    msg = f"ensure_bucket failed: {e}"
                    raise StorageError(msg) from e
                await client.create_bucket(Bucket=bucket)
                log.info("bucket created", bucket=bucket)
