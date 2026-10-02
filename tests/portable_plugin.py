"""Optional Windows fixture adapter; uses real HA without its Linux CLI runner.

Run: pytest -p no:homeassistant -p tests.portable_plugin
Linux CI uses the official plugin and its stronger global lifecycle guards.
This adapter never substitutes Home Assistant modules or network results.
"""

import asyncio

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import frame
from pytest_homeassistant_custom_component.common import async_test_home_assistant


@pytest.fixture
async def hass(tmp_path):
    """Create an actual HA test instance using the official context helper."""
    async with async_test_home_assistant(
        asyncio.get_running_loop(), config_dir=str(tmp_path)
    ) as instance:
        frame.async_setup(instance)
        instance.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
        yield instance
        for entry in instance.config_entries.async_entries():
            if entry.state is ConfigEntryState.LOADED:
                await instance.config_entries.async_unload(entry.entry_id)
        await instance.async_stop(force=True)
