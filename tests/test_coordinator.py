"""Preservation of last-good data and refresh decisions using real HA."""

from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nearby_shops.api import OverpassError
from custom_components.nearby_shops.const import DEFAULTS, DOMAIN
from custom_components.nearby_shops.coordinator import NearbyShopsCoordinator


async def test_good_then_poor_accuracy_then_error(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={**DEFAULTS, "location_entities": ["person.a"]}
    )
    client = MagicMock()
    client.async_search = AsyncMock(
        return_value=(
            [
                {
                    "name": "Lidl",
                    "brand": "Lidl",
                    "type": "supermarket",
                    "latitude": 50,
                    "longitude": 20,
                    "osm_id": 1,
                    "osm_type": "node",
                }
            ],
            False,
        )
    )
    coordinator = NearbyShopsCoordinator(hass, entry, client)
    hass.states.async_set(
        "person.a", "home", {"latitude": 50, "longitude": 20, "gps_accuracy": 12}
    )
    first = await coordinator._async_update_data()
    assert len(first["person.a"]["shops"]) == 1
    hass.states.async_set(
        "person.a", "away", {"latitude": 51, "longitude": 21, "gps_accuracy": 120}
    )
    second = await coordinator._async_update_data()
    assert second["person.a"]["shops"] == first["person.a"]["shops"]
    assert second["person.a"]["update_status"] == "poor_accuracy"
    assert second["person.a"]["observed_accuracy"] == 120
    assert client.async_search.call_count == 1
    client.async_search.side_effect = OverpassError("http_503")
    hass.states.async_set(
        "person.a", "away", {"latitude": 51, "longitude": 21, "gps_accuracy": 12}
    )
    third = await coordinator._async_update_data()
    assert third["person.a"]["shops"] == first["person.a"]["shops"]
    assert third["person.a"]["stale"] and third["person.a"]["last_error"] == "http_503"
    assert (
        third["person.a"]["last_successful_update"]
        == first["person.a"]["last_successful_update"]
    )


async def test_small_movement_and_removed_source(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={**DEFAULTS, "location_entities": ["person.a"]}
    )
    client = MagicMock(async_search=AsyncMock(return_value=([], False)))
    coordinator = NearbyShopsCoordinator(hass, entry, client)
    hass.states.async_set("person.a", "home", {"latitude": 50, "longitude": 20})
    await coordinator._async_update_data()
    hass.states.async_set("person.a", "home", {"latitude": 50.00001, "longitude": 20})
    result = await coordinator._async_update_data()
    assert result["person.a"]["update_status"] == "movement_threshold"
    assert client.async_search.call_count == 1
    hass.states.async_remove("person.a")
    result = await coordinator._async_update_data()
    assert result["person.a"]["stale"]
    assert result["person.a"]["update_status"] == "location_unavailable"
