"""The Homewerks Smart Fan integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .api import HomewerksSmartFanApi
from .const import CONF_FRIENDLY_NAME, CONF_UDN, CONF_UUID, DOMAIN
from .discovery import fetch_device_info, find_device_by_udn

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT, Platform.MEDIA_PLAYER]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry from older versions."""
    if entry.version < 2:
        _LOGGER.info("Migrating config entry %s from version %s", entry.entry_id, entry.version)

        host = entry.data.get(CONF_HOST)
        new_data = dict(entry.data)

        # Try to fetch UPnP info to get UDN
        if host and CONF_UDN not in new_data:
            device = await fetch_device_info(host)
            if device and device.udn:
                new_data[CONF_UDN] = device.udn
                new_data[CONF_UUID] = device.uuid
                new_data[CONF_FRIENDLY_NAME] = device.friendly_name
                _LOGGER.info(
                    "Migration: discovered UDN %s for %s", device.udn, host
                )
            else:
                # Can't reach UPnP — store empty, will be populated later
                new_data.setdefault(CONF_UDN, "")
                new_data.setdefault(CONF_UUID, "")
                new_data.setdefault(CONF_FRIENDLY_NAME, "")
                _LOGGER.warning(
                    "Migration: could not fetch UPnP info from %s. "
                    "UDN will be populated on next successful connection.",
                    host,
                )

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=2,
        )
        _LOGGER.info("Migration complete for %s", entry.entry_id)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewerks Smart Fan from a config entry."""
    host = entry.data[CONF_HOST]
    udn = entry.data.get(CONF_UDN, "")

    api = HomewerksSmartFanApi(host)

    if not await api.connect():
        # Connection failed — try IP recovery if we have a UDN
        if udn:
            _LOGGER.warning(
                "Cannot reach %s, scanning network for device UDN %s",
                host, udn,
            )
            recovered_device = await find_device_by_udn(udn)
            if recovered_device and recovered_device.host != host:
                _LOGGER.info(
                    "Device IP changed: %s → %s. Updating config entry.",
                    host, recovered_device.host,
                )
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_HOST: recovered_device.host},
                )
                api = HomewerksSmartFanApi(recovered_device.host)
                if not await api.connect():
                    _LOGGER.error(
                        "Still cannot connect to %s after IP recovery",
                        recovered_device.host,
                    )
                    return False
            else:
                _LOGGER.error(
                    "Could not find device on network. "
                    "Use 'Reconfigure' to update the IP address."
                )
                return False
        else:
            _LOGGER.error(
                "Failed to connect to Homewerks Smart Fan at %s", host
            )
            return False

    # If we connected but don't have UDN yet, try to fetch it now
    if not udn:
        device = await fetch_device_info(entry.data[CONF_HOST])
        if device and device.udn:
            _LOGGER.info("Populated UDN %s for %s", device.udn, entry.data[CONF_HOST])
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_UDN: device.udn,
                    CONF_UUID: device.uuid,
                    CONF_FRIENDLY_NAME: device.friendly_name,
                },
            )

    # Request initial state from the device
    await api.request_state()

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
