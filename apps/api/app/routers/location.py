from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.config import settings

router = APIRouter(prefix="/location", tags=["location"])

_CACHE_TTL_SECONDS = 60 * 60 * 6
_REVERSE_CACHE: dict[tuple[float, float], tuple[float, dict[str, str | None]]] = {}


def _cache_key(latitude: float, longitude: float) -> tuple[float, float]:
    return (round(latitude, 4), round(longitude, 4))


def _get_cached_result(latitude: float, longitude: float) -> tuple[dict[str, str | None], str] | None:
    key = _cache_key(latitude, longitude)
    cached = _REVERSE_CACHE.get(key)
    if not cached:
        return None

    cached_at, payload = cached
    if time.monotonic() - cached_at > _CACHE_TTL_SECONDS:
        _REVERSE_CACHE.pop(key, None)
        return None

    provider = payload.get("provider") or "nominatim"
    return payload, provider


@router.get("/reverse")
def reverse_location(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> dict[str, str | None]:
    cached = _get_cached_result(latitude, longitude)
    if cached is not None:
        payload, provider_name = cached
        return {
            "district": payload.get("district"),
            "state": payload.get("state"),
            "display_name": payload.get("display_name"),
            "provider": provider_name,
        }

    payload: dict | None = None
    provider_name = "nominatim"

    try:
        if settings.locationiq_api_key:
            provider_name = "locationiq"
            response = httpx.get(
                "https://us1.locationiq.com/v1/reverse.php",
                params={
                    "key": settings.locationiq_api_key,
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "addressdetails": 1,
                },
                timeout=10.0,
            )
        else:
            response = httpx.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "accept-language": "en",
                },
                headers={"User-Agent": "NewsReels/1.0 (+https://newsreels.local)"},
                timeout=10.0,
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="location provider request failed") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="location provider returned invalid data")

    address = payload.get("address") or {}
    district = (
        address.get("city_district")
        or address.get("county")
        or address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
    )
    state = address.get("state") or address.get("state_district") or address.get("province")
    result = {
        "district": district,
        "state": state,
        "display_name": payload.get("display_name"),
        "provider": provider_name,
    }
    _REVERSE_CACHE[_cache_key(latitude, longitude)] = (time.monotonic(), result)
    return result
