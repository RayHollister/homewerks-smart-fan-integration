"""Media player platform for Homewerks Smart Fan speaker."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomewerksSmartFanApi
from .const import DOMAIN, SCAN_INTERVAL as SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homewerks Smart Fan speaker from a config entry."""
    api: HomewerksSmartFanApi = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "Homewerks Smart Fan")

    async_add_entities([HomewerksSmartFanSpeaker(api, entry, name)])


class HomewerksSmartFanSpeaker(MediaPlayerEntity):
    """Representation of a Homewerks Smart Fan speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:speaker"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )
    _attr_should_poll = True

    def __init__(
        self,
        api: HomewerksSmartFanApi,
        entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the speaker."""
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_speaker"
        self._attr_name = "Speaker"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": name,
            "manufacturer": "Homewerks",
            "model": "7148-01-AX Smart Fan",
        }
        self._is_muted = False

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self._api.register_state_callback(self._handle_state_update)
        # Fetch initial volume
        await self._api.get_volume()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed from hass."""
        self._api.unregister_state_callback(self._handle_state_update)

    @callback
    def _handle_state_update(self) -> None:
        """Handle state update from the API."""
        self.async_write_ha_state()

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        # Speaker is always available when device is connected
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 to 1.0)."""
        volume = self._api.state.get("volume", 50)
        return volume / 100.0

    @property
    def is_volume_muted(self) -> bool | None:
        """Return if volume is muted."""
        return self._is_muted

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self._api.set_volume(int(volume * 100))

    async def async_volume_up(self) -> None:
        """Increase volume by 5%."""
        current = self._api.state.get("volume", 50)
        await self._api.set_volume(min(100, current + 5))

    async def async_volume_down(self) -> None:
        """Decrease volume by 5%."""
        current = self._api.state.get("volume", 50)
        await self._api.set_volume(max(0, current - 5))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the speaker."""
        if await self._api.set_mute(mute):
            self._is_muted = mute
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.connected

    async def async_update(self) -> None:
        """Poll the device for current volume state."""
        await self._api.get_volume()
