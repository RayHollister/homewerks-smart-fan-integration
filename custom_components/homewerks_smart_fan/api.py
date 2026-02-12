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
    SUPPORTED_DEVICE_COLOR_TEMPS,
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
        self._reconnect_task: asyncio.Task | None = None
        self._connected = False
        self._upnp_port = UPNP_PORT
        self._state_callbacks: list[callable] = []
        self._reconnect_delay = 1  # Start with 1 second
        self._max_reconnect_delay = 60  # Cap at 60 seconds
        self._should_reconnect = True

    def register_state_callback(self, callback: callable) -> None:
        """Register a callback to be called when state changes."""
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    def unregister_state_callback(self, callback: callable) -> None:
        """Unregister a state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def _notify_state_change(self) -> None:
        """Notify all registered callbacks of a state change."""
        for callback in self._state_callbacks:
            try:
                callback()
            except Exception as err:
                _LOGGER.debug("Error in state callback: %s", err)

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

    def _parse_response(self, data: bytes) -> list[dict[str, Any]]:
        """Parse one or more responses from the device.

        The device may send multiple frames concatenated in a single read.
        Returns a list of parsed JSON payloads.
        """
        results = []
        prefix = PAYLOAD_PREFIX.encode()
        suffix = PAYLOAD_SUFFIX.encode()
        search_start = 0

        while search_start < len(data):
            start = data.find(prefix, search_start)
            if start == -1:
                break

            start += len(prefix)
            end = data.find(suffix, start)
            if end == -1:
                break

            try:
                json_str = data[start:end].decode('utf-8').strip()
                parsed = json.loads(json_str)
                results.append(parsed)
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                _LOGGER.debug("Failed to parse response: %s", err)

            search_start = end + len(suffix)

        return results

    def _invert_color_temp(self, temp: int) -> int:
        """Invert color temperature (device uses opposite scale from standard Kelvin)."""
        # Device: 2200 = cool, 7000 = warm (opposite of standard Kelvin)
        # Standard Kelvin: 2200 = warm, 7000 = cool
        return MIN_COLOR_TEMP_KELVIN + MAX_COLOR_TEMP_KELVIN - temp

    @staticmethod
    def _snap_device_color_temp(device_temp: int) -> int:
        """Snap a device color temperature to the nearest supported value.

        The device only supports four discrete color temps:
        7000 (warm), 5500 (soft), 2700 (cool), 2200 (daylight).
        """
        return min(SUPPORTED_DEVICE_COLOR_TEMPS, key=lambda t: abs(t - device_temp))

    def _update_state_from_response(self, parsed: dict[str, Any], notify: bool = True) -> None:
        """Update internal state from parsed response."""
        changed = False
        if KEY_FAN_POWER in parsed:
            new_val = parsed[KEY_FAN_POWER] == VALUE_ON
            if self._state["fan_power"] != new_val:
                self._state["fan_power"] = new_val
                changed = True
        if KEY_LIGHT_POWER in parsed:
            new_val = parsed[KEY_LIGHT_POWER] == VALUE_ON
            if self._state["light_power"] != new_val:
                self._state["light_power"] = new_val
                changed = True
        if KEY_PERCENTAGE in parsed:
            raw_val = parsed[KEY_PERCENTAGE]
            # Device broadcasts percentage=255 as a sentinel meaning
            # "I don't track brightness". Ignore it — only accept 0-100.
            if isinstance(raw_val, (int, float)) and raw_val <= 100:
                new_val = int(raw_val)
                if self._state["brightness"] != new_val:
                    self._state["brightness"] = new_val
                    changed = True
        if KEY_COLOR_TEMPERATURE in parsed:
            # Invert color temp from device scale to standard Kelvin
            device_temp = parsed[KEY_COLOR_TEMPERATURE]
            new_val = self._invert_color_temp(device_temp)
            if self._state["color_temp"] != new_val:
                self._state["color_temp"] = new_val
                changed = True

        if changed and notify:
            self._notify_state_change()

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
                self._reconnect_delay = 1  # Reset backoff on successful connect
                _LOGGER.debug("Connected to %s:%s", self._host, self._port)

                # Start background listener
                self._listener_task = asyncio.create_task(self._listen_for_updates())

                return True
            except (OSError, asyncio.TimeoutError) as err:
                _LOGGER.error("Failed to connect to %s:%s: %s", self._host, self._port, err)
                self._connected = False
                return False

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._should_reconnect:
            return

        _LOGGER.info(
            "Scheduling reconnect to %s in %s seconds",
            self._host,
            self._reconnect_delay,
        )
        await asyncio.sleep(self._reconnect_delay)

        # Exponential backoff
        self._reconnect_delay = min(
            self._reconnect_delay * 2, self._max_reconnect_delay
        )

        if await self.connect():
            _LOGGER.info("Reconnected to %s:%s", self._host, self._port)
            # Request current state after reconnecting
            await self.request_state()
        elif self._should_reconnect:
            # Failed to reconnect, try again
            self._reconnect_task = asyncio.create_task(self._schedule_reconnect())

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        self._should_reconnect = False

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

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
        consecutive_timeouts = 0
        max_timeouts_before_healthcheck = 3

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

                consecutive_timeouts = 0  # Reset on successful read
                parsed_list = self._parse_response(data)
                for parsed in parsed_list:
                    _LOGGER.debug("Received state update: %s", parsed)
                    self._update_state_from_response(parsed)

            except asyncio.TimeoutError:
                consecutive_timeouts += 1
                if consecutive_timeouts >= max_timeouts_before_healthcheck:
                    # Connection may be dead, try a health check
                    _LOGGER.debug(
                        "No data for %s minutes, sending keepalive",
                        consecutive_timeouts,
                    )
                    try:
                        query = {KEY_FAN_POWER: ""}
                        frame = self._build_frame(query)
                        self._writer.write(frame)
                        await self._writer.drain()
                        consecutive_timeouts = 0
                    except Exception:
                        _LOGGER.warning("Keepalive failed, connection appears dead")
                        self._connected = False
                        break
                continue
            except asyncio.CancelledError:
                return  # Don't reconnect if deliberately cancelled
            except Exception as err:
                _LOGGER.debug("Error reading from device: %s", err)
                self._connected = False
                break

        # Connection lost — schedule reconnection
        if self._should_reconnect and not self._connected:
            _LOGGER.warning("Connection lost to %s, will attempt reconnect", self._host)
            self._reconnect_task = asyncio.create_task(self._schedule_reconnect())

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

                # Update state optimistically and notify
                self._update_state_from_response(data, notify=True)

                _LOGGER.debug("Sent command: %s", data)
                return True

            except Exception as err:
                _LOGGER.error("Failed to send command: %s", err)
                self._connected = False
                if self._should_reconnect:
                    self._reconnect_task = asyncio.create_task(
                        self._schedule_reconnect()
                    )
                return False

    async def request_state(self) -> bool:
        """Request current state from the device.

        Sending a key with an empty string value causes the device to
        report back the current value for that key.
        """
        if not self._connected:
            if not await self.connect():
                return False

        async with self._lock:
            try:
                query = {
                    KEY_FAN_POWER: "",
                    KEY_LIGHT_POWER: "",
                }
                frame = self._build_frame(query)
                self._writer.write(frame)
                await self._writer.drain()
                _LOGGER.debug("Requested state from device")
                return True
            except Exception as err:
                _LOGGER.debug("Failed to request state: %s", err)
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
        # Invert to device scale, then snap to nearest supported value
        device_temp = self._invert_color_temp(temp_kelvin)
        device_temp = self._snap_device_color_temp(device_temp)
        return await self._send_command({KEY_COLOR_TEMPERATURE: device_temp})

    async def send_command(self, data: dict[str, Any]) -> bool:
        """Send a combined command to the device (public API)."""
        return await self._send_command(data)

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
                if self._state["volume"] != volume:
                    self._state["volume"] = volume
                    self._notify_state_change()
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
            if self._state["volume"] != volume:
                self._state["volume"] = volume
                self._notify_state_change()
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
