from datetime import UTC, datetime

import pydantic


class Photo(pydantic.BaseModel):
    id: int = pydantic.Field(description="Photo ID")
    profile_id: int = pydantic.Field(description="FK to profiles.id")
    minio_key: str = pydantic.Field(description="MinIO object key")
    is_active: bool = pydantic.Field(default=True, description="Whether photo is visible")
    is_nsfw: bool = pydantic.Field(default=False, description="Whether photo was flagged as NSFW")
    nsfw_score: float = pydantic.Field(default=0.0, description="NSFW confidence score in 0..1")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Upload timestamp",
    )
