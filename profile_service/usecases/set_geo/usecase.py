from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.profile import Profile
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.SetGeoUsecase")


class SetGeoError(Exception):
    """Base for SetGeo."""


class SetGeoNotFoundError(SetGeoError):
    """No profile for telegram_id."""


@final
class SetGeoUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
    ) -> None:
        self._profile_repository = profile_repository

    @dataclass
    class Request:
        telegram_id: int
        latitude: float
        longitude: float

    @dataclass
    class Response:
        profile: Profile

    async def execute(self, request: Request) -> Response:
        async with self._profile_repository.context() as session:
            try:
                profile = await self._profile_repository.set_geo(
                    session=session,
                    request=ProfileRepositoryProtocol.SetGeoRequest(
                        telegram_id=request.telegram_id,
                        latitude=request.latitude,
                        longitude=request.longitude,
                    ),
                )
            except ValueError as e:
                raise SetGeoNotFoundError(str(e)) from e

        log.info("geo saved", telegram_id=request.telegram_id, profile_id=profile.id)
        return self.Response(profile=profile)
