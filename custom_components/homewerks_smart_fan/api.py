"""API client for Homewerks Smart Fan."""

import asyncio
import json
import logging
import struct
from typing import Any

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_PORT,
    FRAME_HEADER,
    FRAME_PADDING,
    KEY_COLOR_TEMPERATURE,
    KEY_FAN_POWER,
    KEY_LIGHT_POWER,
    KEY_PERCENTAGE,
    PAYLOAD_PREFIX,
    PAYLOAD_SUFFIX,
    VALUE_OFF,
    VALUE_ON,
)

_LOGGER = logging.getLogger(__name__)


class HomewerksSmartFanApi:
    """API client for communicating with Homewerks Smart Fan."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {
            "fan_power": False,
            "light_power": False,
            "brightness": 100,
            "color_temp": 4000,
        }
        self._listener_task: asyncio.Task | None = None
        self._connected = False

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    @property
    def state(self) -> dict[str, Any]:
        """Return the current state."""
        return self._state.copy()

    def _build_frame(self, data: dict[str, Any]) -> bytes:
        """Build a frame for sending to the device."""
        payload = f'{PAYLOAD_PREFIX}{json.dumps(data)}{PAYLOAD_SUFFIX}'
        payload_bytes = payload.encode('utf-8')
        length = struct.pack('<I', len(payload_bytes))
        return FRAME_HEADER + length + FRAME_PADDING + payload_bytes

    def _parse_response(self, data: bytes) -> dict[str, Any] | None:
        """Parse a response from the device."""
        try:
            # Find the JSON payload
            prefix = PAYLOAD_PREFIX.encode()
            suffix = PAYLOAD_SUFFIX.encode()

            start = data.find(prefix)
            if start == -1:
                return None

            start += len(prefix)
            end = data.find(suffix, start)
            if end == -1:
                return None

            json_str = data[start:end].decode('utf-8').strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse response: %s", err)
            return None

    def _update_state_from_response(self, parsed: dict[str, Any]) -> None:
        """Update internal state from parsed response."""
        if KEY_FAN_POWER in parsed:
            self._state["fan_power"] = parsed[KEY_FAN_POWER] == VALUE_ON
        if KEY_LIGHT_POWER in parsed:
            self._state["light_power"] = parsed[KEY_LIGHT_POWER] == VALUE_ON
        if KEY_PERCENTAGE in parsed:
            self._state["brightness"] = parsed[KEY_PERCENTAGE]
        if KEY_COLOR_TEMPERATURE in parsed:
            self._state["color_temp"] = parsed[KEY_COLOR_TEMPERATURE]

    async def connect(self) -> bool:
        """Connect to the device."""
        async with self._lock:
            if self._connected:
                return True

            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=CONNECTION_TIMEOUT,
                )
                self._connected = True
                _LOGGER.debug("Connected to %s:%s", self._host, self._port)

                # Start background listener
                self._listener_task = asyncio.create_task(self._listen_for_updates())

                return True
            except (OSError, asyncio.TimeoutError) as err:
                _LOGGER.error("Failed to connect to %s:%s: %s", self._host, self._port, err)
                self._connected = False
                return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._lock:
            if self._listener_task:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
                self._listener_task = None

            if self._writer:
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass
                self._writer = None
                self._reader = None

            self._connected = False
            _LOGGER.debug("Disconnected from %s:%s", self._host, self._port)

    async def _listen_for_updates(self) -> None:
        """Listen for state updates from the device."""
        while self._connected and self._reader:
            try:
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=60,
                )
                if not data:
                    _LOGGER.warning("Connection closed by device")
                    self._connected = False
                    break

                parsed = self._parse_response(data)
                if parsed:
                    _LOGGER.debug("Received state update: %s", parsed)
                    self._update_state_from_response(parsed)

            except asyncio.TimeoutError:
                # No data received, continue listening
                continue
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.debug("Error reading from device: %s", err)
                self._connected = False
                break

    async def _send_command(self, data: dict[str, Any]) -> bool:
        """Send a command to the device."""
        if not self._connected:
            if not await self.connect():
                return False

        async with self._lock:
            try:
                frame = self._build_frame(data)
                self._writer.write(frame)
                await self._writer.drain()

                # Wait briefly for response
                await asyncio.sleep(0.3)

                # Update state optimistically
                self._update_state_from_response(data)

                _LOGGER.debug("Sent command: %s", data)
                return True

            except Exception as err:
                _LOGGER.error("Failed to send command: %s", err)
                self._connected = False
                return False

    async def set_fan_power(self, on: bool) -> bool:
        """Turn the fan on or off."""
        return await self._send_command({KEY_FAN_POWER: VALUE_ON if on else VALUE_OFF})

    async def set_light_power(self, on: bool) -> bool:
        """Turn the light on or off."""
        return await self._send_command({KEY_LIGHT_POWER: VALUE_ON if on else VALUE_OFF})

    async def set_brightness(self, brightness: int) -> bool:
        """Set the light brightness (0-100)."""
        brightness = max(0, min(100, brightness))
        return await self._send_command({KEY_PERCENTAGE: brightness})

    async def set_color_temperature(self, temp_kelvin: int) -> bool:
        """Set the color temperature in Kelvin."""
        temp_kelvin = max(2200, min(7000, temp_kelvin))
        return await self._send_command({KEY_COLOR_TEMPERATURE: temp_kelvin})

    async def test_connection(self) -> bool:
        """Test if we can connect to the device."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=CONNECTION_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            return False
