"""HA fixtures and deterministic Overpass mocks; never access the network."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def enable_custom_integrations_fixture(request):
    """Allow this repository's custom component."""
    if request.config.pluginmanager.hasplugin("homeassistant"):
        request.getfixturevalue("enable_custom_integrations")
    yield


@pytest.fixture
def mock_overpass():
    """Replace transport at the integration boundary for HA lifecycle tests."""
    with (
        patch(
            "custom_components.nearby_shops.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.nearby_shops.api.OverpassClient.async_search",
            new_callable=AsyncMock,
        ) as mock,
    ):
        mock.return_value = ([], False)
        yield mock
