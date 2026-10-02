"""Common coordinator-backed location entity."""

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NearbyShopsCoordinator


class NearbyEntity(CoordinatorEntity[NearbyShopsCoordinator]):
    """Stable identity includes source domain to avoid person/tracker collisions."""

    _attr_attribution = "© OpenStreetMap contributors"

    def __init__(
        self, coordinator: NearbyShopsCoordinator, entity_id: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self.location_entity = entity_id
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_id}_{kind}"
        state = coordinator.hass.states.get(entity_id)
        source_name = state.name if state else entity_id.split(".", 1)[-1]
        self._attr_name = f"{source_name} {kind.replace('_', ' ')}"

    @property
    def observation(self) -> dict[str, Any]:
        return self.coordinator.data[self.location_entity]

    @property
    def available(self) -> bool:
        return self.observation["has_data"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.observation.items()
            if key not in ("shops", "has_data")
        }
