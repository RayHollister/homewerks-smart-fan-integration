"""API client for Homewerks Smart Fan."""

import asyncio
import json
import logging
import struct
from typing import Any
import aiohttp

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_PORT,
    FRAME_HEADER,
    FRAME_PADDING,
    KEY_COLOR_TEMPERATURE,
    KEY_FAN_POWER,
    KEY_LIGHT_POWER,
    KEY_PERCENTAGE,
    MAX_COLOR_TEMP_KELVIN,
    MIN_COLOR_TEMP_KELVIN,
    PAYLOAD_PREFIX,
    PAYLOAD_SUFFIX,
    UPNP_PORT,
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
            "volume": 50,
        }
        self._listener_task: asyncio.Task | None = None
        self._connected = False
        self._upnp_port = UPNP_PORT

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

    def _invert_color_temp(self, temp: int) -> int:
        """Invert color temperature (device uses opposite scale from standard Kelvin)."""
        # Device: 2200 = cool, 7000 = warm (opposite of standard Kelvin)
        # Standard Kelvin: 2200 = warm, 7000 = cool
        return MIN_COLOR_TEMP_KELVIN + MAX_COLOR_TEMP_KELVIN - temp

    def _update_state_from_response(self, parsed: dict[str, Any]) -> None:
        """Update internal state from parsed response."""
        if KEY_FAN_POWER in parsed:
            self._state["fan_power"] = parsed[KEY_FAN_POWER] == VALUE_ON
        if KEY_LIGHT_POWER in parsed:
            self._state["light_power"] = parsed[KEY_LIGHT_POWER] == VALUE_ON
        if KEY_PERCENTAGE in parsed:
            self._state["brightness"] = parsed[KEY_PERCENTAGE]
        if KEY_COLOR_TEMPERATURE in parsed:
            # Invert color temp from device scale to standard Kelvin
            device_temp = parsed[KEY_COLOR_TEMPERATURE]
            self._state["color_temp"] = self._invert_color_temp(device_temp)

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
        temp_kelvin = max(MIN_COLOR_TEMP_KELVIN, min(MAX_COLOR_TEMP_KELVIN, temp_kelvin))
        # Invert to device scale before sending
        device_temp = self._invert_color_temp(temp_kelvin)
        return await self._send_command({KEY_COLOR_TEMPERATURE: device_temp})

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

    async def _upnp_action(self, service: str, action: str, args: str = "") -> str | None:
        """Execute a UPnP SOAP action."""
        url = f"http://{self._host}:{self._upnp_port}/upnp/control/rendercontrol1"
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"urn:schemas-upnp-org:service:{service}:1#{action}"',
        }
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}:1">
      <InstanceID>0</InstanceID>
      {args}
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, data=body, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return await response.text()
        except Exception as err:
            _LOGGER.error("UPnP action failed: %s", err)
            return None

    async def get_volume(self) -> int | None:
        """Get the current volume level (0-100)."""
        response = await self._upnp_action(
            "RenderingControl",
            "GetVolume",
            "<Channel>Master</Channel>",
        )
        if response and "<CurrentVolume>" in response:
            try:
                start = response.find("<CurrentVolume>") + len("<CurrentVolume>")
                end = response.find("</CurrentVolume>")
                volume = int(response[start:end])
                self._state["volume"] = volume
                return volume
            except (ValueError, IndexError):
                pass
        return None

    async def set_volume(self, volume: int) -> bool:
        """Set the volume level (0-100)."""
        volume = max(0, min(100, volume))
        response = await self._upnp_action(
            "RenderingControl",
            "SetVolume",
            f"<Channel>Master</Channel><DesiredVolume>{volume}</DesiredVolume>",
        )
        if response:
            self._state["volume"] = volume
            return True
        return False

    async def get_mute(self) -> bool | None:
        """Get the current mute state."""
        response = await self._upnp_action(
            "RenderingControl",
            "GetMute",
            "<Channel>Master</Channel>",
        )
        if response and "<CurrentMute>" in response:
            try:
                start = response.find("<CurrentMute>") + len("<CurrentMute>")
                end = response.find("</CurrentMute>")
                return response[start:end] == "1"
            except (ValueError, IndexError):
                pass
        return None

    async def set_mute(self, mute: bool) -> bool:
        """Set the mute state."""
        response = await self._upnp_action(
            "RenderingControl",
            "SetMute",
            f"<Channel>Master</Channel><DesiredMute>{1 if mute else 0}</DesiredMute>",
        )
        return response is not None
