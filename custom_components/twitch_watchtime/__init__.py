"""The twitch_watchtime integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwitchWatchtimeClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_USER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_SCAN_INTERVAL,
    PLATFORMS,
    USER_ALL,
)
from .coordinator import TwitchWatchtimeCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry: create client + coordinator, forward to platforms."""
    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    user = entry.data[CONF_USER]
    user_param: str | None = None if user == USER_ALL else user

    scan_interval = entry.options.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = async_get_clientsession(hass)
    client = TwitchWatchtimeClient(host=host, api_key=api_key, session=session)
    coordinator = TwitchWatchtimeCoordinator(
        hass,
        client=client,
        user=user_param,
        scan_interval=timedelta(seconds=scan_interval),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
