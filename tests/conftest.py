"""Shared pytest fixtures for the twitch_watchtime integration."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_socket
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant

from custom_components.twitch_watchtime.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_USER,
    DOMAIN,
)


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """Re-enable sockets before each fixture sets up.

    aioresponses intercepts real HTTP, but on Windows asyncio's ProactorEventLoop
    creates a self-pipe via socket.socketpair() during loop construction, and
    aiohttp's TCPConnector init also touches socket internals. The HA pytest
    plugin disables sockets in its pytest_runtest_setup hook. We re-enable just
    before each fixture runs so the asyncio/aiohttp plumbing works.
    """
    pytest_socket.enable_socket()
    yield

TEST_HOST = "http://watchtime.test:8765"
TEST_API_KEY = "test-key"
TEST_USER = "jwsoat"


@pytest.fixture
def enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in HA's test harness."""
    yield enable_custom_integrations


@pytest.fixture
def mock_backend() -> AsyncGenerator[aioresponses, None]:
    """Intercept aiohttp calls to the backend."""
    with aioresponses() as m:
        yield m


@pytest.fixture
def config_entry_data() -> dict:
    """Default config entry data."""
    return {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
        CONF_USER: TEST_USER,
    }
