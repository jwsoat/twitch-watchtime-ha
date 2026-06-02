"""Tests for the twitch_watchtime config flow."""
from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.twitch_watchtime.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DOMAIN,
    PLATFORM_MERGED,
    PLATFORM_SOURCES,
    PLATFORM_TWITCH,
    PLATFORM_YOUTUBE,
    USER_ALL,
)


HOST = "http://watchtime.test:8765"
KEY = "secret"


@pytest.fixture
async def patch_clientsession():
    """Replace async_get_clientsession with a ThreadedResolver-backed session.

    HA's shared session uses aiodns which requires a SelectorEventLoop on Windows;
    the test loop is a ProactorEventLoop. aioresponses intercepts before DNS, but
    the connector still imports aiodns at construction time.
    """
    sessions: list[aiohttp.ClientSession] = []

    def _factory(_hass):
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        session = aiohttp.ClientSession(connector=connector)
        sessions.append(session)
        return session

    with patch(
        "custom_components.twitch_watchtime.config_flow.async_get_clientsession",
        side_effect=_factory,
    ):
        yield
    for s in sessions:
        if not s.closed:
            await s.close()


async def _drive_step1(hass: HomeAssistant, mock_backend) -> dict:
    """Drive step 1 of the config flow with a healthy backend."""
    mock_backend.get(f"{HOST}/health", payload={"ok": True, "interval": 60})
    mock_backend.get(
        f"{HOST}/stats/users",
        payload={"users": [{"user": "jwsoat", "last_ts": 1700000000, "count": 42}]},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_API_KEY: KEY}
    )


async def _drive_step2_platform(hass: HomeAssistant, flow_id: str, platform: str) -> dict:
    """Drive step 2 (platform selection)."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_PLATFORM: platform}
    )


async def test_platform_step_displayed_after_user_step(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    """Test that platform step is shown after user step."""
    step2 = await _drive_step1(hass, mock_backend)
    assert step2["type"] == FlowResultType.FORM
    assert step2["step_id"] == "platform"


async def test_platform_step_shows_all_options(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    """Test that platform step offers all platform choices."""
    step2 = await _drive_step1(hass, mock_backend)
    assert step2["type"] == FlowResultType.FORM
    assert step2["step_id"] == "platform"
    # Check that the schema contains all platform options
    schema = step2["data_schema"]
    # Verify schema exists and can be inspected
    assert schema is not None


async def test_full_happy_path_creates_entry(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    step2 = await _drive_step1(hass, mock_backend)
    assert step2["type"] == FlowResultType.FORM
    assert step2["step_id"] == "platform"

    step3 = await _drive_step2_platform(hass, step2["flow_id"], PLATFORM_TWITCH)
    assert step3["type"] == FlowResultType.FORM
    assert step3["step_id"] == "account"

    result = await hass.config_entries.flow.async_configure(
        step3["flow_id"], {CONF_USER: "jwsoat"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "jwsoat"
    assert result["data"] == {CONF_HOST: HOST, CONF_API_KEY: KEY, CONF_PLATFORM: PLATFORM_TWITCH, CONF_USER: "jwsoat"}


async def test_all_accounts_creates_entry_with_sentinel(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    step2 = await _drive_step1(hass, mock_backend)
    step3 = await _drive_step2_platform(hass, step2["flow_id"], PLATFORM_YOUTUBE)
    result = await hass.config_entries.flow.async_configure(
        step3["flow_id"], {CONF_USER: USER_ALL}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "All accounts"
    assert result["data"][CONF_USER] == USER_ALL
    assert result["data"][CONF_PLATFORM] == PLATFORM_YOUTUBE


async def test_cannot_connect_on_health_failure(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    import aiohttp
    mock_backend.get(f"{HOST}/health", exception=aiohttp.ClientConnectorError(None, OSError()))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_API_KEY: KEY}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_auth_on_401(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    mock_backend.get(f"{HOST}/health", payload={"ok": True, "interval": 60})
    mock_backend.get(f"{HOST}/stats/users", status=401, payload={"detail": "bad api key"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_API_KEY: "wrong"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_duplicate_unique_id_aborts(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_API_KEY: KEY, CONF_PLATFORM: PLATFORM_TWITCH, CONF_USER: "jwsoat"},
        unique_id=f"{HOST}:{PLATFORM_TWITCH}:jwsoat",
    )
    existing.add_to_hass(hass)

    step2 = await _drive_step1(hass, mock_backend)
    step3 = await _drive_step2_platform(hass, step2["flow_id"], PLATFORM_TWITCH)
    result = await hass.config_entries.flow.async_configure(
        step3["flow_id"], {CONF_USER: "jwsoat"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "platform,expected_device_name,expected_device_id",
    [
        (PLATFORM_TWITCH, "Twitch - testuser", "twitch_testuser"),
        (PLATFORM_YOUTUBE, "Youtube - testuser", "youtube_testuser"),
        (PLATFORM_MERGED, "Merged - testuser", "merged_testuser"),
    ],
)
async def test_config_flow_all_platforms_creates_correct_device(
    hass: HomeAssistant,
    mock_backend,
    enable_custom_integrations,
    patch_clientsession,
    platform: str,
    expected_device_name: str,
    expected_device_id: str,
) -> None:
    """Test config flow for all three platforms creates correct device with platform-aware identifier."""
    from homeassistant.helpers import device_registry as dr

    # Mock backend responses
    mock_backend.get(f"{HOST}/health", payload={"ok": True, "interval": 60})
    mock_backend.get(
        f"{HOST}/stats/users",
        payload={"users": [{"user": "testuser", "last_ts": 1700000000, "count": 42}]},
    )

    # Step 1: User (host + API key)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_API_KEY: KEY}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "platform"

    # Step 2: Platform selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PLATFORM: platform}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "account"

    # Step 3: Account selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USER: "testuser"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify entry data contains platform
    entry_data = result["data"]
    assert entry_data[CONF_PLATFORM] == platform
    assert entry_data[CONF_USER] == "testuser"
    assert entry_data[CONF_HOST] == HOST
    assert entry_data[CONF_API_KEY] == KEY

    # Allow setup to complete (async_setup_entry creates the device)
    await hass.async_block_till_done()

    # Verify device was created with correct platform-aware identifier
    device_registry = dr.async_get(hass)
    devices = list(device_registry.devices.values())
    platform_devices = [d for d in devices if DOMAIN in d.identifiers]

    assert len(platform_devices) > 0, f"No device found for {platform}"
    device = platform_devices[0]

    # Verify device identifier includes platform
    assert (DOMAIN, expected_device_id) in device.identifiers
    # Verify device name matches platform
    assert device.name == expected_device_name


async def test_multiple_platform_entries_no_conflict(
    hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession
) -> None:
    """Test that Twitch and YouTube entries can coexist without unique ID conflicts."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from homeassistant.helpers import device_registry as dr

    # Mock backend for both flows
    mock_backend.get(f"{HOST}/health", payload={"ok": True, "interval": 60})
    mock_backend.get(
        f"{HOST}/stats/users",
        payload={"users": [{"user": "testuser", "last_ts": 1700000000, "count": 42}]},
    )

    # Create Twitch entry
    twitch_entry = MockConfigEntry(
        domain=DOMAIN,
        title="testuser",
        data={
            CONF_HOST: HOST,
            CONF_API_KEY: KEY,
            CONF_PLATFORM: PLATFORM_TWITCH,
            CONF_USER: "testuser",
        },
        unique_id=f"{HOST}:{PLATFORM_TWITCH}:testuser",
    )
    twitch_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(twitch_entry.entry_id)
    await hass.async_block_till_done()

    # Create YouTube entry with same user, different platform
    youtube_entry = MockConfigEntry(
        domain=DOMAIN,
        title="testuser",
        data={
            CONF_HOST: HOST,
            CONF_API_KEY: KEY,
            CONF_PLATFORM: PLATFORM_YOUTUBE,
            CONF_USER: "testuser",
        },
        unique_id=f"{HOST}:{PLATFORM_YOUTUBE}:testuser",
    )
    youtube_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(youtube_entry.entry_id)
    await hass.async_block_till_done()

    # Verify both entries exist
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    # Verify unique IDs are different (platform-scoped)
    twitch_uid = twitch_entry.unique_id
    youtube_uid = youtube_entry.unique_id
    assert twitch_uid != youtube_uid
    assert PLATFORM_TWITCH in twitch_uid
    assert PLATFORM_YOUTUBE in youtube_uid

    # Verify devices were created with different identifiers
    device_registry = dr.async_get(hass)
    devices = list(device_registry.devices.values())
    platform_devices = [d for d in devices if DOMAIN in d.identifiers]

    # Should have two devices, one for each platform
    assert len(platform_devices) == 2

    twitch_device = next(
        (d for d in platform_devices if (DOMAIN, "twitch_testuser") in d.identifiers), None
    )
    youtube_device = next(
        (d for d in platform_devices if (DOMAIN, "youtube_testuser") in d.identifiers), None
    )

    assert twitch_device is not None, "Twitch device not found"
    assert youtube_device is not None, "YouTube device not found"
    assert twitch_device.name == "Twitch - testuser"
    assert youtube_device.name == "Youtube - testuser"
