"""Guided flow validation on actual Home Assistant flow handlers."""

from custom_components.nearby_shops.config_flow import NearbyShopsConfigFlow
from custom_components.nearby_shops.const import DEFAULTS


async def test_guided_flow(hass):
    hass.states.async_set("person.a", "home")
    hass.states.async_set("sensor.gps", "ok", {"latitude": 50, "longitude": 20})
    flow = NearbyShopsConfigFlow()
    flow.hass = hass
    assert (await flow.async_step_user())["step_id"] == "user"
    assert (await flow.async_step_user({"location_entities": []}))["errors"] == {
        "location_entities": "no_entities"
    }
    assert (
        await flow.async_step_user({"location_entities": ["person.a", "sensor.gps"]})
    )["step_id"] == "shops"
    assert (await flow.async_step_shops({"shop_types": [], "name_filter": "all"}))[
        "errors"
    ] == {"shop_types": "no_shop_types"}
    assert (
        await flow.async_step_shops(
            {"shop_types": ["all"], "name_filter": "include", "names": [" "]}
        )
    )["errors"] == {"names": "no_names"}
    assert (
        await flow.async_step_shops(
            {
                "shop_types": ["all", "bakery"],
                "name_filter": "include",
                "names": ["Lidl"],
            }
        )
    )["step_id"] == "settings"
    result = await flow.async_step_settings(
        {
            key: DEFAULTS[key]
            for key in (
                "radius",
                "max_accuracy",
                "allow_missing_accuracy",
                "movement_threshold",
                "minimum_query_interval",
            )
        }
    )
    assert result["type"] == "create_entry"
    assert result["data"]["shop_types"] == ["all"]
    assert result["data"]["location_entities"] == ["person.a", "sensor.gps"]


async def test_invalid_ranges_and_unsupported_entity(hass):
    hass.states.async_set("person.a", "home")
    flow = NearbyShopsConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user({"location_entities": ["light.invalid"]})
    assert result["errors"] == {"base": "invalid_input"}
    values = {
        key: DEFAULTS[key]
        for key in (
            "radius",
            "max_accuracy",
            "allow_missing_accuracy",
            "movement_threshold",
            "minimum_query_interval",
        )
    }
    result = await flow.async_step_settings({**values, "radius": 5001})
    assert result["errors"] == {"base": "invalid_input"}
