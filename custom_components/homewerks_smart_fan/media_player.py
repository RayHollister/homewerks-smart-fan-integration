"""Media player platform for Homewerks Smart Fan speaker."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomewerksSmartFanApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

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

    async def async_update(self) -> None:
        """Fetch current volume from device."""
        await self._api.get_volume()
