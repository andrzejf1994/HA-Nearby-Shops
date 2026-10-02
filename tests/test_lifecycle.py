"""Real HA config-entry, platform and options reload tests."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nearby_shops.const import DEFAULTS, DOMAIN


async def setup(hass):
    hass.states.async_set(
        "person.andrzej", "home", {"latitude": 50, "longitude": 20, "gps_accuracy": 12}
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={**DEFAULTS, "location_entities": ["person.andrzej"]}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_unload(hass, mock_overpass):
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert mock_overpass.call_count == 1
    assert hass.states.get("sensor.andrzej_nearby_shops").state == "0"
    assert hass.states.get("sensor.andrzej_nearest_shop").state == "unknown"
    assert hass.states.get("binary_sensor.andrzej_near_shop").state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data
    hass.states.async_set("person.andrzej", "away", {"latitude": 51, "longitude": 21})
    await hass.async_block_till_done()
    assert mock_overpass.call_count == 1


async def test_options_reload(hass, mock_overpass):
    entry = await setup(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"location_entities": ["person.andrzej"]}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"shop_types": ["all"], "name_filter": "all", "names": []}
    )
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                key: value
                for key, value in {**DEFAULTS, "radius": 500}.items()
                if key
                in (
                    "radius",
                    "max_accuracy",
                    "allow_missing_accuracy",
                    "movement_threshold",
                    "minimum_query_interval",
                )
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        reload.assert_called_once_with(entry.entry_id)
    assert entry.runtime_data.settings["radius"] == 500
    assert entry.state is ConfigEntryState.LOADED


async def test_offline_setup(hass, mock_overpass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={**DEFAULTS, "location_entities": ["person.missing"]}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_overpass.assert_not_called()
    assert hass.states.get("sensor.missing_nearby_shops").state == "unavailable"


async def test_options_remove_source_prunes_registry(hass, mock_overpass):
    entry = await setup(hass)
    hass.states.async_set("person.marta", "home", {"latitude": 50, "longitude": 20})
    hass.config_entries.async_update_entry(
        entry, options={**DEFAULTS, "location_entities": ["person.marta"]}
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registered) == 3
    assert all("person.marta" in entity.unique_id for entity in registered)


async def test_duplicate_source_object_names_have_distinct_unique_ids(
    hass, mock_overpass
):
    hass.states.async_set("person.a", "home", {"latitude": 50, "longitude": 20})
    hass.states.async_set("device_tracker.a", "home", {"latitude": 50, "longitude": 20})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**DEFAULTS, "location_entities": ["person.a", "device_tracker.a"]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registered) == 6
    assert len({entity.unique_id for entity in registered}) == 6
