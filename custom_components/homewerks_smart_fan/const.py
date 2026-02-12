"""Constants for the Homewerks Smart Fan integration."""

DOMAIN = "homewerks_smart_fan"

# Device connection
DEFAULT_PORT = 8899
UPNP_PORT = 59152
UPNP_DESCRIPTION_PORT = 49152

# Config entry keys
CONF_UDN = "udn"
CONF_UUID = "uuid"
CONF_FRIENDLY_NAME = "friendly_name"

# Frame protocol
FRAME_HEADER = b'\x18\x96\x18\x20'
FRAME_PADDING = b'\x00' * 12
PAYLOAD_PREFIX = "MCU+PAS+"
PAYLOAD_SUFFIX = "&"

# JSON keys for commands
KEY_FAN_POWER = "fan_power"
KEY_LIGHT_POWER = "light_power"
KEY_PERCENTAGE = "percentage"
KEY_COLOR_TEMPERATURE = "colorTemperature"

# Values
VALUE_ON = "ON"
VALUE_OFF = "OFF"

# Color temperature range (Kelvin)
MIN_COLOR_TEMP_KELVIN = 2200
MAX_COLOR_TEMP_KELVIN = 7000

# Brightness range
MIN_BRIGHTNESS = 0
MAX_BRIGHTNESS = 100

# Polling interval (seconds)
SCAN_INTERVAL = 30

# Connection timeout (seconds)
CONNECTION_TIMEOUT = 5

# Discovery
DISCOVERY_TIMEOUT = 2
DISCOVERY_CONCURRENCY = 50
LINKPLAY_MANUFACTURER = "Linkplay Technology Inc."
