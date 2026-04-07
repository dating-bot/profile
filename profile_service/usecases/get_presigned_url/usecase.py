from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.protocols.storage.protocol import StorageProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.GetPresignedUrlUsecase")


class GetPresignedUrlError(Exception):
    """Base exception for GetPresignedUrl usecase."""


class GetPresignedUrlNotFoundError(GetPresignedUrlError):
    """Photo not found."""


@final
class GetPresignedUrlUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
        storage: StorageProtocol,
        presigned_ttl_seconds: int = 900,
    ) -> None:
        self._profile_repository = profile_repository
        self._storage = storage
        self._presigned_ttl_seconds = presigned_ttl_seconds

    @dataclass
    class Request:
        """Request to get a presigned URL for a photo."""

        photo_id: int

    @dataclass
    class Response:
        """Presigned URL for photo."""

        url: str

    async def execute(self, request: Request) -> Response:
        """Generate presigned MinIO URL (TTL from config, default 900s)."""
        async with self._profile_repository.context() as session:
            photo = await self._profile_repository.get_photo_by_id(
                session=session,
                photo_id=request.photo_id,
            )

        if photo is None:
            error_msg = f"Photo not found: photo_id={request.photo_id}"
            raise GetPresignedUrlNotFoundError(error_msg)

        url = await self._storage.get_presigned_url(
            key=photo.minio_key,
            ttl_seconds=self._presigned_ttl_seconds,
        )

        log.debug("presigned url generated", photo_id=request.photo_id)
        return self.Response(url=url)
