"""Nearby Shops config-entry lifecycle."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .api import OverpassClient
from .const import DOMAIN
from .coordinator import NearbyShopsCoordinator

type NearbyShopsConfigEntry = ConfigEntry[NearbyShopsCoordinator]
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NearbyShopsConfigEntry) -> bool:
    """Set up without requiring GPS or Overpass availability at startup."""
    shared = hass.data.setdefault(
        DOMAIN,
        {"client": OverpassClient(async_get_clientsession(hass)), "entries": set()},
    )
    coordinator = NearbyShopsCoordinator(hass, entry, shared["client"])
    entry.runtime_data = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        if not shared["entries"]:
            hass.data.pop(DOMAIN, None)
        raise

    @callback
    def location_changed(event) -> None:
        entry.async_create_background_task(
            hass, coordinator.async_request_refresh(), "Nearby Shops location refresh"
        )

    entry.async_on_unload(
        async_track_state_change_event(
            hass, coordinator.settings["location_entities"], location_changed
        )
    )
    shared["entries"].add(entry.entry_id)
    registry = er.async_get(hass)
    valid_ids = {
        f"{entry.entry_id}_{source}_{kind}"
        for source in coordinator.settings["location_entities"]
        for kind in ("nearby_shops", "nearest_shop", "near_shop")
    }
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.unique_id not in valid_ids:
            registry.async_remove(registered.entity_id)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NearbyShopsConfigEntry
) -> bool:
    """Stop platforms, subscriptions, refresh timers and entry tasks."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        shared = hass.data[DOMAIN]
        shared["entries"].discard(entry.entry_id)
        if not shared["entries"]:
            hass.data.pop(DOMAIN)
        return True
    return False
