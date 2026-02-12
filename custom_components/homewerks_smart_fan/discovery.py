"""Device discovery for Homewerks Smart Fan."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from xml.etree import ElementTree

import aiohttp

from .const import (
    DEFAULT_PORT,
    DISCOVERY_CONCURRENCY,
    DISCOVERY_TIMEOUT,
    LINKPLAY_MANUFACTURER,
    UPNP_DESCRIPTION_PORT,
)

_LOGGER = logging.getLogger(__name__)

UPNP_NS = "{urn:schemas-upnp-org:device-1-0}"


@dataclass
class DiscoveredDevice:
    """Represents a discovered Homewerks Smart Fan."""

    host: str
    friendly_name: str
    udn: str
    uuid: str
    manufacturer: str
    model_name: str
    model_description: str


async def fetch_device_info(host: str) -> DiscoveredDevice | None:
    """Fetch UPnP device info from a specific host.

    Returns a DiscoveredDevice if the host has a Linkplay-based device
    with an MCU control port (8899), or None otherwise.
    """
    url = f"http://{host}:{UPNP_DESCRIPTION_PORT}/description.xml"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=DISCOVERY_TIMEOUT)
            ) as response:
                if response.status != 200:
                    return None
                xml_text = await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return None

    try:
        root = ElementTree.fromstring(xml_text)
        device = root.find(f"{UPNP_NS}device")
        if device is None:
            return None

        manufacturer = _text(device, f"{UPNP_NS}manufacturer")
        if LINKPLAY_MANUFACTURER not in (manufacturer or ""):
            return None

        # Verify MCU control port is reachable
        if not await _check_port(host, DEFAULT_PORT):
            return None

        udn = _text(device, f"{UPNP_NS}UDN") or ""
        uuid_raw = _text(device, f"{UPNP_NS}uuid") or ""

        return DiscoveredDevice(
            host=host,
            friendly_name=_text(device, f"{UPNP_NS}friendlyName") or "Unknown",
            udn=udn,
            uuid=uuid_raw,
            manufacturer=manufacturer or "",
            model_name=_text(device, f"{UPNP_NS}modelName") or "",
            model_description=_text(device, f"{UPNP_NS}modelDescription") or "",
        )
    except ElementTree.ParseError:
        _LOGGER.debug("Failed to parse UPnP XML from %s", host)
        return None


async def discover_devices(
    network_prefix: str | None = None,
) -> list[DiscoveredDevice]:
    """Scan the local /24 subnet for Homewerks Smart Fan devices.

    If network_prefix is not provided, attempts to detect it automatically.
    network_prefix should be like "10.0.0" (first three octets).
    """
    if network_prefix is None:
        network_prefix = await _detect_network_prefix()
        if network_prefix is None:
            _LOGGER.warning("Could not detect local network prefix for discovery")
            return []

    _LOGGER.debug("Scanning %s.0/24 for Homewerks Smart Fan devices", network_prefix)

    semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)
    devices: list[DiscoveredDevice] = []

    async def _probe(host_suffix: int) -> None:
        host = f"{network_prefix}.{host_suffix}"
        async with semaphore:
            # Quick port check first to avoid slow HTTP timeout
            if not await _check_port(host, UPNP_DESCRIPTION_PORT):
                return
            device = await fetch_device_info(host)
            if device:
                _LOGGER.debug("Discovered device: %s at %s", device.friendly_name, host)
                devices.append(device)

    tasks = [_probe(i) for i in range(1, 255)]
    await asyncio.gather(*tasks)

    return devices


async def find_device_by_udn(udn: str) -> DiscoveredDevice | None:
    """Scan the network for a device matching the given UDN.

    Used for automatic IP recovery when a device's IP changes.
    """
    devices = await discover_devices()
    for device in devices:
        if device.udn == udn:
            return device
    return None


async def _check_port(host: str, port: int) -> bool:
    """Check if a TCP port is open on a host."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=DISCOVERY_TIMEOUT,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _detect_network_prefix() -> str | None:
    """Try to detect the local network prefix (first 3 octets).

    Uses a non-blocking approach to determine the local IP.
    """
    import socket

    def _get_prefix() -> str | None:
        try:
            # Connect to a public DNS to determine local IP (no data sent)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            parts = local_ip.split(".")
            if len(parts) == 4:
                return ".".join(parts[:3])
        except Exception:
            pass
        return None

    return await asyncio.get_running_loop().run_in_executor(None, _get_prefix)


def _text(element: ElementTree.Element, tag: str) -> str | None:
    """Get text content of a child element."""
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None
