from minio import Minio
from pydantic import BaseModel, Field


class MinIOConfig(BaseModel):
    endpoint: str = Field(description="MinIO endpoint (host:port)")
    access_key: str = Field(description="Access key")
    secret_key: str = Field(description="Secret key")
    bucket: str = Field(description="Bucket name for profile photos")
    secure: bool = Field(default=False, description="Use HTTPS")
    presigned_ttl_seconds: int = Field(default=900, description="Presigned URL TTL in seconds")


def provide_minio_client(config: MinIOConfig) -> Minio:
    return Minio(
        endpoint=config.endpoint,
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=config.secure,
    )
