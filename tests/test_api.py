"""Transport, cache coverage and failure tests without real HTTP."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.nearby_shops.api import OverpassClient, OverpassError
from custom_components.nearby_shops.models import Location


def client_with_response(status=200, payload=None):
    response = MagicMock(status=status, headers={})
    response.json = AsyncMock(
        return_value=payload if payload is not None else {"elements": []}
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = context
    return OverpassClient(session), response


async def test_cache_shares_nearby_coverage_and_serializes():
    client, _ = client_with_response()
    a, b = await asyncio.gather(
        client.async_search(Location(50, 20, None), 300, ["all"]),
        client.async_search(Location(50.0001, 20, None), 300, ["all"]),
    )
    assert not a[1] and b[1]
    assert client.session.post.call_count == 1


async def test_cache_radius_types_expiry():
    client, _ = client_with_response()
    point = Location(50, 20, None)
    with patch("custom_components.nearby_shops.api.monotonic", return_value=1000):
        await client.async_search(point, 300, ["all"])
    with patch("custom_components.nearby_shops.api.monotonic", return_value=1010):
        await client.async_search(point, 500, ["all"])
    with patch("custom_components.nearby_shops.api.monotonic", return_value=1020):
        await client.async_search(point, 300, ["bakery"])
    with patch("custom_components.nearby_shops.api.monotonic", return_value=1400):
        await client.async_search(point, 300, ["all"])
    assert client.requests == 4


@pytest.mark.parametrize("status", [429, 500, 503, 404])
async def test_http_errors_backoff(status):
    client, response = client_with_response(status)
    response.headers = {"Retry-After": "120"}
    with pytest.raises(OverpassError, match=f"http_{status}"):
        await client.async_search(Location(50, 20, None), 300, ["all"])
    with pytest.raises(OverpassError, match="backoff"):
        await client.async_search(Location(50, 20, None), 300, ["all"])
    assert client.session.post.call_count == 1
    assert not client.cache


@pytest.mark.parametrize(
    "error", [TimeoutError(), aiohttp.ClientConnectionError(), ValueError("bad JSON")]
)
async def test_transport_and_json_errors(error):
    client, response = client_with_response()
    response.json.side_effect = error
    with pytest.raises(OverpassError):
        await client.async_search(Location(50, 20, None), 300, ["all"])


async def test_partial_response_is_not_cached():
    client, _ = client_with_response(
        payload={"elements": [], "remark": "runtime error: timeout"}
    )
    with pytest.raises(OverpassError, match="invalid_response"):
        await client.async_search(Location(50, 20, None), 300, ["all"])


async def test_query_and_input_safety():
    client, _ = client_with_response()
    await client.async_search(Location(50, 20, None), 300, ["supermarket", "bakery"])
    query = client.session.post.call_args.kwargs["data"]["data"]
    assert "nwr(around:375" in query and "out center tags" in query
    assert "^(bakery|supermarket)$" in query
    with pytest.raises(ValueError):
        await client.async_search(Location(50, 20, None), 300, ['bad"tag'])


async def test_safety_throttle_waits_for_distant_sources():
    client, _ = client_with_response()
    with patch(
        "custom_components.nearby_shops.api.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await client.async_search(Location(50, 20, None), 300, ["all"])
        await client.async_search(Location(51, 21, None), 300, ["all"])
        sleep.assert_awaited_once()
        assert client.requests == 2


async def test_cancellation_releases_shared_lock():
    client, response = client_with_response()
    response.json.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await client.async_search(Location(50, 20, None), 300, ["all"])
    assert not client.lock.locked()
    assert client.failures == 0
