"""The Homewerks Smart Fan integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .api import HomewerksSmartFanApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewerks Smart Fan from a config entry."""
    host = entry.data[CONF_HOST]

    api = HomewerksSmartFanApi(host)

    if not await api.connect():
        _LOGGER.error("Failed to connect to Homewerks Smart Fan at %s", host)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api: HomewerksSmartFanApi = hass.data[DOMAIN].pop(entry.entry_id)
        await api.disconnect()

    return unload_ok
