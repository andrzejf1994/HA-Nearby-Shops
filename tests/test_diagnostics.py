"""Diagnostics must not expose personal locations or source identifiers."""

import json

from custom_components.nearby_shops.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .test_lifecycle import setup


async def test_redaction(hass, mock_overpass):
    entry = await setup(hass)
    entry.runtime_data.settings["names"] = ["Private Shop"]
    data = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(data)
    assert "person.andrzej" not in serialized
    assert "Private Shop" not in serialized
    assert data["trackers"][0]["latitude"] == "**REDACTED**"
    assert data["trackers"][0]["longitude"] == "**REDACTED**"
    assert data["tracker_count"] == 1
    assert data["trackers"][0]["location_accuracy"] == 12
