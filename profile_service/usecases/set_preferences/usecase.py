from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.preferences import GenderPref, Preferences
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.usecases.SetPreferencesUsecase")


class SetPreferencesError(Exception):
    """Base exception for SetPreferences usecase."""


class SetPreferencesNotFoundError(SetPreferencesError):
    """Profile not found."""


@final
class SetPreferencesUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
    ) -> None:
        self._profile_repository = profile_repository

    @dataclass
    class Request:
        telegram_id: int
        age_min: int | None
        age_max: int | None
        gender_pref: GenderPref | None
        max_distance_km: int | None

    @dataclass
    class Response:
        preferences: Preferences

    async def execute(self, request: Request) -> Response:
        try:
            async with self._profile_repository.context() as session:
                preferences = await self._profile_repository.upsert_preferences(
                    session,
                    ProfileRepositoryProtocol.UpsertPreferencesRequest(
                        telegram_id=request.telegram_id,
                        age_min=request.age_min,
                        age_max=request.age_max,
                        gender_pref=request.gender_pref,
                        max_distance_km=request.max_distance_km,
                    ),
                )
        except ValueError as e:
            raise SetPreferencesNotFoundError(str(e)) from e

        log.info("preferences set", telegram_id=request.telegram_id)
        return self.Response(preferences=preferences)
