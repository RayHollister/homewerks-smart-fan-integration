# Homewerks Smart Fan Integration for Home Assistant

A custom Home Assistant integration for the Homewerks Smart Fan (7148-01-AX) with Alexa, LED Light, and Bluetooth Speakers.

## Disclaimer

**This is an unofficial, community-developed integration.** It is not created, endorsed, supported, or affiliated with Homewerks Worldwide, LLC or any of its subsidiaries. "Homewerks" is a trademark of Homewerks Worldwide, LLC.

This integration was developed through reverse engineering of the device's network protocol for personal use and is provided "as is" without warranty of any kind. Use at your own risk.

- No official support is available from Homewerks for this integration
- This integration may stop working if the device firmware is updated
- The authors are not responsible for any damage to your device or system

## Features

- **Fan Control**: Turn the bathroom exhaust fan on/off
- **Light Control**: Turn the LED light on/off
- **Brightness Control**: Adjust light brightness (0-100%)
- **Color Temperature**: Adjust light color from warm white (2200K) to cool white (7000K)
- **Speaker Volume**: Control the built-in Bluetooth speaker volume (0-100%)
- **Volume Mute**: Mute/unmute the speaker

## Supported Devices

- Homewerks 7148-01-AX Smart Bathroom Fan

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Search for "Homewerks Smart Fan" and install it
7. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/homewerks_smart_fan` folder
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Homewerks Smart Fan"
4. The integration will automatically scan your network for Homewerks Smart Fan devices
5. **If your fan is found**: Select it from the list and click **Submit**
6. **If your fan is not found**: Choose "Enter IP address manually" and enter the IP address

### Finding Your Fan's IP Address

If automatic discovery doesn't find your fan, you can find the IP address in the **Home NetWerks Connect** app:

1. Open the **Home NetWerks Connect** app
2. Go to **Devices**
3. Tap the **⚙️ gear icon** on your device
4. Tap **Speaker Info**
5. The **IP** address will be displayed

### Changing the IP Address

If your fan's IP address changes (e.g., after a router reboot or DHCP reassignment):

- **Automatic recovery**: The integration will automatically scan the network to find the device by its unique identifier on the next Home Assistant restart. No action needed in most cases.
- **Manual update**: Go to **Settings** → **Devices & Services** → find the Homewerks Smart Fan integration → click **⋮** (three dots) → **Reconfigure**. The integration will scan for devices, or you can enter the new IP address manually.

## Technical Details

This integration communicates directly with the fan over your local network using a TCP connection on port 8899. No cloud services are required.

### Protocol

The fan uses a Linkplay-based module with a custom MCU for fan and light control. Commands are sent as JSON payloads with a binary frame header.

## Troubleshooting

### Cannot Connect

- Ensure the fan is powered on and connected to your WiFi network
- Verify the IP address is correct
- Check that port 8899 is not blocked by your firewall
- Try restarting the fan by turning it off and on at the circuit breaker

### State Not Updating

The integration uses both real-time push updates and periodic polling (every 30 seconds) to keep state in sync. It also automatically reconnects if the connection drops. If the state still isn't updating:

- Check your Home Assistant logs for connection errors
- Verify the fan's IP address hasn't changed (check your router's DHCP client list)
- Try removing and re-adding the integration

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes in each version.

## License

MIT License
