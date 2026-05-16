"""DataUpdateCoordinator for the twitch_watchtime integration."""
from __future__ import annotations

import asyncio
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
    TwitchWatchtimeError,
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
            if self._user is not None:
                now = snapshot.get("now")
                channel = now.get("channel") if now else None
                windows = (
                    ("now_channel_today_seconds", "today"),
                    ("now_channel_week_seconds", "week"),
                    ("now_channel_month_seconds", "month"),
                    ("now_channel_all_seconds", "all"),
                )
                if channel:
                    results = await asyncio.gather(
                        *(
                            self._client.async_get_channel_today(
                                channel=channel, user=self._user, window=window
                            )
                            for _, window in windows
                        ),
                        return_exceptions=True,
                    )
                    for (key, _), result in zip(windows, results):
                        snapshot[key] = 0 if isinstance(result, BaseException) else result
                else:
                    for key, _ in windows:
                        snapshot[key] = 0
            return snapshot
        except TwitchWatchtimeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TwitchWatchtimeConnectionError as err:
            raise UpdateFailed(str(err)) from err
