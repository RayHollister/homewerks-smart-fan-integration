"""Config flow for Homewerks Smart Fan integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import HomewerksSmartFanApi
from .const import CONF_FRIENDLY_NAME, CONF_UDN, CONF_UUID, DOMAIN
from .discovery import DiscoveredDevice, discover_devices, fetch_device_info

_LOGGER = logging.getLogger(__name__)

MANUAL_ENTRY = "manual"


async def validate_connection(hass: HomeAssistant, host: str) -> bool:
    """Validate that we can connect to the device's MCU port."""
    api = HomewerksSmartFanApi(host)
    return await api.test_connection()


async def validate_and_fetch_info(
    hass: HomeAssistant, host: str
) -> DiscoveredDevice:
    """Validate connection and fetch device info.

    Raises CannotConnect if the device isn't reachable.
    """
    api = HomewerksSmartFanApi(host)
    if not await api.test_connection():
        raise CannotConnect

    device = await fetch_device_info(host)
    if device is None:
        # Device is reachable on 8899 but no UPnP description.
        # Create a minimal device info with no UDN.
        device = DiscoveredDevice(
            host=host,
            friendly_name="Homewerks Smart Fan",
            udn="",
            uuid="",
            manufacturer="Unknown",
            model_name="Unknown",
            model_description="",
        )

    return device


class HomewerksSmartFanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homewerks Smart Fan."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_devices: list[DiscoveredDevice] = []
        self._selected_device: DiscoveredDevice | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — scan for devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User chose a device or manual entry
            selection = user_input.get("device")
            if selection == MANUAL_ENTRY:
                return await self.async_step_manual()

            # Find the selected device
            for device in self._discovered_devices:
                if device.udn == selection:
                    self._selected_device = device
                    break

            if self._selected_device:
                return await self._async_create_or_update_entry(
                    self._selected_device
                )

        # Scan for devices
        self._discovered_devices = await discover_devices()

        if not self._discovered_devices:
            # No devices found, go straight to manual entry
            return await self.async_step_manual()

        # Build selection list
        device_options = {
            device.udn: f"{device.friendly_name} ({device.host})"
            for device in self._discovered_devices
        }
        device_options[MANUAL_ENTRY] = "Enter IP address manually..."

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            name = user_input.get(CONF_NAME, "").strip()

            try:
                device = await validate_and_fetch_info(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                if name:
                    device.friendly_name = name
                return await self._async_create_or_update_entry(device)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_NAME, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration — update the IP address."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            selection = user_input.get("device")
            if selection == MANUAL_ENTRY:
                return await self.async_step_reconfigure_manual()

            # Find the selected device
            for device in self._discovered_devices:
                if device.host == selection:
                    self._selected_device = device
                    break

            if self._selected_device:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: self._selected_device.host},
                )

        # Scan for devices
        self._discovered_devices = await discover_devices()

        if not self._discovered_devices:
            return await self.async_step_reconfigure_manual()

        # Build selection — use host as key since UDN might match
        current_host = entry.data.get(CONF_HOST, "")
        device_options = {}
        for device in self._discovered_devices:
            label = f"{device.friendly_name} ({device.host})"
            if device.host == current_host:
                label += " (current)"
            device_options[device.host] = label
        device_options[MANUAL_ENTRY] = "Enter IP address manually..."

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
            errors=errors,
        )

    async def async_step_reconfigure_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry during reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        current_host = entry.data.get(CONF_HOST, "")

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            try:
                device = await validate_and_fetch_info(self.hass, host)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                # Update the entry with new host (and UDN if we got one)
                data_updates = {CONF_HOST: host}
                if device.udn:
                    data_updates[CONF_UDN] = device.udn
                    data_updates[CONF_UUID] = device.uuid

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

        return self.async_show_form(
            step_id="reconfigure_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                }
            ),
            errors=errors,
        )

    async def _async_create_or_update_entry(
        self, device: DiscoveredDevice
    ) -> ConfigFlowResult:
        """Create a config entry from a discovered device."""
        # Use UDN as unique ID if available, fall back to host
        unique_id = device.udn if device.udn else device.host
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: device.host}
        )

        title = device.friendly_name or "Homewerks Smart Fan"

        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: device.host,
                CONF_NAME: title,
                CONF_UDN: device.udn,
                CONF_UUID: device.uuid,
                CONF_FRIENDLY_NAME: device.friendly_name,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
