"""Fan platform for Homewerks Smart Fan."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomewerksSmartFanApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homewerks Smart Fan from a config entry."""
    api: HomewerksSmartFanApi = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "Homewerks Smart Fan")

    async_add_entities([HomewerksSmartFanEntity(api, entry, name)])


class HomewerksSmartFanEntity(FanEntity):
    """Representation of a Homewerks Smart Fan."""

    _attr_has_entity_name = True
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_icon = "mdi:fan"
    _attr_should_poll = False

    def __init__(
        self,
        api: HomewerksSmartFanApi,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the fan."""
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_name = "Fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": name,
            "manufacturer": "Homewerks",
            "model": "7148-01-AX Smart Fan",
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self._api.register_state_callback(self._handle_state_update)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed from hass."""
        self._api.unregister_state_callback(self._handle_state_update)

    @callback
    def _handle_state_update(self) -> None:
        """Handle state update from the API."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._api.state.get("fan_power", False)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self._api.set_fan_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._api.set_fan_power(False)
