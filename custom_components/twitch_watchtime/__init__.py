"""The twitch_watchtime integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwitchWatchtimeClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_IDLE_TIMEOUT,
    OPT_SCAN_INTERVAL,
    PLATFORMS,
    PLATFORM_TWITCH,
    USER_ALL,
)
from .coordinator import TwitchWatchtimeCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    platform = entry.data[CONF_PLATFORM]
    user = entry.data[CONF_USER]
    scan_interval = timedelta(
        seconds=entry.options.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    idle_timeout = entry.options.get(OPT_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)

    session = async_get_clientsession(hass)
    client = TwitchWatchtimeClient(host=host, api_key=api_key, session=session)

    coordinator = TwitchWatchtimeCoordinator(
        hass=hass,
        client=client,
        platform=platform,
        user=user if user != USER_ALL else None,
        scan_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "idle_timeout": idle_timeout,
        "platform": platform,
        "user": user,
    }

    device_name = f"{platform.title()} - {user}"
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{platform}_{user}")},
        name=device_name,
    )

    # Set up sensors and binary sensors with platform-aware unique_id
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor", "binary_sensor"],
    )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change so the new scan interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
