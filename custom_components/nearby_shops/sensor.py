"""Shop count and nearest shop sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NearbyShopsConfigEntry
from .entity import NearbyEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NearbyShopsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for each configured location."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            cls(coordinator, source, kind)
            for source in coordinator.settings["location_entities"]
            for cls, kind in (
                (ShopCount, "nearby_shops"),
                (NearestShop, "nearest_shop"),
            )
        ]
    )


class ShopCount(NearbyEntity, SensorEntity):
    """Count filtered nearby shops."""

    _attr_icon = "mdi:store-search"

    @property
    def native_value(self) -> int:
        return len(self.observation["shops"])

    @property
    def extra_state_attributes(self) -> dict:
        return {**super().extra_state_attributes, "shops": self.observation["shops"]}


class NearestShop(NearbyEntity, SensorEntity):
    """Name of the nearest matching shop; unknown for an empty result."""

    _attr_icon = "mdi:store-marker"

    @property
    def native_value(self) -> str | None:
        shops = self.observation["shops"]
        return shops[0]["name"][:255] if shops else None

    @property
    def extra_state_attributes(self) -> dict:
        shops = self.observation["shops"]
        return {**super().extra_state_attributes, **(shops[0] if shops else {})}
