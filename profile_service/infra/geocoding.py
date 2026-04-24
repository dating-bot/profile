from pydantic import BaseModel, Field


class GeocodingConfig(BaseModel):
    enabled: bool = Field(default=False, description="Enable city geocoding")
    base_url: str = Field(default="https://geocode.maps.co", description="Geocoding provider base URL")
    api_key: str | None = Field(default=None, description="Provider API key")
    timeout_seconds: float = Field(default=5.0, description="HTTP timeout in seconds")
    cache_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, description="City geocoding cache TTL in seconds")
    cache_max_entries: int = Field(default=50_000, description="Max in-memory cached cities")
