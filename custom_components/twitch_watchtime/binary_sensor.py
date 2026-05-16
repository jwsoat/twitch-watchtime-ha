"""Binary sensor platform for twitch_watchtime."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TwitchWatchtimeCoordinator
from .sensor import _device_info  # reuse the helper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TwitchWatchtimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WatchtimeActiveBinarySensor(coordinator, entry)])


class WatchtimeActiveBinarySensor(
    CoordinatorEntity[TwitchWatchtimeCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True
    _attr_name = "Watchtime active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:circle-medium"

    def __init__(self, coordinator: TwitchWatchtimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("now") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = self.coordinator.data.get("now") or {}
        return {
            "channel": now.get("channel"),
            "category": now.get("category"),
            "title": now.get("title"),
        }
