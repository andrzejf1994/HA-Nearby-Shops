"""Privacy-preserving config entry diagnostics."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NearbyShopsConfigEntry

REDACT = {
    "location_entities",
    "location_entity",
    "latitude",
    "longitude",
    "names",
    "shops",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NearbyShopsConfigEntry
) -> dict:
    """Never export source identities, shop names or any GPS coordinates."""
    coordinator = entry.runtime_data
    client = coordinator.client
    return {
        "configuration": async_redact_data(coordinator.settings, REDACT),
        "tracker_count": len(coordinator.settings["location_entities"]),
        "trackers": [
            async_redact_data({**item, "poi_count": len(item["shops"])}, REDACT)
            for item in coordinator.data.values()
        ],
        "overpass": {
            "status": client.status,
            "requests": client.requests,
            "failures": client.failures,
        },
        "cache": {"entries": len(client.cache), "hits": client.hits},
    }
