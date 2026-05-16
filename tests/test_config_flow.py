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
    CONF_USER,
    DOMAIN,
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


async def test_full_happy_path_creates_entry(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    step2 = await _drive_step1(hass, mock_backend)
    assert step2["type"] == FlowResultType.FORM
    assert step2["step_id"] == "account"

    result = await hass.config_entries.flow.async_configure(
        step2["flow_id"], {CONF_USER: "jwsoat"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "jwsoat"
    assert result["data"] == {CONF_HOST: HOST, CONF_API_KEY: KEY, CONF_USER: "jwsoat"}


async def test_all_accounts_creates_entry_with_sentinel(hass: HomeAssistant, mock_backend, enable_custom_integrations, patch_clientsession) -> None:
    step2 = await _drive_step1(hass, mock_backend)
    result = await hass.config_entries.flow.async_configure(
        step2["flow_id"], {CONF_USER: USER_ALL}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "All accounts"
    assert result["data"][CONF_USER] == USER_ALL


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
        data={CONF_HOST: HOST, CONF_API_KEY: KEY, CONF_USER: "jwsoat"},
        unique_id=f"{HOST}:jwsoat",
    )
    existing.add_to_hass(hass)

    step2 = await _drive_step1(hass, mock_backend)
    result = await hass.config_entries.flow.async_configure(
        step2["flow_id"], {CONF_USER: "jwsoat"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
