"""Tests for TwitchWatchtimeClient."""
from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.twitch_watchtime.api import (
    TwitchWatchtimeAuthError,
    TwitchWatchtimeClient,
    TwitchWatchtimeConnectionError,
)


HOST = "http://watchtime.test:8765"
KEY = "secret"

async def _make_client() -> tuple[TwitchWatchtimeClient, aiohttp.ClientSession]:
    # Use ThreadedResolver to avoid aiodns (which requires SelectorEventLoop on Windows).
    # aioresponses intercepts before any DNS happens anyway.
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    session = aiohttp.ClientSession(connector=connector)
    return TwitchWatchtimeClient(host=HOST, api_key=KEY, session=session), session


async def test_health_returns_true_on_200() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/health", payload={"ok": True, "interval": 60})
            assert await client.async_check_health() is True
    finally:
        await session.close()


async def test_health_raises_connection_error_on_network_failure() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/health", exception=aiohttp.ClientConnectorError(None, OSError()))
            with pytest.raises(TwitchWatchtimeConnectionError):
                await client.async_check_health()
    finally:
        await session.close()


async def test_get_users_returns_list() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(
                f"{HOST}/stats/users",
                payload={"users": [
                    {"user": "jwsoat", "last_ts": 1700000000, "count": 42},
                    {"user": "anonymous", "last_ts": 1699999000, "count": 5},
                ]},
            )
            users = await client.async_get_users()
            assert users == [
                {"user": "jwsoat", "last_ts": 1700000000, "count": 42},
                {"user": "anonymous", "last_ts": 1699999000, "count": 5},
            ]
    finally:
        await session.close()


async def test_get_users_raises_auth_error_on_401() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/stats/users", status=401, payload={"detail": "bad api key"})
            with pytest.raises(TwitchWatchtimeAuthError):
                await client.async_get_users()
    finally:
        await session.close()


async def test_fetch_snapshot_merges_five_endpoints() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/stats/total?window=today", payload={"window": "today", "seconds": 1800})
            m.get(f"{HOST}/stats/total?window=week", payload={"window": "week", "seconds": 7200})
            m.get(f"{HOST}/stats/total?window=all", payload={"window": "all", "seconds": 360000})
            m.get(f"{HOST}/stats/top_channel?window=today", payload={"channel": "cinna", "seconds": 1200})
            m.get(f"{HOST}/stats/now", payload={
                "ts": 1700000000, "channel": "cinna", "category": "Just Chatting",
                "title": "stream title", "twitch_user": None,
            })
            m.get(f"{HOST}/stats/categories?window=today", payload={"categories": [
                {"category": "Just Chatting", "seconds": 900},
            ]})
            m.get(f"{HOST}/stats/categories?window=week", payload={"categories": [
                {"category": "Just Chatting", "seconds": 4500},
            ]})
            m.get(f"{HOST}/stats/categories?window=all", payload={"categories": [
                {"category": "League of Legends", "seconds": 200000},
            ]})
            snap = await client.async_fetch_snapshot(user=None)
            assert snap == {
                "today_seconds": 1800,
                "week_seconds": 7200,
                "all_seconds": 360000,
                "top_channel": "cinna",
                "top_channel_seconds": 1200,
                "now": {
                    "ts": 1700000000, "channel": "cinna", "category": "Just Chatting",
                    "title": "stream title", "twitch_user": None,
                },
                "top_category_today": "Just Chatting",
                "top_category_today_seconds": 900,
                "top_category_week": "Just Chatting",
                "top_category_week_seconds": 4500,
                "top_category_all": "League of Legends",
                "top_category_all_seconds": 200000,
            }
    finally:
        await session.close()


async def test_fetch_snapshot_passes_user_param_when_set() -> None:
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/stats/total?window=today&user=jwsoat", payload={"window": "today", "seconds": 60})
            m.get(f"{HOST}/stats/total?window=week&user=jwsoat", payload={"window": "week", "seconds": 60})
            m.get(f"{HOST}/stats/total?window=all&user=jwsoat", payload={"window": "all", "seconds": 60})
            m.get(f"{HOST}/stats/top_channel?window=today&user=jwsoat", payload={"channel": None, "seconds": 0})
            m.get(f"{HOST}/stats/now?user=jwsoat", payload={"now": None})
            m.get(f"{HOST}/stats/categories?window=today&user=jwsoat", payload={"categories": []})
            m.get(f"{HOST}/stats/categories?window=week&user=jwsoat", payload={"categories": []})
            m.get(f"{HOST}/stats/categories?window=all&user=jwsoat", payload={"categories": []})
            snap = await client.async_fetch_snapshot(user="jwsoat")
            assert snap["today_seconds"] == 60
            assert snap["top_channel"] is None
            assert snap["now"] is None
            assert snap["top_category_today"] is None
            assert snap["top_category_today_seconds"] == 0
    finally:
        await session.close()


async def test_fetch_snapshot_normalizes_stats_now_null_shape() -> None:
    """/stats/now returns {now: null} when idle — the client should normalize to a single None."""
    client, session = await _make_client()
    try:
        with aioresponses() as m:
            m.get(f"{HOST}/stats/total?window=today", payload={"window": "today", "seconds": 0})
            m.get(f"{HOST}/stats/total?window=week", payload={"window": "week", "seconds": 0})
            m.get(f"{HOST}/stats/total?window=all", payload={"window": "all", "seconds": 0})
            m.get(f"{HOST}/stats/top_channel?window=today", payload={"channel": None, "seconds": 0})
            m.get(f"{HOST}/stats/now", payload={"now": None})
            m.get(f"{HOST}/stats/categories?window=today", payload={"categories": []})
            m.get(f"{HOST}/stats/categories?window=week", payload={"categories": []})
            m.get(f"{HOST}/stats/categories?window=all", payload={"categories": []})
            snap = await client.async_fetch_snapshot(user=None)
            assert snap["now"] is None
    finally:
        await session.close()
