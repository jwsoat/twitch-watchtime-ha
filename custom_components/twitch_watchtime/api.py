"""HTTP client for the twitch-watchtime FastAPI backend.

The only module in this integration that talks to the network. Accepts an
aiohttp ClientSession so it's testable with aioresponses and reusable with
HA's shared session in production.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


def _normalize_host(host: str) -> str:
    """Accept "1.2.3.4:8765", "http://...", or "https://..." and return a usable base URL."""
    h = host.strip().rstrip("/")
    if not h.startswith(("http://", "https://")):
        h = f"http://{h}"
    return h


class TwitchWatchtimeError(Exception):
    """Base error for the client."""


class TwitchWatchtimeConnectionError(TwitchWatchtimeError):
    """Connection refused, DNS failure, timeout, etc."""


class TwitchWatchtimeAuthError(TwitchWatchtimeError):
    """Backend rejected the API key (401/403)."""


class TwitchWatchtimeClient:
    """Thin async client around the watchtime backend."""

    def __init__(
        self,
        *,
        host: str,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = _normalize_host(host)
        self._headers = {"X-API-Key": api_key}
        self._session = session

    async def _get(self, path: str, params: dict[str, str] | None = None, *, auth: bool = True) -> Any:
        url = f"{self._host}{path}"
        headers = self._headers if auth else {}
        try:
            async with self._session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as res:
                if res.status in (401, 403):
                    raise TwitchWatchtimeAuthError(f"{res.status} on {path}")
                res.raise_for_status()
                return await res.json()
        except (aiohttp.ClientConnectorError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
            # Defensive: aiohttp's ClientConnectorError.__str__ can itself raise if
            # the connection_key is malformed (seen in test fixtures). Fall back to
            # the type name in that case so we always raise our own exception type.
            try:
                detail = str(err) or err.__class__.__name__
            except Exception:  # noqa: BLE001
                detail = err.__class__.__name__
            raise TwitchWatchtimeConnectionError(detail) from err
        except aiohttp.ClientResponseError as err:
            raise TwitchWatchtimeConnectionError(f"HTTP {err.status}") from err

    async def async_check_health(self) -> bool:
        """Hit /health (no auth)."""
        data = await self._get("/health", auth=False)
        return bool(data.get("ok"))

    async def async_get_users(self) -> list[dict[str, Any]]:
        """Return the list of distinct twitch_user values (powers the picker)."""
        data = await self._get("/stats/users")
        return list(data.get("users", []))

    async def async_get_channel_today(self, *, channel: str, user: str | None, window: str = "today") -> int:
        """Return seconds watched for channel in the given window."""
        params: dict[str, str] = {"channel": channel, "window": window}
        if user:
            params["user"] = user
        data = await self._get("/stats/channel", params=params)
        return int(data.get("seconds", 0))

    async def async_get_top_category(self, *, window: str, user: str | None) -> dict[str, Any]:
        """Return the #1 category for the window, or {'category': None, 'seconds': 0}."""
        params: dict[str, str] = {"window": window}
        if user:
            params["user"] = user
        data = await self._get("/stats/categories", params=params)
        cats = data.get("categories") or []
        if not cats:
            return {"category": None, "seconds": 0}
        top = cats[0]
        return {"category": top.get("category"), "seconds": int(top.get("seconds", 0))}

    async def async_fetch_snapshot(self, *, user: str | None) -> dict[str, Any]:
        """Run the five tick calls in parallel and merge into a coordinator-shaped dict.

        Passing user=None pools all accounts; any other value is sent as ?user=<value>.
        """
        params_user = {"user": user} if user else None
        params_today = {"window": "today", **(params_user or {})}
        params_week = {"window": "week", **(params_user or {})}
        params_month = {"window": "month", **(params_user or {})}
        params_all = {"window": "all", **(params_user or {})}

        (
            today, top_today, top_week, top_month, top_all,
            week, month, all_time, now,
            cat_today, cat_week, cat_month, cat_all,
        ) = await asyncio.gather(
            self._get("/stats/total", params=params_today),
            self._get("/stats/top_channel", params=params_today),
            self._get("/stats/top_channel", params=params_week),
            self._get("/stats/top_channel", params=params_month),
            self._get("/stats/top_channel", params=params_all),
            self._get("/stats/total", params=params_week),
            self._get("/stats/total", params=params_month),
            self._get("/stats/total", params=params_all),
            self._get("/stats/now", params=params_user),
            self._get("/stats/categories", params=params_today),
            self._get("/stats/categories", params=params_week),
            self._get("/stats/categories", params=params_month),
            self._get("/stats/categories", params=params_all),
        )

        # /stats/now returns either {"now": None} or {"ts": ..., "channel": ..., ...}
        now_value: dict[str, Any] | None
        if isinstance(now, dict) and "now" in now and now["now"] is None:
            now_value = None
        else:
            now_value = now

        def _pick_top_cat(data: Any) -> tuple[str | None, int]:
            cats = (data or {}).get("categories") or []
            if not cats:
                return None, 0
            first = cats[0]
            return first.get("category"), int(first.get("seconds", 0))

        tc_today_name, tc_today_sec = _pick_top_cat(cat_today)
        tc_week_name, tc_week_sec = _pick_top_cat(cat_week)
        tc_month_name, tc_month_sec = _pick_top_cat(cat_month)
        tc_all_name, tc_all_sec = _pick_top_cat(cat_all)

        return {
            "today_seconds": int(today.get("seconds", 0)),
            "week_seconds": int(week.get("seconds", 0)),
            "month_seconds": int(month.get("seconds", 0)),
            "all_seconds": int(all_time.get("seconds", 0)),
            "top_channel": top_today.get("channel"),
            "top_channel_seconds": int(top_today.get("seconds", 0)),
            "top_channel_week": top_week.get("channel"),
            "top_channel_week_seconds": int(top_week.get("seconds", 0)),
            "top_channel_month": top_month.get("channel"),
            "top_channel_month_seconds": int(top_month.get("seconds", 0)),
            "top_channel_all": top_all.get("channel"),
            "top_channel_all_seconds": int(top_all.get("seconds", 0)),
            "now": now_value,
            "top_category_today": tc_today_name,
            "top_category_today_seconds": tc_today_sec,
            "top_category_week": tc_week_name,
            "top_category_week_seconds": tc_week_sec,
            "top_category_month": tc_month_name,
            "top_category_month_seconds": tc_month_sec,
            "top_category_all": tc_all_name,
            "top_category_all_seconds": tc_all_sec,
        }
