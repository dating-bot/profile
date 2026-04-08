from dataclasses import dataclass
from typing import final, override

import structlog
from grpclib import Status
from grpclib.exceptions import GRPCError

from profile_api.v1 import profile_pb2
from profile_api.v1.profile_grpc import ProfileServiceBase
from profile_service.app.server.utils import unary
from profile_service.domain.profile import Gender
from profile_service.usecases.create_profile.usecase import CreateProfileAlreadyExistsError, CreateProfileUsecase
from profile_service.usecases.get_presigned_url.usecase import GetPresignedUrlNotFoundError, GetPresignedUrlUsecase
from profile_service.usecases.get_profile.usecase import GetProfileUsecase
from profile_service.usecases.set_geo.usecase import SetGeoNotFoundError, SetGeoUsecase
from profile_service.usecases.update_profile.usecase import UpdateProfileNotFoundError, UpdateProfileUsecase
from profile_service.usecases.delete_photo.usecase import DeletePhotoNotFoundError, DeletePhotoUsecase
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


@final
@dataclass(slots=True)
class ProfileServiceHandler(ProfileServiceBase):
    _create_profile_usecase: CreateProfileUsecase
    _get_profile_usecase: GetProfileUsecase
    _update_profile_usecase: UpdateProfileUsecase
    _set_geo_usecase: SetGeoUsecase
    _upload_photo_usecase: UploadPhotoUsecase
    _delete_photo_usecase: DeletePhotoUsecase
    _get_presigned_url_usecase: GetPresignedUrlUsecase

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
