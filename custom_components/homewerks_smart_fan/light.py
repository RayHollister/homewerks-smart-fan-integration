"""Light platform for Homewerks Smart Fan."""

from __future__ import annotations

from datetime import timedelta
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomewerksSmartFanApi
from .const import (
    DOMAIN,
    KEY_COLOR_TEMPERATURE,
    KEY_LIGHT_POWER,
    KEY_PERCENTAGE,
    MAX_COLOR_TEMP_KELVIN,
    MIN_COLOR_TEMP_KELVIN,
    SCAN_INTERVAL as SCAN_INTERVAL_SECONDS,
    SUPPORTED_DEVICE_COLOR_TEMPS,
    VALUE_ON,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)


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
    _attr_should_poll = True

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
        """Turn on the light.

        Sends all attributes as a single combined command to avoid
        race conditions where a power-on resets brightness to 100%.
        Color temperature is snapped to the four values the device
        firmware supports: 2200, 2700, 5500, 7000 (device scale).
        """
        command: dict[str, Any] = {}

        # Handle brightness change
        if ATTR_BRIGHTNESS in kwargs:
            # Convert from HA 0-255 to device 0-100
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            command[KEY_PERCENTAGE] = brightness

        # Handle color temperature change
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            temp_kelvin = max(MIN_COLOR_TEMP_KELVIN, min(MAX_COLOR_TEMP_KELVIN, temp_kelvin))
            # Invert to device scale, then snap to nearest supported value
            device_temp = MIN_COLOR_TEMP_KELVIN + MAX_COLOR_TEMP_KELVIN - temp_kelvin
            device_temp = min(SUPPORTED_DEVICE_COLOR_TEMPS, key=lambda t: abs(t - device_temp))
            command[KEY_COLOR_TEMPERATURE] = device_temp

        # Always include power-on in the same frame
        command[KEY_LIGHT_POWER] = VALUE_ON

        await self._api.send_command(command)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._api.set_light_power(False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.connected

    async def async_update(self) -> None:
        """Poll the device for current state as a fallback."""
        await self._api.request_state()
