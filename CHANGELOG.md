# Changelog

All notable changes to this project will be documented in this file.

## [1.5.0] - 2026-05-17

### Added
- **Software-based light transitions** — the `transition` parameter is now supported in `light.turn_on`, gradually stepping through brightness values over the requested duration since the device firmware does not support native transitions
- Declared `LightEntityFeature.TRANSITION` so Home Assistant passes the transition parameter through to the entity
- Brightness transitions complete first, then color temperature is applied at the end

### Changed
- Color temperature changes during a transition are applied as a single step after the brightness fade completes, rather than simultaneously

## [1.4.0] - 2026-02-12

### Fixed
- **Brightness reset on polling** — `request_state()` no longer polls brightness, which was causing the device to reset brightness to 100% ([#4](https://github.com/RayHollister/homewerks-smart-fan-integration/issues/4))
- **Brightness reset on power-on** — `light_power=ON` is now only sent when the light is actually off; brightness and color temp changes are sent as standalone commands when the light is already on, matching the Homewerks mobile app behavior
- **Brightness 255 sentinel** — device state broadcasts reporting `percentage=255` are now ignored (sentinel value meaning "not tracked", not actual brightness); only values 0–100 are accepted
- **Color temperature snapping** — device only supports four discrete values (7000, 5500, 2700, 2200 on device scale); incoming values are now snapped to the nearest supported value ([#5](https://github.com/RayHollister/homewerks-smart-fan-integration/issues/5))
- Reverted echo suppression logic that was blocking legitimate device state updates from reaching the HA UI

### Changed
- Renamed `_snap_device_color_temp` to `_snap_color_temp` for consistency
- Corrected docstrings to accurately describe the device's inverted color temperature scale

## [1.3.0] - 2026-02-11

### Added
- **Automatic device discovery** — scans local network for Homewerks Smart Fan devices during setup so users don't need to know the IP address ([#1](https://github.com/RayHollister/homewerks-smart-fan-integration/issues/1))
- **Reconfigure flow** — easily update the device IP address via Settings → Integrations → Reconfigure without deleting and re-adding the integration
- **Automatic IP recovery** — if the device IP changes, the integration scans the network on startup to find the device by its unique identifier (UDN) and updates the config entry automatically
- Device identification via UPnP description (Linkplay-based devices on port 49152)
- Config entry stores device UDN for persistent identification across IP changes
- Manual setup shows instructions for finding the IP in the Home NetWerks Connect app

### Changed
- Config entry version bumped to 2 (automatic migration from v1)
- Unique ID changed from IP address to device UDN for stability
- Setup flow now scans for devices first, falls back to manual IP entry

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
