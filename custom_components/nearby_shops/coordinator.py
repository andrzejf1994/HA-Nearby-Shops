"""Coordinate location events, periodic refresh and last-good observations."""

import logging
from datetime import timedelta
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import OverpassClient, OverpassError
from .const import DEFAULTS
from .models import Location, filter_shops, location, number, should_query

_LOGGER = logging.getLogger(__name__)


class NearbyShopsCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """One coordinator for all trackers of an entry."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OverpassClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Nearby Shops",
            config_entry=entry,
            update_interval=timedelta(seconds=15),
        )
        self.settings = {**DEFAULTS, **entry.data, **entry.options}
        self.client = client
        self.previous: dict[str, Location] = {}
        self.attempts: dict[str, float] = {}
        self.observations: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        result = {}
        for entity_id in self.settings["location_entities"]:
            old = self.observations.get(entity_id, {"shops": [], "has_data": False})
            item = {
                **old,
                "radius": self.settings["radius"],
                "location_entity": entity_id,
                "stale": True,
                "last_error": old.get("last_error"),
            }
            state = self.hass.states.get(entity_id)
            item["observed_accuracy"] = (
                number(state.attributes.get("gps_accuracy")) if state else None
            )
            point, status = location(
                dict(state.attributes) if state else {},
                self.settings["max_accuracy"],
                self.settings["allow_missing_accuracy"],
            )
            if state is None or state.state in ("unknown", "unavailable"):
                point, status = None, "location_unavailable"
            if point is None:
                item["update_status"] = status
                _LOGGER.debug("Skipping location update: %s", status)
            else:
                now = monotonic()
                elapsed = now - self.attempts.get(entity_id, -float("inf"))
                if not should_query(
                    point,
                    self.previous.get(entity_id),
                    elapsed,
                    self.settings["movement_threshold"],
                    self.settings["minimum_query_interval"],
                ):
                    item["update_status"] = "movement_threshold"
                    item["stale"] = old.get("stale", False)
                    _LOGGER.debug("Skipping update: movement threshold")
                else:
                    self.attempts[entity_id] = now
                    try:
                        pois, cached = await self.client.async_search(
                            point, self.settings["radius"], self.settings["shop_types"]
                        )
                    except OverpassError as err:
                        item["update_status"] = "api_error"
                        item["last_error"] = str(err)
                    else:
                        self.previous[entity_id] = point
                        item.update(
                            shops=filter_shops(pois, point, self.settings),
                            has_data=True,
                            latitude=point.latitude,
                            longitude=point.longitude,
                            location_accuracy=point.accuracy,
                            stale=False,
                            last_error=None,
                            update_status="cache_hit" if cached else "updated",
                            last_successful_update=dt_util.utcnow().isoformat(),
                        )
                    item["last_query_attempt"] = dt_util.utcnow().isoformat()
            result[entity_id] = item
        self.observations = result
        return result
