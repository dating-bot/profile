from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast, final, override

import sqlalchemy as sa
import structlog
from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.adapters.postgres_models.models import PhotoORM, PreferenceORM, ProfileORM, UserORM
from profile_service.domain.photo import Photo
from profile_service.domain.preferences import Preferences
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
                ProfileORM.is_active,
                ProfileORM.boost_expires_at,
                ProfileORM.subscription_tier,
                ProfileORM.subscription_expires_at,
                ProfileORM.last_telegram_payment_charge_id,
                ProfileORM.last_provider_payment_charge_id,
                ProfileORM.last_invoice_payload,
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
    async def get_profile_by_id(
        self,
        session: AsyncSession,
        profile_id: int,
    ) -> Profile | None:
        result = await session.execute(
            sa
            .select(ProfileORM, UserORM.telegram_id)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(ProfileORM.id == profile_id)
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
        values: dict[str, object] = {
            "name": request.name,
            "age": request.age,
            "city": request.city,
            "bio": request.bio,
            "updated_at": datetime.now(UTC),
        }
        if request.replace_location:
            values["location"] = _point_wkt(request.latitude, request.longitude)

        result = await session.execute(
            sa
            .update(ProfileORM)
            .where(
                ProfileORM.user_id
                == sa.select(UserORM.id).where(UserORM.telegram_id == request.telegram_id).scalar_subquery()
            )
            .values(**values)
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
                ProfileORM.is_active,
                ProfileORM.boost_expires_at,
                ProfileORM.subscription_tier,
                ProfileORM.subscription_expires_at,
                ProfileORM.last_telegram_payment_charge_id,
                ProfileORM.last_provider_payment_charge_id,
                ProfileORM.last_invoice_payload,
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
                ProfileORM.is_active,
                ProfileORM.boost_expires_at,
                ProfileORM.subscription_tier,
                ProfileORM.subscription_expires_at,
                ProfileORM.last_telegram_payment_charge_id,
                ProfileORM.last_provider_payment_charge_id,
                ProfileORM.last_invoice_payload,
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
                PhotoORM.nsfw_score,
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

    @override
    async def get_photo_owned_by_telegram(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        photo_id: int,
    ) -> Photo | None:
        result = await session.execute(
            sa
            .select(PhotoORM)
            .join(ProfileORM, PhotoORM.profile_id == ProfileORM.id)
            .join(UserORM, ProfileORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id, PhotoORM.id == photo_id)
        )
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    @override
    async def delete_photo_by_id(self, session: AsyncSession, photo_id: int) -> None:
        _ = await session.execute(sa.delete(PhotoORM).where(PhotoORM.id == photo_id))

    @override
    async def upsert_preferences(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.UpsertPreferencesRequest,
    ) -> Preferences:
        profile_result = await session.execute(
            sa
            .select(ProfileORM.id)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(UserORM.telegram_id == request.telegram_id)
        )
        profile_id = profile_result.scalar_one_or_none()
        if profile_id is None:
            msg = f"profile not found for telegram_id={request.telegram_id}"
            raise ValueError(msg)

        result = await session.execute(
            pg_insert(PreferenceORM)
            .values(
                profile_id=profile_id,
                min_age=request.age_min,
                max_age=request.age_max,
                gender=request.gender_pref.value if request.gender_pref else None,
                max_distance_km=request.max_distance_km,
            )
            .on_conflict_do_update(
                index_elements=["profile_id"],
                set_={
                    "min_age": request.age_min,
                    "max_age": request.age_max,
                    "gender": request.gender_pref.value if request.gender_pref else None,
                    "max_distance_km": request.max_distance_km,
                },
            )
            .returning(
                PreferenceORM.id,
                PreferenceORM.profile_id,
                PreferenceORM.min_age,
                PreferenceORM.max_age,
                PreferenceORM.gender,
                PreferenceORM.max_distance_km,
            )
        )
        row = result.mappings().one()
        orm = PreferenceORM(**dict(row))
        log.debug("preferences upserted", profile_id=profile_id, telegram_id=request.telegram_id)
        return orm.to_domain()

    @override
    async def get_preferences_by_telegram_id(
        self,
        session: AsyncSession,
        telegram_id: int,
    ) -> Preferences | None:
        result = await session.execute(
            sa
            .select(PreferenceORM)
            .join(ProfileORM, PreferenceORM.profile_id == ProfileORM.id)
            .join(UserORM, ProfileORM.user_id == UserORM.id)
            .where(UserORM.telegram_id == telegram_id)
        )
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    @override
    async def activate_subscription(
        self,
        session: AsyncSession,
        request: ProfileRepositoryProtocol.ActivateSubscriptionRequest,
    ) -> Profile:
        result = await session.execute(
            sa
            .select(ProfileORM, UserORM.telegram_id)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(UserORM.telegram_id == request.telegram_id)
        )
        row = result.one_or_none()
        if row is None:
            msg = f"profile not found for telegram_id={request.telegram_id}"
            raise ValueError(msg)

        profile_orm = cast("ProfileORM", row[0])
        tg_id = cast("int", row[1])

        # Idempotency: same Telegram charge id should not extend subscription repeatedly.
        if (
            request.telegram_payment_charge_id
            and profile_orm.last_telegram_payment_charge_id == request.telegram_payment_charge_id
        ):
            return profile_orm.to_domain(telegram_id=tg_id)

        now = datetime.now(UTC)
        base = profile_orm.subscription_expires_at or now
        if base < now:
            base = now
        expires_at = base + timedelta(seconds=request.duration_seconds)

        update_values: dict[str, object] = {
            "subscription_tier": request.tier.value,
            "subscription_expires_at": expires_at,
            "updated_at": now,
        }
        if request.telegram_payment_charge_id:
            update_values["last_telegram_payment_charge_id"] = request.telegram_payment_charge_id
        if request.provider_payment_charge_id:
            update_values["last_provider_payment_charge_id"] = request.provider_payment_charge_id
        if request.invoice_payload:
            update_values["last_invoice_payload"] = request.invoice_payload

        await session.execute(sa.update(ProfileORM).where(ProfileORM.id == profile_orm.id).values(**update_values))

        result = await session.execute(
            sa
            .select(ProfileORM, UserORM.telegram_id)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(ProfileORM.id == profile_orm.id)
        )
        updated_row = result.one()
        updated = cast("ProfileORM", updated_row[0]).to_domain(telegram_id=cast("int", updated_row[1]))
        log.info(
            "subscription activated",
            telegram_id=request.telegram_id,
            tier=request.tier.value,
            subscription_expires_at=updated.subscription_expires_at.isoformat()
            if updated.subscription_expires_at
            else None,
        )
        return updated
