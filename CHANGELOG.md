# Changelog

All notable changes to this project will be documented in this file.

## [1.2.1] - 2026-02-11

### Added
- Automatic reconnection with exponential backoff (1s → 60s) when connection drops
- Periodic polling fallback for state synchronization (every 30 seconds)
- Connection health monitoring with keepalive after 3 minutes of silence
- Entity availability tracking — entities show as unavailable when device is disconnected
- Working device state query protocol — discovered that sending property keys with empty string values (e.g., `{"fan_power": ""}`) causes the device to report its current state
- Initial state query on connect and reconnect so entities start with accurate values

### Fixed
- Fan, light, and brightness state not reliably syncing back to Home Assistant ([#3](https://github.com/RayHollister/homewerks-smart-fan-integration/issues/3))
- Entities now start with accurate state on boot instead of defaulting to off
- Connection drops no longer require HA restart — integration reconnects automatically
- Response parser now handles multiple concatenated frames in a single TCP read
- Brightness values from device (0-255) are now correctly normalized to HA's 0-100 scale
- Send command failures now trigger automatic reconnection instead of silently failing

## [1.2.0] - 2025-01-22

### Added
- Real-time state synchronization with Home Assistant UI
- Callback system for instant entity updates when device state changes
- Initial volume fetch when speaker entity loads

### Fixed
- Entity states now properly reflect device status in Home Assistant
- State changes from device now immediately update the UI

## [1.1.2] - 2025-01-22

### Added
- Integration brand icon for Home Assistant UI and HACS

## [1.1.1] - 2025-01-22

### Added
- Fan entity icon (mdi:fan)
- Speaker entity icon (mdi:speaker)
- Disclaimer in README about unofficial status

## [1.1.0] - 2025-01-22

### Added
- Speaker volume control via media_player entity
- Volume mute/unmute support
- Volume step controls (+/- 5%)

### Fixed
- Color temperature values were inverted (warm showed as cool and vice versa)

## [1.0.0] - 2025-01-22

### Added
- Initial release
- Fan control (on/off)
- Light control (on/off)
- Light brightness adjustment (0-100%)
- Light color temperature adjustment (2200K-7000K)
- Local control via TCP port 8899
- Real-time state updates from device
