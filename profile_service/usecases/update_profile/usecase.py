from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.profile import Profile
from profile_service.protocols.events.protocol import MessageQueueProtocol
from profile_service.protocols.geocoding.protocol import GeocodingProtocol
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.usecases._profile_events import publish_profile_updated

log = structlog.stdlib.get_logger("profile_service.usecases.UpdateProfileUsecase")


class UpdateProfileError(Exception):
    """Base exception for UpdateProfile usecase."""


class UpdateProfileNotFoundError(UpdateProfileError):
    """Profile not found."""


@final
class UpdateProfileUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
        message_queue: MessageQueueProtocol,
        geocoding: GeocodingProtocol,
    ) -> None:
        self._profile_repository = profile_repository
        self._message_queue = message_queue
        self._geocoding = geocoding

    @dataclass
    class Request:
        """Request to update profile fields."""

        telegram_id: int
        name: str
        age: int
        city: str
        bio: str

    @dataclass
    class Response:
        """Updated profile."""

        profile: Profile

    async def execute(self, request: Request) -> Response:
        """Update profile and publish profile.updated event."""
        async with self._profile_repository.context() as session:
            existing = await self._profile_repository.get_profile_by_telegram_id(
                session=session,
                telegram_id=request.telegram_id,
            )
            if existing is None:
                error_msg = f"Profile not found for telegram_id={request.telegram_id}"
                raise UpdateProfileNotFoundError(error_msg)

            city_changed = (existing.city or "").strip() != request.city.strip()
            geo: tuple[float, float] | None = None
            if city_changed:
                log.info(
                    "attempting city geocoding on update",
                    telegram_id=request.telegram_id,
                    city=request.city,
                    city_changed=city_changed,
                    had_lat=existing.latitude is not None,
                    had_lon=existing.longitude is not None,
                )
                geo = await self._geocoding.geocode_city(request.city)

            profile = await self._profile_repository.update_profile(
                session=session,
                request=ProfileRepositoryProtocol.UpdateProfileRequest(
                    telegram_id=request.telegram_id,
                    name=request.name,
                    age=request.age,
                    city=request.city,
                    bio=request.bio,
                    replace_location=city_changed,
                    latitude=geo[0] if geo is not None else None,
                    longitude=geo[1] if geo is not None else None,
                ),
            )
            if city_changed and geo is not None:
                log.info(
                    "city geocoding applied on update",
                    telegram_id=request.telegram_id,
                    city=request.city,
                    latitude=geo[0],
                    longitude=geo[1],
                )
            elif city_changed:
                log.warning(
                    "city changed but geocoding failed, location cleared",
                    telegram_id=request.telegram_id,
                    city=request.city,
                )

        await publish_profile_updated(
            self._message_queue,
            profile_id=profile.id,
            telegram_id=request.telegram_id,
        )

        log.info("profile updated", telegram_id=request.telegram_id, profile_id=profile.id)
        return self.Response(profile=profile)
