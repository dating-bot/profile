from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast, final, override

import sqlalchemy as sa
import structlog
from geoalchemy2.elements import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.adapters.postgres_models.models import PhotoORM, ProfileORM, UserORM
from profile_service.domain.photo import Photo
from profile_service.domain.profile import Profile
from profile_service.infra.postgres import AsyncSessionFactory
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol

log = structlog.stdlib.get_logger("profile_service.adapters.profile.postgres")


def _point_wkt(lat: float | None, lon: float | None) -> WKTElement | None:
    if lat is None or lon is None:
        return None
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


@final
@dataclass(slots=True)
class PostgresProfileRepositoryAdapter(ProfileRepositoryProtocol[AsyncSession]):
    _session_factory: AsyncSessionFactory

    @override
    @asynccontextmanager
    async def context(self) -> AsyncGenerator[AsyncSession]:
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @override
    async def get_or_create_user(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.GetOrCreateUserRequest,
    ) -> int:
        result = await session.execute(sa.select(UserORM.id).where(UserORM.telegram_id == request.telegram_id))
        user_id = result.scalar_one_or_none()
        if user_id is not None:
            return user_id

        result = await session.execute(sa.insert(UserORM).values(telegram_id=request.telegram_id).returning(UserORM.id))
        user_id = result.scalar_one()
        log.debug("user created", telegram_id=request.telegram_id, user_id=user_id)
        return user_id

    @override
    async def create_profile(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.CreateProfileRequest,
    ) -> Profile:
        result = await session.execute(
            sa
            .insert(ProfileORM)
            .values(
                user_id=request.user_id,
                name=request.name,
                bio=request.bio,
                age=request.age,
                gender=request.gender.value,
                city=request.city,
                location=_point_wkt(request.latitude, request.longitude),
            )
            .returning(
                ProfileORM.id,
                ProfileORM.user_id,
                ProfileORM.name,
                ProfileORM.bio,
                ProfileORM.age,
                ProfileORM.gender,
                ProfileORM.city,
                ProfileORM.location,
                ProfileORM.ai_quality_score,
                ProfileORM.created_at,
                ProfileORM.updated_at,
            )
        )
        row = result.mappings().one()
        orm = ProfileORM(**dict(row))
        profile = orm.to_domain(telegram_id=request.telegram_id)
        log.debug("profile created", profile_id=profile.id, user_id=request.user_id)
        return profile

    @override
    async def get_profile_by_telegram_id(
        self,
        session: AsyncSession,
        telegram_id: int,
    ) -> Profile | None:
        result = await session.execute(
            sa
            .select(ProfileORM, UserORM.telegram_id)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(UserORM.telegram_id == telegram_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        profile_orm = cast("ProfileORM", row[0])
        tg_id = cast("int", row[1])
        return profile_orm.to_domain(telegram_id=tg_id)

    @override
    async def update_profile(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.UpdateProfileRequest,
    ) -> Profile:
        result = await session.execute(
            sa
            .update(ProfileORM)
            .where(
                ProfileORM.user_id
                == sa.select(UserORM.id).where(UserORM.telegram_id == request.telegram_id).scalar_subquery()
            )
            .values(
                name=request.name,
                age=request.age,
                city=request.city,
                bio=request.bio,
                updated_at=datetime.now(UTC),
            )
            .returning(
                ProfileORM.id,
                ProfileORM.user_id,
                ProfileORM.name,
                ProfileORM.bio,
                ProfileORM.age,
                ProfileORM.gender,
                ProfileORM.city,
                ProfileORM.location,
                ProfileORM.ai_quality_score,
                ProfileORM.created_at,
                ProfileORM.updated_at,
            )
        )
        row = result.mappings().one()
        orm = ProfileORM(**dict(row))
        profile = orm.to_domain(telegram_id=request.telegram_id)
        log.debug("profile updated", profile_id=profile.id, telegram_id=request.telegram_id)
        return profile

    @override
    async def set_geo(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.SetGeoRequest,
    ) -> Profile:
        result = await session.execute(
            sa
            .update(ProfileORM)
            .where(
                ProfileORM.user_id
                == sa.select(UserORM.id).where(UserORM.telegram_id == request.telegram_id).scalar_subquery()
            )
            .values(
                location=_point_wkt(request.latitude, request.longitude),
                updated_at=datetime.now(UTC),
            )
            .returning(
                ProfileORM.id,
                ProfileORM.user_id,
                ProfileORM.name,
                ProfileORM.bio,
                ProfileORM.age,
                ProfileORM.gender,
                ProfileORM.city,
                ProfileORM.location,
                ProfileORM.ai_quality_score,
                ProfileORM.created_at,
                ProfileORM.updated_at,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            msg = f"profile not found for telegram_id={request.telegram_id}"
            raise ValueError(msg)
        orm = ProfileORM(**dict(row))
        profile = orm.to_domain(telegram_id=request.telegram_id)
        log.debug("profile geo updated", profile_id=profile.id, telegram_id=request.telegram_id)
        return profile

    @override
    async def create_photo(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.CreatePhotoRequest,
    ) -> Photo:
        result = await session.execute(
            sa
            .insert(PhotoORM)
            .values(
                profile_id=request.profile_id,
                minio_key=request.minio_key,
            )
            .returning(
                PhotoORM.id,
                PhotoORM.profile_id,
                PhotoORM.minio_key,
                PhotoORM.is_active,
                PhotoORM.is_nsfw,
                PhotoORM.created_at,
            )
        )
        row = result.mappings().one()
        photo = Photo.model_validate(row)
        log.debug("photo created", photo_id=photo.id, profile_id=request.profile_id)
        return photo

    @override
    async def get_photo_by_id(
        self,
        session: AsyncSession,
        photo_id: int,
    ) -> Photo | None:
        result = await session.execute(sa.select(PhotoORM).where(PhotoORM.id == photo_id))
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    @override
    async def get_active_photos_by_profile(
        self,
        session: AsyncSession,
        profile_id: int,
    ) -> list[Photo]:
        result = await session.execute(
            sa
            .select(PhotoORM)
            .where(PhotoORM.profile_id == profile_id, PhotoORM.is_active.is_(True))
            .order_by(PhotoORM.created_at)
        )
        return [row.to_domain() for row in result.scalars().all()]
