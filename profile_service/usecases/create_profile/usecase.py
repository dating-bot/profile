from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.profile import Gender, Profile
from profile_service.protocols.events.protocol import MessageQueueProtocol
from profile_service.protocols.geocoding.protocol import GeocodingProtocol
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.usecases._profile_events import publish_profile_updated

log = structlog.stdlib.get_logger("profile_service.usecases.CreateProfileUsecase")


class CreateProfileError(Exception):
    """Base exception for CreateProfile usecase."""


class CreateProfileAlreadyExistsError(CreateProfileError):
    """Profile already exists for this telegram_id."""


@final
class CreateProfileUsecase:
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
        """Request to create a new user profile."""

        telegram_id: int
        name: str
        age: int
        city: str
        bio: str
        gender: Gender
        latitude: float | None = None
        longitude: float | None = None

    @dataclass
    class Response:
        """Created profile."""

        profile: Profile

    async def execute(self, request: Request) -> Response:
        """Create a new profile. Raises CreateProfileAlreadyExistsError if profile exists."""
        latitude = request.latitude
        longitude = request.longitude
        if latitude is None or longitude is None:
            log.info("attempting city geocoding on create", telegram_id=request.telegram_id, city=request.city)
            geo = await self._geocoding.geocode_city(request.city)
            if geo is not None:
                latitude, longitude = geo
                log.info(
                    "city geocoding applied on create",
                    telegram_id=request.telegram_id,
                    city=request.city,
                    latitude=latitude,
                    longitude=longitude,
                )

        async with self._profile_repository.context() as session:
            existing = await self._profile_repository.get_profile_by_telegram_id(
                session=session,
                telegram_id=request.telegram_id,
            )
            if existing is not None:
                log.warning("profile already exists", telegram_id=request.telegram_id)
                error_msg = f"Profile already exists for telegram_id={request.telegram_id}"
                raise CreateProfileAlreadyExistsError(error_msg)

            user_id = await self._profile_repository.get_or_create_user(
                session=session,
                request=ProfileRepositoryProtocol.GetOrCreateUserRequest(
                    telegram_id=request.telegram_id,
                ),
            )

            profile = await self._profile_repository.create_profile(
                session=session,
                request=ProfileRepositoryProtocol.CreateProfileRequest(
                    user_id=user_id,
                    telegram_id=request.telegram_id,
                    name=request.name,
                    age=request.age,
                    city=request.city,
                    bio=request.bio,
                    gender=request.gender,
                    latitude=latitude,
                    longitude=longitude,
                ),
            )

        await publish_profile_updated(
            self._message_queue,
            profile_id=profile.id,
            telegram_id=request.telegram_id,
        )
        log.info("profile created", telegram_id=request.telegram_id, profile_id=profile.id)
        return self.Response(profile=profile)
