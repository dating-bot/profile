from typing import Protocol


class GeocodingProtocol(Protocol):
    async def geocode_city(self, city: str) -> tuple[float, float] | None: ...
