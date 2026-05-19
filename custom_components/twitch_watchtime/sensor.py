"""Sensor platform for twitch_watchtime."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HOST,
    CONF_USER,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    USER_ALL,
)
from .coordinator import TwitchWatchtimeCoordinator


def _fmt_duration(seconds: int) -> str:
    if not seconds:
        return "0 seconds"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)

    def p(n: int, w: str) -> str:
        return f"{n} {w}{'s' if n != 1 else ''}"

    if h > 0:
        return p(h, "hour") if m == 0 else f"{p(h, 'hour')} {p(m, 'minute')}"
    if m > 0:
        return p(m, "minute") if s == 0 else f"{p(m, 'minute')} {p(s, 'second')}"
    return p(s, "second")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TwitchWatchtimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [
        WatchtimeDurationSensor(coordinator, entry, "today", "Watchtime today"),
        WatchtimeDurationSensor(coordinator, entry, "week", "Watchtime last 7 days"),
        WatchtimeDurationSensor(coordinator, entry, "month", "Watchtime last 30 days"),
        WatchtimeDurationSensor(coordinator, entry, "all", "Watchtime all"),
        WatchtimeNowWatchingSensor(coordinator, entry),
        WatchtimeNowCategorySensor(coordinator, entry),
        WatchtimeTopChannelSensor(coordinator, entry, "today", "Top Channel Daily"),
        WatchtimeTopChannelSensor(coordinator, entry, "week", "Top Channel Last 7 Days"),
        WatchtimeTopChannelSensor(coordinator, entry, "month", "Top Channel Last 30 Days"),
        WatchtimeTopChannelSensor(coordinator, entry, "all", "Top Channel All Time"),
        WatchtimeTopCategorySensor(coordinator, entry, "today", "Watchtime top category today"),
        WatchtimeTopCategorySensor(coordinator, entry, "week", "Watchtime top category last 7 days"),
        WatchtimeTopCategorySensor(coordinator, entry, "month", "Watchtime top category last 30 days"),
        WatchtimeTopCategorySensor(coordinator, entry, "all", "Watchtime top category all"),
    ]
    entities += [
        WatchtimeCurrentChannelTodaySensor(coordinator, entry),
        WatchtimeCurrentChannelWindowSensor(coordinator, entry, "week", "now_channel_week_seconds", "Watchtime current channel last 7 days"),
        WatchtimeCurrentChannelWindowSensor(coordinator, entry, "month", "now_channel_month_seconds", "Watchtime current channel last 30 days"),
        WatchtimeCurrentChannelWindowSensor(coordinator, entry, "all", "now_channel_all_seconds", "Watchtime current channel all time"),
    ]
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    user = entry.data[CONF_USER]
    name = "All accounts" if user == USER_ALL else user
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=entry.data[CONF_HOST],
    )


class _BaseWatchtimeEntity(CoordinatorEntity[TwitchWatchtimeCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TwitchWatchtimeCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)


class WatchtimeDurationSensor(_BaseWatchtimeEntity, SensorEntity):
    """today / week / all duration sensors."""

    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        coordinator: TwitchWatchtimeCoordinator,
        entry: ConfigEntry,
        window: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, entry, window, name)
        self._window = window

    def _seconds(self) -> int:
        return int(self.coordinator.data.get(f"{self._window}_seconds", 0))

    @property
    def native_value(self) -> str:
        return _fmt_duration(self._seconds())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        seconds = self._seconds()
        attrs: dict[str, Any] = {"seconds": seconds}
        if self._window == "today":
            attrs["top_channel"] = data.get("top_channel")
            attrs["top_channel_seconds"] = data.get("top_channel_seconds", 0)
        return attrs


class WatchtimeNowWatchingSensor(_BaseWatchtimeEntity, SensorEntity):
    """Current channel name or 'idle'."""

    _attr_icon = "mdi:television-play"

    def __init__(self, coordinator: TwitchWatchtimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "now_watching", "Watchtime now watching")

    @property
    def native_value(self) -> str:
        now = self.coordinator.data.get("now")
        if not now:
            return "idle"
        return now.get("channel") or "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = self.coordinator.data.get("now") or {}
        return {
            "category": now.get("category"),
            "title": now.get("title"),
            "started_at": now.get("ts"),
            "twitch_user": now.get("twitch_user"),
        }


class WatchtimeNowCategorySensor(_BaseWatchtimeEntity, SensorEntity):
    """Current category name or 'idle'."""

    _attr_icon = "mdi:shape"

    def __init__(self, coordinator: TwitchWatchtimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "now_category", "Watchtime now category")

    @property
    def native_value(self) -> str:
        now = self.coordinator.data.get("now")
        if not now:
            return "idle"
        return now.get("category") or "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = self.coordinator.data.get("now") or {}
        return {
            "channel": now.get("channel"),
            "title": now.get("title"),
            "started_at": now.get("ts"),
            "twitch_user": now.get("twitch_user"),
        }


class WatchtimeCurrentChannelTodaySensor(_BaseWatchtimeEntity, SensorEntity):
    """Time watched today for the currently active channel."""

    _attr_icon = "mdi:timer-play-outline"

    def __init__(self, coordinator: TwitchWatchtimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "now_channel_today", "Watchtime current channel today")

    @property
    def native_value(self) -> str:
        seconds = int(self.coordinator.data.get("now_channel_today_seconds", 0))
        return _fmt_duration(seconds)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        now = data.get("now") or {}
        seconds = int(data.get("now_channel_today_seconds", 0))
        return {"channel": now.get("channel"), "seconds": seconds}


class WatchtimeCurrentChannelWindowSensor(_BaseWatchtimeEntity, SensorEntity):
    """Time watched in a window for the currently active channel."""

    _attr_icon = "mdi:timer-play-outline"

    def __init__(
        self,
        coordinator: TwitchWatchtimeCoordinator,
        entry: ConfigEntry,
        window: str,
        data_key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, entry, f"now_channel_{window}", name)
        self._data_key = data_key

    @property
    def native_value(self) -> str:
        seconds = int(self.coordinator.data.get(self._data_key, 0))
        return _fmt_duration(seconds)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        now = data.get("now") or {}
        seconds = int(data.get(self._data_key, 0))
        return {"channel": now.get("channel"), "seconds": seconds}


class WatchtimeTopChannelSensor(_BaseWatchtimeEntity, SensorEntity):
    """Top channel for a window (today / week / all)."""

    _attr_icon = "mdi:crown"

    def __init__(
        self,
        coordinator: TwitchWatchtimeCoordinator,
        entry: ConfigEntry,
        window: str,
        name: str,
    ) -> None:
        # today keeps the legacy key so existing entity IDs are preserved
        key = "top_channel" if window == "today" else f"top_channel_{window}"
        super().__init__(coordinator, entry, key, name)
        self._channel_key = key
        self._seconds_key = "top_channel_seconds" if window == "today" else f"top_channel_{window}_seconds"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get(self._channel_key) or "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        seconds = int(self.coordinator.data.get(self._seconds_key, 0))
        return {"seconds": seconds, "formatted": _fmt_duration(seconds)}


class WatchtimeTopCategorySensor(_BaseWatchtimeEntity, SensorEntity):
    """Top category for a window (today / week / all)."""

    _attr_icon = "mdi:shape"

    def __init__(
        self,
        coordinator: TwitchWatchtimeCoordinator,
        entry: ConfigEntry,
        window: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, entry, f"top_category_{window}", name)
        self._window = window

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get(f"top_category_{self._window}") or "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        seconds = int(self.coordinator.data.get(f"top_category_{self._window}_seconds", 0))
        return {"seconds": seconds, "formatted": _fmt_duration(seconds)}
