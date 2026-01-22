"""Light platform for Homewerks Smart Fan."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomewerksSmartFanApi
from .const import DOMAIN, MAX_COLOR_TEMP_KELVIN, MIN_COLOR_TEMP_KELVIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homewerks Smart Fan light from a config entry."""
    api: HomewerksSmartFanApi = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "Homewerks Smart Fan")

    async_add_entities([HomewerksSmartFanLight(api, entry, name)])


class HomewerksSmartFanLight(LightEntity):
    """Representation of a Homewerks Smart Fan light."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN

    def __init__(
        self,
        api: HomewerksSmartFanApi,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the light."""
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_name = "Light"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": name,
            "manufacturer": "Homewerks",
            "model": "7148-01-AX Smart Fan",
        }

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._api.state.get("light_power", False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light (0-255)."""
        # Convert from 0-100 to 0-255
        percentage = self._api.state.get("brightness", 100)
        return int(percentage * 255 / 100)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._api.state.get("color_temp", 4000)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # Handle brightness change
        if ATTR_BRIGHTNESS in kwargs:
            # Convert from 0-255 to 0-100
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await self._api.set_brightness(brightness)

        # Handle color temperature change
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self._api.set_color_temperature(kwargs[ATTR_COLOR_TEMP_KELVIN])

        # Turn on the light
        await self._api.set_light_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._api.set_light_power(False)
