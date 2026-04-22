from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.profile import Profile
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.GetProfileByIdUsecase")


@final
class GetProfileByIdUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
    ) -> None:
        self._profile_repository = profile_repository

    @dataclass
    class Request:
        profile_id: str

    @dataclass
    class Response:
        profile: Profile | None

    async def execute(self, request: Request) -> Response:
        async with self._profile_repository.context() as session:
            profile = await self._profile_repository.get_profile_by_id(
                session=session,
                profile_id=request.profile_id,
            )
        if profile is None:
            log.debug("profile not found by id", profile_id=request.profile_id)
        else:
            log.debug("profile fetched by id", profile_id=request.profile_id, telegram_id=profile.telegram_id)
        return self.Response(profile=profile)
