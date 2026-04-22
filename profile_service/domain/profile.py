from datetime import UTC, datetime
from enum import StrEnum

import pydantic


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class Profile(pydantic.BaseModel):
    id: int = pydantic.Field(description="Profile ID")
    user_id: int = pydantic.Field(description="FK to users.id")
    telegram_id: int = pydantic.Field(description="Telegram user ID (denormalized for convenience)")
    name: str | None = pydantic.Field(None, description="Display name")
    bio: str | None = pydantic.Field(None, description="Bio text")
    age: int | None = pydantic.Field(None, description="Age in years")
    gender: Gender | None = pydantic.Field(None, description="Gender")
    city: str | None = pydantic.Field(None, description="City name")
    latitude: float | None = pydantic.Field(None, description="WGS84 latitude")
    longitude: float | None = pydantic.Field(None, description="WGS84 longitude")
    ai_quality_score: float | None = pydantic.Field(None, description="AI quality score 0–10")
    is_active: bool = pydantic.Field(default=True, description="Whether profile is active")
    boost_expires_at: datetime | None = pydantic.Field(None, description="When boost expires")
    created_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation timestamp",
    )
    updated_at: datetime = pydantic.Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last update timestamp",
    )
