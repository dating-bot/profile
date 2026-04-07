from typing import final

import dishka
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service import adapters, infra, protocols, usecases
from profile_service.app.server import grpc_handler


@final
class InfraProvider(dishka.Provider):
    scope = dishka.Scope.APP

    global_config = dishka.provide(staticmethod(infra.GlobalConfig.load))
    subconfigs = dishka.provide_all(*infra.GlobalConfig.subconfigs())
    async_engine = dishka.provide(staticmethod(infra.provide_async_engine))
    async_session_factory = dishka.provide(staticmethod(infra.provide_async_session_factory))
    rabbitmq_connection = dishka.provide(staticmethod(infra.provide_rabbitmq_connection))
    rabbitmq_topology = dishka.provide(staticmethod(infra.provide_rabbitmq_topology))
    aioboto3_session = dishka.provide(staticmethod(infra.provide_aioboto3_session))


@final
class AdapterProvider(dishka.Provider):
    scope = dishka.Scope.APP

    profile_repository = dishka.provide(
        source=adapters.PostgresProfileRepositoryAdapter,
        provides=protocols.ProfileRepositoryProtocol,
    )
    storage = dishka.provide(
        source=adapters.MinIOStorageAdapter,
        provides=protocols.StorageProtocol,
    )
    message_queue = dishka.provide(
        source=adapters.RabbitMQAdapter,
        provides=protocols.MessageQueueProtocol,
    )


@final
class UsecaseProvider(dishka.Provider):
    scope = dishka.Scope.APP

    create_profile_usecase = dishka.provide(usecases.CreateProfileUsecase)
    get_profile_usecase = dishka.provide(usecases.GetProfileUsecase)
    update_profile_usecase = dishka.provide(usecases.UpdateProfileUsecase)
    set_geo_usecase = dishka.provide(usecases.SetGeoUsecase)
    upload_photo_usecase = dishka.provide(usecases.UploadPhotoUsecase)

    @dishka.provide
    def get_presigned_url_usecase(
        self,
        profile_repository: protocols.ProfileRepositoryProtocol[AsyncSession],
        storage: protocols.StorageProtocol,
        minio_config: infra.MinIOConfig,
    ) -> usecases.GetPresignedUrlUsecase:
        """юзкейс генерации presigned URL для фото (TTL из конфига MinIO)"""
        return usecases.GetPresignedUrlUsecase(
            profile_repository=profile_repository,
            storage=storage,
            presigned_ttl_seconds=minio_config.presigned_ttl_seconds,
        )


@final
class AppProvider(dishka.Provider):
    scope = dishka.Scope.APP

    grpc_service_handler = dishka.provide(grpc_handler.ProfileServiceHandler)


container = dishka.make_async_container(InfraProvider(), AdapterProvider(), UsecaseProvider(), AppProvider())
