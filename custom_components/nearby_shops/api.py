"""Generic OSM transport and bounded shared spatial cache."""

import asyncio
import logging
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any

import aiohttp

from .const import CACHE_MARGIN, CACHE_TTL, ENDPOINT, MAX_CACHE_ENTRIES
from .models import Location, distance, parse_elements

_LOGGER = logging.getLogger(__name__)


class OverpassError(Exception):
    """Transient transport failure with a safe diagnostic code."""


@dataclass
class CacheItem:
    """Coverage circle and its raw POIs."""

    point: Location
    radius: float
    query_key: tuple[str, tuple[str, ...]]
    created: float
    pois: list[dict[str, Any]]


class OverpassClient:
    """Serialize requests across entries; share coverage without radius edge loss."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.lock = asyncio.Lock()
        self.cache: list[CacheItem] = []
        self.hits = 0
        self.requests = 0
        self.next_request = 0.0
        self.retry_until = 0.0
        self.failures = 0
        self.status = "idle"

    async def async_search(
        self, point: Location, radius: float, values: list[str], key: str = "shop"
    ) -> tuple[list[dict], bool]:
        """Fetch generic tagged POIs, with cache coverage and server backoff."""
        if not re.fullmatch(r"[a-z_]+", key) or any(
            not re.fullmatch(r"[a-z_]+", value) for value in values
        ):
            raise ValueError("Invalid OSM selector")
        query_key = (key, tuple(sorted(set(values))))
        async with self.lock:
            now = monotonic()
            self.cache = [item for item in self.cache if now - item.created < CACHE_TTL]
            for item in self.cache:
                if (
                    item.query_key == query_key
                    and distance(
                        point.latitude,
                        point.longitude,
                        item.point.latitude,
                        item.point.longitude,
                    )
                    + radius
                    <= item.radius
                ):
                    self.hits += 1
                    _LOGGER.debug("Cache hit")
                    return item.pois, True
            if now < self.retry_until:
                raise OverpassError("backoff")
            if now < self.next_request:
                await asyncio.sleep(self.next_request - now)
                now = monotonic()
            query_radius = radius + CACHE_MARGIN
            selector = (
                f'["{key}"]'
                if "all" in values
                else f'["{key}"~"^({"|".join(query_key[1])})$"]'
            )
            query = f"[out:json][timeout:25];nwr(around:{query_radius},{point.latitude},{point.longitude}){selector};out center tags;"
            self.requests += 1
            self.next_request = now + 5  # Global safety throttle, even for large jumps.
            _LOGGER.debug("Querying Overpass for %s", key)
            try:
                async with self.session.post(
                    ENDPOINT,
                    data={"data": query},
                    timeout=aiohttp.ClientTimeout(total=35),
                    headers={
                        "User-Agent": "NearbyShops/0.1.0 (Home Assistant; github.com/andrzejf1994/HA-Nearby-Shops)"
                    },
                ) as response:
                    if response.status != 200:
                        retry = response.headers.get("Retry-After", "")
                        delay = (
                            min(3600, max(60, int(retry))) if retry.isdecimal() else 60
                        )
                        if response.status == 429:
                            self.retry_until = monotonic() + delay
                        raise OverpassError(f"http_{response.status}")
                    payload = await response.json()
                    pois = parse_elements(payload, key)
            except (
                aiohttp.ClientError,
                TimeoutError,
                ValueError,
                OverpassError,
            ) as err:
                self.failures += 1
                self.status = (
                    str(err)
                    if isinstance(err, OverpassError)
                    else "timeout"
                    if isinstance(err, TimeoutError)
                    else "invalid_response"
                    if isinstance(err, ValueError)
                    else "connection_error"
                )
                self.retry_until = max(
                    self.retry_until,
                    monotonic() + min(900, 30 * 2 ** min(self.failures - 1, 5)),
                )
                if self.failures == 1:
                    _LOGGER.warning("Overpass temporarily unavailable: %s", self.status)
                raise OverpassError(self.status) from err
            self.failures = 0
            self.status = "ok"
            self.cache.append(
                CacheItem(point, query_radius, query_key, monotonic(), pois)
            )
            self.cache = self.cache[-MAX_CACHE_ENTRIES:]
            _LOGGER.debug("Received %s POIs", len(pois))
            return pois, False
