from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.photo import Photo
from profile_service.domain.profile import Profile
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.GetProfileUsecase")


@final
class GetProfileUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
    ) -> None:
        self._profile_repository = profile_repository

    @dataclass
    class Request:
        """Request to get a profile by telegram_id."""

        telegram_id: int

    @dataclass
    class Response:
        """Profile lookup result."""

        profile: Profile | None
        photos: list[Photo]

    async def execute(self, request: Request) -> Response:
        async with self._profile_repository.context() as session:
            profile = await self._profile_repository.get_profile_by_telegram_id(
                session=session,
                telegram_id=request.telegram_id,
            )
            if profile is None:
                log.debug("profile not found", telegram_id=request.telegram_id)
                return self.Response(profile=None, photos=[])

            photos = await self._profile_repository.get_active_photos_by_profile(
                session=session,
                profile_id=profile.id,
            )

        log.debug("profile fetched", telegram_id=request.telegram_id, profile_id=profile.id)
        return self.Response(profile=profile, photos=photos)
