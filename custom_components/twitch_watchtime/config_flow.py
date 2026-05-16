"""Config flow for twitch_watchtime."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import (
    TwitchWatchtimeAuthError,
    TwitchWatchtimeClient,
    TwitchWatchtimeConnectionError,
    _normalize_host,
)
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_USER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OPT_IDLE_TIMEOUT,
    OPT_SCAN_INTERVAL,
    USER_ALL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)


class TwitchWatchtimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two-step setup: validate host+key, then pick a user."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._api_key: str | None = None
        self._users: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            api_key = user_input[CONF_API_KEY]
            session = async_get_clientsession(self.hass)
            client = TwitchWatchtimeClient(host=host, api_key=api_key, session=session)
            try:
                await client.async_check_health()
                self._users = await client.async_get_users()
            except TwitchWatchtimeAuthError:
                errors["base"] = "invalid_auth"
            except TwitchWatchtimeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating watchtime backend")
                errors["base"] = "unknown"
            else:
                self._host = host
                self._api_key = api_key
                return await self.async_step_account()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_account(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            assert self._host is not None
            assert self._api_key is not None
            chosen = user_input[CONF_USER]
            unique = f"{self._host}:{chosen}"
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()
            title = "All accounts" if chosen == USER_ALL else chosen
            return self.async_create_entry(
                title=title,
                data={CONF_HOST: self._host, CONF_API_KEY: self._api_key, CONF_USER: chosen},
            )

        # Build the dropdown: All accounts + each known user
        options: dict[str, str] = {USER_ALL: "All accounts"}
        for u in self._users:
            label = (
                f"{u['user']} — {u['count']} entries"
                if u.get("count") is not None
                else u["user"]
            )
            options[u["user"]] = label

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({vol.Required(CONF_USER): vol.In(options)}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TwitchWatchtimeOptionsFlow:
        return TwitchWatchtimeOptionsFlow(config_entry)


class TwitchWatchtimeOptionsFlow(config_entries.OptionsFlow):
    """Lets the user tweak scan interval and idle timeout after install."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_SCAN_INTERVAL,
                    default=opts.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                vol.Required(
                    OPT_IDLE_TIMEOUT,
                    default=opts.get(OPT_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
                ): vol.All(int, vol.Range(min=30, max=600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
