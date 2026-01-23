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
4. Enter the IP address of your fan (find it in your router's DHCP client list)
5. Click **Submit**

## Finding Your Fan's IP Address

The fan will appear on your network with a hostname like "Bathroom" (or whatever you named it in the Home NetWerks app). You can find its IP address by:

1. Checking your router's DHCP client list
2. Using a network scanner app
3. Looking in the Home NetWerks Connect app settings

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

The integration receives state updates from the fan in real-time. If the state isn't updating:
- Check your Home Assistant logs for connection errors
- Try removing and re-adding the integration

## License

MIT License
