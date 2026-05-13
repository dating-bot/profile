from dataclasses import dataclass
from typing import final, override

import structlog
from grpclib import Status
from grpclib.exceptions import GRPCError

from profile_api.v1 import profile_pb2
from profile_api.v1.profile_grpc import ProfileServiceBase
from profile_service.app.server.utils import unary
from profile_service.domain.preferences import GenderPref
from profile_service.domain.profile import Gender, SubscriptionTier
from profile_service.usecases.activate_subscription.usecase import (
    ActivateSubscriptionNotFoundError,
    ActivateSubscriptionUsecase,
)
from profile_service.usecases.create_profile.usecase import CreateProfileAlreadyExistsError, CreateProfileUsecase
from profile_service.usecases.delete_photo.usecase import DeletePhotoNotFoundError, DeletePhotoUsecase
from profile_service.usecases.get_preferences.usecase import GetPreferencesUsecase
from profile_service.usecases.get_presigned_url.usecase import GetPresignedUrlNotFoundError, GetPresignedUrlUsecase
from profile_service.usecases.get_profile.usecase import GetProfileUsecase
from profile_service.usecases.get_profile_by_id.usecase import GetProfileByIdUsecase
from profile_service.usecases.set_geo.usecase import SetGeoNotFoundError, SetGeoUsecase
from profile_service.usecases.set_preferences.usecase import SetPreferencesNotFoundError, SetPreferencesUsecase
from profile_service.usecases.update_profile.usecase import UpdateProfileNotFoundError, UpdateProfileUsecase
from profile_service.usecases.upload_photo.usecase import UploadPhotoProfileNotFoundError, UploadPhotoUsecase

log = structlog.stdlib.get_logger("profile_service.grpc")


_GENDER_TO_PROTO: dict[Gender | None, profile_pb2.Gender.ValueType] = {
    None: profile_pb2.GENDER_UNSPECIFIED,
    Gender.MALE: profile_pb2.GENDER_MALE,
    Gender.FEMALE: profile_pb2.GENDER_FEMALE,
}

_GENDER_FROM_PROTO: dict[int, Gender] = {
    profile_pb2.GENDER_MALE: Gender.MALE,
    profile_pb2.GENDER_FEMALE: Gender.FEMALE,
}

_SUBSCRIPTION_TIER_TO_PROTO: dict[SubscriptionTier, profile_pb2.SubscriptionTier.ValueType] = {
    SubscriptionTier.FREE: profile_pb2.SUBSCRIPTION_TIER_FREE,
    SubscriptionTier.PREMIUM: profile_pb2.SUBSCRIPTION_TIER_PREMIUM,
}

_SUBSCRIPTION_TIER_FROM_PROTO: dict[int, SubscriptionTier] = {
    profile_pb2.SUBSCRIPTION_TIER_FREE: SubscriptionTier.FREE,
    profile_pb2.SUBSCRIPTION_TIER_PREMIUM: SubscriptionTier.PREMIUM,
}


@final
@dataclass(slots=True)
class ProfileServiceHandler(ProfileServiceBase):
    _create_profile_usecase: CreateProfileUsecase
    _get_profile_usecase: GetProfileUsecase
    _get_profile_by_id_usecase: GetProfileByIdUsecase
    _update_profile_usecase: UpdateProfileUsecase
    _set_geo_usecase: SetGeoUsecase
    _upload_photo_usecase: UploadPhotoUsecase
    _delete_photo_usecase: DeletePhotoUsecase
    _get_presigned_url_usecase: GetPresignedUrlUsecase
    _set_preferences_usecase: SetPreferencesUsecase
    _get_preferences_usecase: GetPreferencesUsecase
    _activate_subscription_usecase: ActivateSubscriptionUsecase

    @override
    @unary
    async def Health(self, request: profile_pb2.HealthRequest) -> profile_pb2.HealthResponse:
        return profile_pb2.HealthResponse(ok=True)

    @override
    @unary
    async def CreateProfile(self, request: profile_pb2.CreateProfileRequest) -> profile_pb2.CreateProfileResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")
        if not request.name:
            raise GRPCError(Status.INVALID_ARGUMENT, "name is required")

        gender = _GENDER_FROM_PROTO.get(request.gender)
        if gender is None:
            raise GRPCError(Status.INVALID_ARGUMENT, "gender is required")

        lat = request.latitude if request.HasField("latitude") else None
        lon = request.longitude if request.HasField("longitude") else None

        try:
            response = await self._create_profile_usecase.execute(
                CreateProfileUsecase.Request(
                    telegram_id=request.telegram_id,
                    name=request.name,
                    age=request.age,
                    city=request.city,
                    bio=request.bio,
                    gender=gender,
                    latitude=lat,
                    longitude=lon,
                )
            )
        except CreateProfileAlreadyExistsError as e:
            raise GRPCError(Status.ALREADY_EXISTS, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in CreateProfile", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.CreateProfileResponse(profile_id=response.profile.id)

    @override
    @unary
    async def GetProfile(self, request: profile_pb2.GetProfileRequest) -> profile_pb2.GetProfileResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")

        try:
            response = await self._get_profile_usecase.execute(
                GetProfileUsecase.Request(telegram_id=request.telegram_id)
            )
        except Exception as e:
            log.exception("unexpected error in GetProfile", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        if response.profile is None:
            return profile_pb2.GetProfileResponse(found=False)

        photos = [profile_pb2.PhotoInfo(photo_id=p.id, is_active=p.is_active) for p in response.photos]

        proto = profile_pb2.GetProfileResponse(
            found=True,
            profile_id=response.profile.id,
            name=response.profile.name or "",
            age=response.profile.age or 0,
            city=response.profile.city or "",
            bio=response.profile.bio or "",
            gender=_GENDER_TO_PROTO[response.profile.gender],
            photos=photos,
        )
        if response.profile.latitude is not None:
            proto.latitude = response.profile.latitude
        if response.profile.longitude is not None:
            proto.longitude = response.profile.longitude
        proto.subscription_tier = _SUBSCRIPTION_TIER_TO_PROTO.get(
            response.profile.subscription_tier, profile_pb2.SUBSCRIPTION_TIER_FREE
        )
        if response.profile.subscription_expires_at is not None:
            proto.subscription_expires_at_seconds = int(response.profile.subscription_expires_at.timestamp())
        return proto

    @override
    @unary
    async def GetProfileById(self, request: profile_pb2.GetProfileByIdRequest) -> profile_pb2.GetProfileByIdResponse:
        if not request.profile_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "profile_id is required")

        try:
            response = await self._get_profile_by_id_usecase.execute(
                GetProfileByIdUsecase.Request(profile_id=request.profile_id)
            )
        except Exception as e:
            log.exception("unexpected error in GetProfileById", profile_id=request.profile_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        if response.profile is None:
            return profile_pb2.GetProfileByIdResponse(found=False)

        p = response.profile
        proto = profile_pb2.GetProfileByIdResponse(
            found=True,
            profile_id=p.id,
            telegram_id=p.telegram_id,
            name=p.name or "",
            age=p.age or 0,
            city=p.city or "",
            bio=p.bio or "",
            gender=_GENDER_TO_PROTO[p.gender],
            is_active=p.is_active,
        )
        if p.latitude is not None:
            proto.latitude = p.latitude
        if p.longitude is not None:
            proto.longitude = p.longitude
        if p.boost_expires_at is not None:
            proto.boost_expires_at_seconds = int(p.boost_expires_at.timestamp())
        proto.subscription_tier = _SUBSCRIPTION_TIER_TO_PROTO.get(
            p.subscription_tier, profile_pb2.SUBSCRIPTION_TIER_FREE
        )
        if p.subscription_expires_at is not None:
            proto.subscription_expires_at_seconds = int(p.subscription_expires_at.timestamp())
        return proto

    @override
    @unary
    async def UpdateProfile(self, request: profile_pb2.UpdateProfileRequest) -> profile_pb2.UpdateProfileResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")

        try:
            _ = await self._update_profile_usecase.execute(
                UpdateProfileUsecase.Request(
                    telegram_id=request.telegram_id,
                    name=request.name,
                    age=request.age,
                    city=request.city,
                    bio=request.bio,
                )
            )
        except UpdateProfileNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in UpdateProfile", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.UpdateProfileResponse(success=True)

    @override
    @unary
    async def SetGeo(self, request: profile_pb2.SetGeoRequest) -> profile_pb2.SetGeoResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")

        try:
            _ = await self._set_geo_usecase.execute(
                SetGeoUsecase.Request(
                    telegram_id=request.telegram_id,
                    latitude=request.latitude,
                    longitude=request.longitude,
                )
            )
        except SetGeoNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in SetGeo", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.SetGeoResponse(success=True)

    @override
    @unary
    async def UploadPhoto(self, request: profile_pb2.UploadPhotoRequest) -> profile_pb2.UploadPhotoResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")
        if not request.data:
            raise GRPCError(Status.INVALID_ARGUMENT, "data is required")

        try:
            response = await self._upload_photo_usecase.execute(
                UploadPhotoUsecase.Request(
                    telegram_id=request.telegram_id,
                    data=request.data,
                    content_type=request.content_type or "image/jpeg",
                )
            )
        except UploadPhotoProfileNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in UploadPhoto", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.UploadPhotoResponse(
            photo_id=response.photo.id,
            minio_key=response.photo.minio_key,
        )

    @override
    @unary
    async def DeletePhoto(self, request: profile_pb2.DeletePhotoRequest) -> profile_pb2.DeletePhotoResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")
        if not request.photo_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "photo_id is required")

        try:
            _ = await self._delete_photo_usecase.execute(
                DeletePhotoUsecase.Request(
                    telegram_id=request.telegram_id,
                    photo_id=request.photo_id,
                )
            )
        except DeletePhotoNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in DeletePhoto", telegram_id=request.telegram_id, photo_id=request.photo_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.DeletePhotoResponse(success=True)

    @override
    @unary
    async def GetPresignedUrl(self, request: profile_pb2.GetPresignedUrlRequest) -> profile_pb2.GetPresignedUrlResponse:
        if not request.photo_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "photo_id is required")

        try:
            response = await self._get_presigned_url_usecase.execute(
                GetPresignedUrlUsecase.Request(photo_id=request.photo_id)
            )
        except GetPresignedUrlNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in GetPresignedUrl", photo_id=request.photo_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.GetPresignedUrlResponse(url=response.url)

    @override
    @unary
    async def SetPreferences(self, request: profile_pb2.SetPreferencesRequest) -> profile_pb2.SetPreferencesResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")

        proto_gender_to_pref = {
            profile_pb2.GENDER_PREF_MALE: GenderPref.MALE,
            profile_pb2.GENDER_PREF_FEMALE: GenderPref.FEMALE,
            profile_pb2.GENDER_PREF_ANY: GenderPref.ANY,
        }
        gender_pref = proto_gender_to_pref.get(request.gender_pref)

        try:
            _ = await self._set_preferences_usecase.execute(
                SetPreferencesUsecase.Request(
                    telegram_id=request.telegram_id,
                    age_min=request.age_min or None,
                    age_max=request.age_max or None,
                    gender_pref=gender_pref,
                    max_distance_km=request.max_distance_km or None,
                )
            )
        except SetPreferencesNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in SetPreferences", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        return profile_pb2.SetPreferencesResponse(success=True)

    @override
    @unary
    async def GetPreferences(self, request: profile_pb2.GetPreferencesRequest) -> profile_pb2.GetPreferencesResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")

        try:
            response = await self._get_preferences_usecase.execute(
                GetPreferencesUsecase.Request(telegram_id=request.telegram_id)
            )
        except Exception as e:
            log.exception("unexpected error in GetPreferences", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        if response.preferences is None:
            return profile_pb2.GetPreferencesResponse(found=False)

        p = response.preferences
        gender_pref_map = {
            "male": profile_pb2.GENDER_PREF_MALE,
            "female": profile_pb2.GENDER_PREF_FEMALE,
            "any": profile_pb2.GENDER_PREF_ANY,
        }
        proto = profile_pb2.GetPreferencesResponse(
            found=True,
            age_min=p.age_min or 0,
            age_max=p.age_max or 0,
            gender_pref=gender_pref_map.get(p.gender_pref.value, profile_pb2.GENDER_PREF_ANY),
            max_distance_km=p.max_distance_km or 0,
        )
        return proto

    @override
    @unary
    async def ActivateSubscription(
        self, request: profile_pb2.ActivateSubscriptionRequest
    ) -> profile_pb2.ActivateSubscriptionResponse:
        if not request.telegram_id:
            raise GRPCError(Status.INVALID_ARGUMENT, "telegram_id is required")
        if request.duration_seconds <= 0:
            raise GRPCError(Status.INVALID_ARGUMENT, "duration_seconds must be > 0")

        tier = _SUBSCRIPTION_TIER_FROM_PROTO.get(request.tier)
        if tier is None:
            raise GRPCError(Status.INVALID_ARGUMENT, "tier is required")

        try:
            response = await self._activate_subscription_usecase.execute(
                ActivateSubscriptionUsecase.Request(
                    telegram_id=request.telegram_id,
                    tier=tier,
                    duration_seconds=request.duration_seconds,
                    telegram_payment_charge_id=request.telegram_payment_charge_id or None,
                    provider_payment_charge_id=request.provider_payment_charge_id or None,
                    invoice_payload=request.invoice_payload or None,
                )
            )
        except ActivateSubscriptionNotFoundError as e:
            raise GRPCError(Status.NOT_FOUND, str(e)) from e
        except Exception as e:
            log.exception("unexpected error in ActivateSubscription", telegram_id=request.telegram_id)
            raise GRPCError(Status.INTERNAL, "internal error") from e

        expires_at_seconds = (
            int(response.profile.subscription_expires_at.timestamp())
            if response.profile.subscription_expires_at is not None
            else 0
        )
        return profile_pb2.ActivateSubscriptionResponse(
            success=True,
            subscription_expires_at_seconds=expires_at_seconds,
        )
