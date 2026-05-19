"""Tests for TwitchWatchtimeCoordinator."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.twitch_watchtime.api import (
    TwitchWatchtimeAuthError,
    TwitchWatchtimeConnectionError,
)
from custom_components.twitch_watchtime.coordinator import TwitchWatchtimeCoordinator


SNAPSHOT = {
    "today_seconds": 1800,
    "week_seconds": 7200,
    "month_seconds": 28800,
    "all_seconds": 360000,
    "top_channel": "cinna",
    "top_channel_seconds": 1200,
    "top_channel_week": "cinna",
    "top_channel_week_seconds": 5000,
    "top_channel_month": "cinna",
    "top_channel_month_seconds": 20000,
    "top_channel_all": "cinna",
    "top_channel_all_seconds": 280000,
    "now": {
        "ts": 1700000000,
        "channel": "cinna",
        "category": "Just Chatting",
        "title": "test stream",
        "twitch_user": "jwsoat",
    },
    "top_category_today": "Just Chatting",
    "top_category_today_seconds": 900,
    "top_category_week": "Just Chatting",
    "top_category_week_seconds": 4500,
    "top_category_month": "Just Chatting",
    "top_category_month_seconds": 18000,
    "top_category_all": "League of Legends",
    "top_category_all_seconds": 200000,
}


def _mock_client(snapshot=None, raises=None, channel_seconds=600):
    client = AsyncMock()
    if raises is not None:
        client.async_fetch_snapshot.side_effect = raises
    else:
        client.async_fetch_snapshot.return_value = snapshot or SNAPSHOT
    client.async_get_channel_today.return_value = channel_seconds
    return client


async def test_coordinator_returns_snapshot_on_success(hass: HomeAssistant) -> None:
    client = _mock_client()
    coord = TwitchWatchtimeCoordinator(
        hass, client=client, user="jwsoat", scan_interval=timedelta(seconds=60)
    )
    data = await coord._async_update_data()
    assert data["today_seconds"] == SNAPSHOT["today_seconds"]
    assert data["top_channel_week"] == SNAPSHOT["top_channel_week"]
    assert data["top_channel_all"] == SNAPSHOT["top_channel_all"]
    client.async_fetch_snapshot.assert_awaited_once_with(user="jwsoat")


async def test_coordinator_passes_none_for_all_accounts(hass: HomeAssistant) -> None:
    client = _mock_client()
    coord = TwitchWatchtimeCoordinator(
        hass, client=client, user=None, scan_interval=timedelta(seconds=60)
    )
    data = await coord._async_update_data()
    client.async_fetch_snapshot.assert_awaited_once_with(user=None)
    # all-accounts entry also fetches per-channel data for the active channel
    assert data["now_channel_today_seconds"] == 600
    assert data["now_channel_month_seconds"] == 600
    client.async_get_channel_today.assert_awaited()


async def test_coordinator_raises_auth_failed_on_401(hass: HomeAssistant) -> None:
    client = _mock_client(raises=TwitchWatchtimeAuthError("401"))
    coord = TwitchWatchtimeCoordinator(
        hass, client=client, user="jwsoat", scan_interval=timedelta(seconds=60)
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_coordinator_raises_update_failed_on_connection_error(hass: HomeAssistant) -> None:
    client = _mock_client(raises=TwitchWatchtimeConnectionError("timeout"))
    coord = TwitchWatchtimeCoordinator(
        hass, client=client, user="jwsoat", scan_interval=timedelta(seconds=60)
    )
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
