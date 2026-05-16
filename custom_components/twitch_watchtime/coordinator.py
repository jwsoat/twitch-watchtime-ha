"""DataUpdateCoordinator for the twitch_watchtime integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TwitchWatchtimeAuthError,
    TwitchWatchtimeClient,
    TwitchWatchtimeConnectionError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TwitchWatchtimeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the backend and exposes the merged snapshot to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: TwitchWatchtimeClient,
        user: str | None,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{user or 'all_accounts'}",
            update_interval=scan_interval,
        )
        self._client = client
        self._user = user

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = await self._client.async_fetch_snapshot(user=self._user)
            now = snapshot.get("now")
            channel = now.get("channel") if now else None
            if channel:
                snapshot["now_channel_today_seconds"] = await self._client.async_get_channel_today(
                    channel=channel, user=self._user
                )
            else:
                snapshot["now_channel_today_seconds"] = 0
            return snapshot
        except TwitchWatchtimeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TwitchWatchtimeConnectionError as err:
            raise UpdateFailed(str(err)) from err
