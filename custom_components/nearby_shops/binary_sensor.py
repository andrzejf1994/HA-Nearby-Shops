"""Presence of a matching shop within radius."""

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Create proximity entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NearShop(coordinator, source, "near_shop")
        for source in coordinator.settings["location_entities"]
    )


class NearShop(NearbyEntity, BinarySensorEntity):
    """True if at least one filtered shop is nearby."""

    _attr_icon = "mdi:store-check"

    @property
    def is_on(self) -> bool:
        return bool(self.observation["shops"])

    @property
    def extra_state_attributes(self) -> dict:
        shops = self.observation["shops"]
        return {
            **super().extra_state_attributes,
            "shop_count": len(shops),
            "nearest_shop": shops[0]["name"] if shops else None,
            "nearest_distance": shops[0]["distance"] if shops else None,
        }
