from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from profile_service.domain.photo import Photo
from profile_service.domain.preferences import GenderPref, Preferences
from profile_service.domain.profile import Gender, Profile


class ProfileRepositoryProtocol[SessionT](Protocol):
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[SessionT]:
        raise NotImplementedError
        yield  # pyright: ignore[reportUnreachable]

    @dataclass
    class GetOrCreateUserRequest:
        telegram_id: int

    async def get_or_create_user(self, session: SessionT, request: GetOrCreateUserRequest) -> int:
        """Returns user.id (creates user row if not exists)."""
        ...

    @dataclass
    class CreateProfileRequest:
        user_id: int
        telegram_id: int
        name: str
        age: int
        city: str
        bio: str
        gender: Gender
        latitude: float | None = None
        longitude: float | None = None

    async def create_profile(self, session: SessionT, request: CreateProfileRequest) -> Profile: ...

    async def get_profile_by_telegram_id(self, session: SessionT, telegram_id: int) -> Profile | None: ...

    async def get_profile_by_id(self, session: SessionT, profile_id: int) -> Profile | None: ...

    @dataclass
    class UpdateProfileRequest:
        telegram_id: int
        name: str
        age: int
        city: str
        bio: str

    async def update_profile(self, session: SessionT, request: UpdateProfileRequest) -> Profile: ...

    @dataclass
    class SetGeoRequest:
        telegram_id: int
        latitude: float
        longitude: float

    async def set_geo(self, session: SessionT, request: SetGeoRequest) -> Profile: ...

    @dataclass
    class CreatePhotoRequest:
        profile_id: int
        minio_key: str

    async def create_photo(self, session: SessionT, request: CreatePhotoRequest) -> Photo: ...

    async def get_photo_by_id(self, session: SessionT, photo_id: int) -> Photo | None: ...

    async def get_active_photos_by_profile(self, session: SessionT, profile_id: int) -> list[Photo]: ...

    async def get_photo_owned_by_telegram(
        self,
        session: SessionT,
        *,
        telegram_id: int,
        photo_id: int,
    ) -> Photo | None:
        """Фото по id, если оно принадлежит профилю с данным telegram_id."""

    async def delete_photo_by_id(self, session: SessionT, photo_id: int) -> None:
        """Удалить строку фото (после проверки владельца)."""

    @dataclass
    class UpsertPreferencesRequest:
        telegram_id: int
        age_min: int | None
        age_max: int | None
        gender_pref: GenderPref | None
        max_distance_km: int | None

    async def upsert_preferences(self, session: SessionT, request: UpsertPreferencesRequest) -> Preferences: ...

    async def get_preferences_by_telegram_id(self, session: SessionT, telegram_id: int) -> Preferences | None: ...
