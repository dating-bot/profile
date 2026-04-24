import asyncio
import time
from collections import OrderedDict
from typing import Any, final

import httpx
import structlog

from profile_service.infra.geocoding import GeocodingConfig
from profile_service.protocols.geocoding.protocol import GeocodingProtocol

log = structlog.stdlib.get_logger("profile_service.adapters.geocoding.mapsco")


@final
class MapsCoGeocodingAdapter(GeocodingProtocol):
    def __init__(self, *, config: GeocodingConfig) -> None:
        self._config = config
        self._cache: OrderedDict[str, tuple[float, float, float]] = OrderedDict()
        self._cache_lock = asyncio.Lock()

    async def geocode_city(self, city: str) -> tuple[float, float] | None:
        if not self._config.enabled:
            return None
        if not self._config.api_key:
            return None

        city_query = city.strip()
        if not city_query:
            return None
        cache_key = city_query.casefold()

        cached = await self._cache_get(cache_key)
        if cached is not None:
            log.info("city geocoding cache hit", city=city_query, latitude=cached[0], longitude=cached[1])
            return cached

        log.info("city geocoding provider request", city=city_query, provider="maps.co")
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                response = await client.get(
                    f"{self._config.base_url.rstrip('/')}/search",
                    params={
                        "q": city_query,
                        "api_key": self._config.api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            log.exception("city geocoding request failed", city=city_query)
            return None

        if not isinstance(payload, list) or not payload:
            log.info("city geocoding empty result", city=city_query)
            return None

        candidate = payload[0]
        if not isinstance(candidate, dict):
            return None

        lat = _parse_float(candidate.get("lat"))
        lon = _parse_float(candidate.get("lon"))
        if lat is None or lon is None:
            return None

        await self._cache_set(cache_key, (lat, lon))
        log.info("city geocoded", city=city_query, latitude=lat, longitude=lon)
        return (lat, lon)

    async def _cache_get(self, city_key: str) -> tuple[float, float] | None:
        now = time.monotonic()
        async with self._cache_lock:
            entry = self._cache.get(city_key)
            if entry is None:
                return None
            lat, lon, expires_at = entry
            if expires_at <= now:
                self._cache.pop(city_key, None)
                return None
            self._cache.move_to_end(city_key)
            return (lat, lon)

    async def _cache_set(self, city_key: str, geo: tuple[float, float]) -> None:
        now = time.monotonic()
        expires_at = now + max(self._config.cache_ttl_seconds, 1)
        async with self._cache_lock:
            self._cache[city_key] = (geo[0], geo[1], expires_at)
            self._cache.move_to_end(city_key)

            while len(self._cache) > self._config.cache_max_entries:
                self._cache.popitem(last=False)


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
