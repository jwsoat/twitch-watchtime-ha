# Multi-Platform Watchtime Integration Design

**Date:** 2026-06-03  
**Status:** Approved

## Overview

Extend the Twitch watchtime Home Assistant integration to support YouTube and merged (combined Twitch + YouTube) watchtime sensors. The backend already provides YouTube endpoints matching Twitch structure and merged data endpoints. The HA integration needs to support platform selection and display separate devices per platform + account combination.

## Goals

1. Support Twitch, YouTube, and merged watchtime data via single integration entry
2. Create separate HA devices per platform+account: `Twitch-jwsoat`, `YouTube-myaccount`, `Merged-all`
3. Reuse sensor logic across platforms (no code duplication)
4. Scale to additional platforms in the future without refactoring coordinators/sensors

## Architecture

### Config Flow

Three-step flow:

1. **Step 1 (user):** Host + API key validation (unchanged)
2. **Step 2 (platform):** Dropdown: `Twitch`, `YouTube`, `Merged`
3. **Step 3 (account):** Account selector populated from backend for chosen platform

**Entry storage:** Each entry stores `{platform, user}` in its config data.

**Device naming:** `{platform.title()} - {user}` (e.g., `Twitch - jwsoat`, `Merged - all`)

### Coordinator

Rename `TwitchWatchtimeCoordinator` → `WatchtimeCoordinator`. Add `platform` parameter:

```python
class WatchtimeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: WatchtimeClient,
        platform: str,  # "twitch", "youtube", "merged"
        user: str | None,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(...)
        self._platform = platform
        self._user = user

    async def _async_update_data(self) -> dict[str, Any]:
        snapshot = await self._client.async_fetch_snapshot(
            platform=self._platform, user=self._user
        )
        # Rest of logic unchanged
```

### API Client

Parameterize endpoints by platform:

```python
async def async_fetch_snapshot(
    self, *, platform: str, user: str | None
) -> dict[str, Any]:
    # Calls /stats/{platform}/{user} or /stats/{platform}/merged

async def async_get_channel_today(
    self,
    *,
    platform: str,
    channel: str,
    user: str | None,
    window: str,
) -> int:
    # Calls /channel/{platform}/{user}/{channel}?window={window}
```

Backend returns same snapshot shape for `twitch` and `youtube`; `merged` combines both.

### Sensors

No changes to sensor logic. Sensors read `coordinator.data` unchanged. Device name derived from config:

```python
platform = config_entry.data.get(CONF_PLATFORM)
user = config_entry.data.get(CONF_USER)
device_name = f"{platform.title()} - {user}"

unique_id = f"{platform}_{user}_watchtime_today"  # includes platform
```

### Entity Registration

In `__init__.py` `async_setup_entry()`:

1. Extract `platform` and `user` from entry config
2. Create `WatchtimeCoordinator` with platform parameter
3. Register all sensors with platform-aware `unique_id` and device name
4. All sensors read from same coordinator; platform distinction is transparent

## Data Flow

```
Config entry {platform: "twitch", user: "jwsoat"}
    ↓
WatchtimeCoordinator(platform="twitch", user="jwsoat")
    ↓
async_fetch_snapshot(platform="twitch", user="jwsoat")
    ↓
Backend: GET /stats/twitch/jwsoat
    ↓
Snapshot dict (same shape for twitch/youtube/merged)
    ↓
Sensors read coordinator.data (unchanged logic)
    ↓
Device: "Twitch - jwsoat"
```

## Sensors Generated Per Entry

Same sensors for Twitch/YouTube/Merged (no branching in sensor.py):

- Watch time totals: today, week, month, all
- Top channel: daily, weekly, monthly, all-time
- Top category: daily, weekly, monthly, all-time
- Live status: now-watching, now-category, active
- Current channel: today, week, month, all-time

All reference `coordinator.data` unchanged; platform distinction handled by config and device naming.

## Configuration Constants

Add to `const.py`:

```python
CONF_PLATFORM = "platform"
PLATFORMS = ["twitch", "youtube", "merged"]
```

## Implementation Scope

1. Rename coordinator class, add platform parameter
2. Update API client endpoints to accept platform
3. Update config flow: add platform step between health check and account selection
4. Update entry creation: pass platform to coordinator
5. Update entity registration: derive device name from platform+user, update unique_id format
6. Update README: document platform selection and merged account behavior
7. Update tests: test all three platform paths

## Testing

- Config flow: test all platform paths (Twitch, YouTube, Merged)
- Coordinator: test platform parameter is passed correctly to API client
- Sensors: verify unique_id includes platform, device name is correct
- Integration: add entry for Twitch + YouTube + Merged, verify all three devices exist with correct names

## Future Extensibility

Adding a fourth platform (e.g., streaming service X):

1. Backend adds `/stats/servicex` endpoints matching pattern
2. Add `"servicex"` to `PLATFORMS` constant
3. That's it—coordinator and sensors work unchanged
