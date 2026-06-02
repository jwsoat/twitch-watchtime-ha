"""Tests for the twitch_watchtime integration setup."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.twitch_watchtime import async_setup_entry
from custom_components.twitch_watchtime.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORM_TWITCH,
    USER_ALL,
)


async def test_coordinator_created_with_platform_parameter(hass: HomeAssistant) -> None:
    """Test that WatchtimeCoordinator receives platform parameter."""
    config_entry = hass.config_entries.async_create_entry(
        domain=DOMAIN,
        title="Twitch - testuser",
        data={
            CONF_HOST: "http://localhost:8765",
            CONF_API_KEY: "test_key",
            CONF_PLATFORM: PLATFORM_TWITCH,
            CONF_USER: "testuser",
        },
    )

    with patch("custom_components.twitch_watchtime.TwitchWatchtimeClient"):
        with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            mock_instance.last_update_success = True
            mock_coordinator.return_value = mock_instance

            result = await async_setup_entry(hass, config_entry)

            # Verify coordinator was created with platform
            mock_coordinator.assert_called_once()
            call_kwargs = mock_coordinator.call_args[1]
            assert call_kwargs["platform"] == PLATFORM_TWITCH
            assert call_kwargs["user"] == "testuser"
            assert result is True


async def test_coordinator_created_with_youtube_platform(hass: HomeAssistant) -> None:
    """Test that coordinator passes youtube platform to coordinator."""
    config_entry = hass.config_entries.async_create_entry(
        domain=DOMAIN,
        title="YouTube - testaccount",
        data={
            CONF_HOST: "http://localhost:8765",
            CONF_API_KEY: "test_key",
            CONF_PLATFORM: "youtube",
            CONF_USER: "testaccount",
        },
    )

    with patch("custom_components.twitch_watchtime.TwitchWatchtimeClient"):
        with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            mock_instance.last_update_success = True
            mock_coordinator.return_value = mock_instance

            await async_setup_entry(hass, config_entry)

            # Platform should be passed to coordinator
            assert mock_coordinator.call_args[1]["platform"] == "youtube"
            assert mock_coordinator.call_args[1]["user"] == "testaccount"


async def test_device_registered_with_platform_identifier(hass: HomeAssistant) -> None:
    """Test that device is registered with platform-user identifier."""
    config_entry = hass.config_entries.async_create_entry(
        domain=DOMAIN,
        title="Twitch - jwsoat",
        data={
            CONF_HOST: "http://localhost:8765",
            CONF_API_KEY: "test_key",
            CONF_PLATFORM: PLATFORM_TWITCH,
            CONF_USER: "jwsoat",
        },
    )

    with patch("custom_components.twitch_watchtime.TwitchWatchtimeClient"):
        with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coordinator:
            mock_instance = AsyncMock()
            mock_instance.last_update_success = True
            mock_coordinator.return_value = mock_instance

            await async_setup_entry(hass, config_entry)

            # Verify device was registered with platform-aware identifier
            from homeassistant.helpers import device_registry as dr
            device_registry = dr.async_get(hass)
            devices = list(device_registry.devices.values())
            assert len(devices) > 0
            device = devices[0]
            assert (DOMAIN, f"{PLATFORM_TWITCH}_jwsoat") in device.identifiers
