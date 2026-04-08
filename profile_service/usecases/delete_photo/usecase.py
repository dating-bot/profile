from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.protocols.storage.protocol import StorageProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.DeletePhotoUsecase")


class DeletePhotoError(Exception):
    """Base exception for DeletePhoto."""


class DeletePhotoNotFoundError(DeletePhotoError):
    """Фото не найдено или не принадлежит пользователю."""


@final
class DeletePhotoUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
        storage: StorageProtocol,
    ) -> None:
        self._profile_repository = profile_repository
        self._storage = storage

    @dataclass
    class Request:
        telegram_id: int
        photo_id: int

    @dataclass
    class Response:
        success: bool

    async def execute(self, request: Request) -> Response:
        async with self._profile_repository.context() as session:
            photo = await self._profile_repository.get_photo_owned_by_telegram(
                session,
                telegram_id=request.telegram_id,
                photo_id=request.photo_id,
            )
            if photo is None:
                raise DeletePhotoNotFoundError(
                    f"photo not found or access denied: photo_id={request.photo_id}",
                )

            _ = await self._storage.delete_object(photo.minio_key)
            _ = await self._profile_repository.delete_photo_by_id(session, photo_id=photo.id)

        log.info("photo deleted", telegram_id=request.telegram_id, photo_id=request.photo_id)
        return self.Response(success=True)
