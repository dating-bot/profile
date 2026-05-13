import json
import uuid
from dataclasses import dataclass
from typing import final

import structlog
import structlog.contextvars
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.photo import Photo
from profile_service.infra import PHOTO_UPLOADED_QUEUE
from profile_service.protocols.events.protocol import MessageQueueProtocol, PushMessage
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.protocols.storage.protocol import StorageProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.UploadPhotoUsecase")


class UploadPhotoError(Exception):
    """Base exception for UploadPhoto usecase."""


class UploadPhotoProfileNotFoundError(UploadPhotoError):
    """Profile not found."""


@final
class UploadPhotoUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
        storage: StorageProtocol,
        message_queue: MessageQueueProtocol,
    ) -> None:
        self._profile_repository = profile_repository
        self._storage = storage
        self._message_queue = message_queue

    @dataclass
    class Request:
        """Request to upload a photo for a profile."""

        telegram_id: int
        data: bytes
        content_type: str

    @dataclass
    class Response:
        """Uploaded photo."""

        photo: Photo

    async def execute(self, request: Request) -> Response:
        """Store photo in MinIO, then save metadata in DB."""
        trace_id = str(structlog.contextvars.get_contextvars().get("trace_id") or uuid.uuid4().hex)
        async with self._profile_repository.context() as session:
            profile = await self._profile_repository.get_profile_by_telegram_id(
                session=session,
                telegram_id=request.telegram_id,
            )
            if profile is None:
                error_msg = f"Profile not found for telegram_id={request.telegram_id}"
                raise UploadPhotoProfileNotFoundError(error_msg)

            minio_key = f"profiles/{profile.id}/{uuid.uuid4().hex}"
            await self._storage.put(
                StorageProtocol.PutRequest(
                    key=minio_key,
                    data=request.data,
                    content_type=request.content_type,
                )
            )

            photo = await self._profile_repository.create_photo(
                session=session,
                request=ProfileRepositoryProtocol.CreatePhotoRequest(
                    profile_id=profile.id,
                    minio_key=minio_key,
                ),
            )

        await self._message_queue.push(
            PHOTO_UPLOADED_QUEUE,
            PushMessage(
                body=json.dumps({
                    "photo_id": photo.id,
                    "profile_id": profile.id,
                    "telegram_id": request.telegram_id,
                    "minio_key": minio_key,
                }).encode(),
                headers={"trace_id": trace_id},
                content_type="application/json",
            ),
        )

        log.info("photo uploaded", telegram_id=request.telegram_id, photo_id=photo.id, minio_key=minio_key)
        return self.Response(photo=photo)
