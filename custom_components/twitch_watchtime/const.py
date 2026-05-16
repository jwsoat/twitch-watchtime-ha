"""Constants for the twitch_watchtime integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "twitch_watchtime"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Config entry keys
CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_USER = "user"  # Twitch login, "all_accounts" sentinel, or a custom-typed login

# Special value used in CONF_USER when the entry should pool all accounts.
USER_ALL = "all_accounts"

# Options flow keys
OPT_SCAN_INTERVAL = "scan_interval"
OPT_IDLE_TIMEOUT = "idle_timeout"

# Defaults
DEFAULT_SCAN_INTERVAL = 10  # seconds — matches the backend heartbeat cadence
DEFAULT_IDLE_TIMEOUT = 120  # seconds — matches the API's /stats/now window
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# Manufacturer/model strings shown in HA device info
MANUFACTURER = "Twitch Watchtime"
MODEL = "Self-hosted"
