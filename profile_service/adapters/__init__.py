from profile_service.adapters.events.rabbitmq.adapter import RabbitMQAdapter as RabbitMQAdapter
from profile_service.adapters.geocoding.mapsco.adapter import MapsCoGeocodingAdapter as MapsCoGeocodingAdapter
from profile_service.adapters.profile.postgres.adapter import (
    PostgresProfileRepositoryAdapter as PostgresProfileRepositoryAdapter,
)
from profile_service.adapters.storage.minio.adapter import MinIOStorageAdapter as MinIOStorageAdapter
