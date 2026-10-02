"""UI-only setup and options, using native Home Assistant selectors."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN, SHOP_TYPES
from .models import location


def schema(step: str, values: dict, entities: list[str]) -> vol.Schema:
    """Build shared schemas for configuration and options."""
    fields: dict = {}
    if step in ("user", "init"):
        fields[
            vol.Required("location_entities", default=values["location_entities"])
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(multiple=True, include_entities=entities)
        )
    elif step == "shops":
        fields[vol.Required("shop_types", default=values["shop_types"])] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["all", *SHOP_TYPES],
                    multiple=True,
                    translation_key="shop_types",
                )
            )
        )
        fields[vol.Required("name_filter", default=values["name_filter"])] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["all", "include", "exclude"], translation_key="name_filter"
                )
            )
        )
        fields[vol.Optional("names", default=values["names"])] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[],
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        )
    else:
        for name, minimum, maximum, unit in (
            ("radius", 50, 5000, "m"),
            ("max_accuracy", 0, 5000, "m"),
            ("movement_threshold", 1, 5000, "m"),
            ("minimum_query_interval", 60, 86400, "s"),
        ):
            fields[vol.Required(name, default=values[name])] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=minimum,
                    max=maximum,
                    step=1,
                    unit_of_measurement=unit,
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        fields[
            vol.Required(
                "allow_missing_accuracy", default=values["allow_missing_accuracy"]
            )
        ] = selector.BooleanSelector()
    return vol.Schema(fields)


class FlowSteps(config_entries.ConfigEntryBaseFlow):
    """Identical guided screens for setup and options."""

    values: dict[str, Any]

    async def _step(
        self, step: str, user_input: dict[str, Any] | None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        entities = [
            state.entity_id
            for state in self.hass.states.async_all()
            if state.domain in ("person", "device_tracker")
            or location(dict(state.attributes), 0, True)[0] is not None
        ]
        entities = sorted(set(entities) | set(self.values["location_entities"]))
        if user_input is not None:
            try:
                cleaned = schema(step, self.values, entities)(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_input"
            else:
                self.values.update(cleaned)
                if step in ("user", "init") and not cleaned["location_entities"]:
                    errors["location_entities"] = "no_entities"
                elif step == "shops" and not cleaned["shop_types"]:
                    errors["shop_types"] = "no_shop_types"
                elif (
                    step == "shops"
                    and cleaned["name_filter"] != "all"
                    and not any(name.strip() for name in cleaned.get("names", []))
                ):
                    errors["names"] = "no_names"
                elif step in ("user", "init"):
                    return await self.async_step_shops()
                elif step == "shops":
                    if "all" in self.values["shop_types"]:
                        self.values["shop_types"] = ["all"]
                    return await self.async_step_settings()
                else:
                    return self.async_create_entry(
                        title="Nearby Shops", data=self.values
                    )
        return self.async_show_form(
            step_id=step, data_schema=schema(step, self.values, entities), errors=errors
        )

    async def async_step_shops(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose OSM tags and exact name/brand filters."""
        return await self._step("shops", user_input)

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure range, accuracy and refresh thresholds."""
        return await self._step("settings", user_input)


class NearbyShopsConfigFlow(FlowSteps, config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a group of location sources."""

    VERSION = 1

    def __init__(self) -> None:
        self.values = dict(DEFAULTS)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select sources; offline trackers may be configured."""
        return await self._step("user", user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NearbyShopsOptionsFlow:
        """Use HA's automatic reload after options are saved."""
        return NearbyShopsOptionsFlow()


class NearbyShopsOptionsFlow(FlowSteps, config_entries.OptionsFlowWithReload):
    """Edit all settings without replacing the config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Load existing settings once per options flow."""
        if not hasattr(self, "values"):
            self.values = {
                **DEFAULTS,
                **self.config_entry.data,
                **self.config_entry.options,
            }
        return await self._step("init", user_input)
