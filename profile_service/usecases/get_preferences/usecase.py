from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.preferences import Preferences
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.GetPreferencesUsecase")


@final
class GetPreferencesUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
    ) -> None:
        self._profile_repository = profile_repository

    @dataclass
    class Request:
        telegram_id: int

    @dataclass
    class Response:
        preferences: Preferences | None

    async def execute(self, request: Request) -> Response:
        async with self._profile_repository.context() as session:
            preferences = await self._profile_repository.get_preferences_by_telegram_id(
                session=session,
                telegram_id=request.telegram_id,
            )
        if preferences is None:
            log.debug("preferences not found", telegram_id=request.telegram_id)
        else:
            log.debug("preferences fetched", telegram_id=request.telegram_id)
        return self.Response(preferences=preferences)
