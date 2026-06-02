# Multi-Platform Watchtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Home Assistant integration to support Twitch, YouTube, and merged watchtime data via platform selection in config flow.

**Architecture:** Generalize the coordinator to accept a platform parameter, parameterize API client endpoints by platform, add a platform selection step to config flow, and update entity registration to use platform-aware device names and unique_ids.

**Tech Stack:** Home Assistant integration framework, async Python, voluptuous config validation.

---

## Task 1: Add Platform Constants

**Files:**
- Modify: `custom_components/twitch_watchtime/const.py`

- [ ] **Step 1: Add platform constants**

Open `const.py` and add these constants after `USER_ALL`:

```python
CONF_PLATFORM = "platform"

PLATFORM_TWITCH = "twitch"
PLATFORM_YOUTUBE = "youtube"
PLATFORM_MERGED = "merged"

PLATFORMS = [PLATFORM_TWITCH, PLATFORM_YOUTUBE, PLATFORM_MERGED]
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/twitch_watchtime/const.py
git commit -m "feat: add platform constants for twitch/youtube/merged"
```

---

## Task 2: Rename Coordinator and Add Platform Parameter

**Files:**
- Modify: `custom_components/twitch_watchtime/coordinator.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Write the failing test for platform parameter**

Create `tests/test_coordinator.py`:

```python
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from unittest.mock import AsyncMock, MagicMock

from custom_components.twitch_watchtime.coordinator import WatchtimeCoordinator
from custom_components.twitch_watchtime.const import DOMAIN


@pytest.mark.asyncio
async def test_coordinator_stores_platform():
    """Test that coordinator stores platform parameter."""
    hass = MagicMock(spec=HomeAssistant)
    client = AsyncMock()
    
    coordinator = WatchtimeCoordinator(
        hass=hass,
        client=client,
        platform="twitch",
        user="testuser",
        scan_interval=None,
    )
    
    assert coordinator._platform == "twitch"
    assert coordinator._user == "testuser"


@pytest.mark.asyncio
async def test_coordinator_passes_platform_to_client():
    """Test that coordinator passes platform to API client."""
    from datetime import timedelta
    
    hass = MagicMock(spec=HomeAssistant)
    client = AsyncMock()
    client.async_fetch_snapshot = AsyncMock(return_value={})
    
    coordinator = WatchtimeCoordinator(
        hass=hass,
        client=client,
        platform="youtube",
        user="testuser",
        scan_interval=timedelta(seconds=60),
    )
    
    await coordinator._async_update_data()
    
    client.async_fetch_snapshot.assert_called_once_with(
        platform="youtube",
        user="testuser",
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_coordinator.py::test_coordinator_stores_platform -v
```

Expected output: `FAILED tests/test_coordinator.py::test_coordinator_stores_platform - (class not found / import error)`

- [ ] **Step 3: Rename coordinator class and add platform parameter**

Open `custom_components/twitch_watchtime/coordinator.py` and update:

```python
class WatchtimeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the backend and exposes the snapshot to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: TwitchWatchtimeClient,
        platform: str,
        user: str | None,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{platform}_{user or 'all_accounts'}",
            update_interval=scan_interval,
        )
        self._client = client
        self._platform = platform
        self._user = user

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = await self._client.async_fetch_snapshot(
                platform=self._platform,
                user=self._user,
            )
            # Rest of method unchanged
            now = snapshot.get("now")
            channel = now.get("channel") if now else None
            windows = (
                ("now_channel_today_seconds", "today"),
                ("now_channel_week_seconds", "week"),
                ("now_channel_month_seconds", "month"),
                ("now_channel_all_seconds", "all"),
            )
            if channel:
                results = await asyncio.gather(
                    *(
                        self._client.async_get_channel_today(
                            platform=self._platform,
                            channel=channel,
                            user=self._user,
                            window=window,
                        )
                        for _, window in windows
                    ),
                    return_exceptions=True,
                )
                for (key, _), result in zip(windows, results):
                    snapshot[key] = 0 if isinstance(result, BaseException) else result
            else:
                for key, _ in windows:
                    snapshot[key] = 0
            return snapshot
        except TwitchWatchtimeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TwitchWatchtimeConnectionError as err:
            raise UpdateFailed(str(err)) from err
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_coordinator.py -v
```

Expected output: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/twitch_watchtime/coordinator.py tests/test_coordinator.py
git commit -m "refactor: rename TwitchWatchtimeCoordinator to WatchtimeCoordinator and add platform parameter"
```

---

## Task 3: Update API Client to Parameterize Endpoints

**Files:**
- Modify: `custom_components/twitch_watchtime/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing test for platform parameterization**

Create `tests/test_api.py`:

```python
import pytest
from unittest.mock import AsyncMock
from aiohttp import ClientSession

from custom_components.twitch_watchtime.api import TwitchWatchtimeClient


@pytest.mark.asyncio
async def test_fetch_snapshot_constructs_correct_url_for_platform():
    """Test that API client constructs platform-specific URLs."""
    session = AsyncMock(spec=ClientSession)
    session.get = AsyncMock()
    session.get.return_value.__aenter__ = AsyncMock(
        return_value=AsyncMock(
            json=AsyncMock(return_value={"now": None}),
            status=200,
        )
    )
    session.get.return_value.__aexit__ = AsyncMock()
    
    client = TwitchWatchtimeClient(
        host="http://localhost:8765",
        api_key="test_key",
        session=session,
    )
    
    # Test Twitch endpoint
    await client.async_fetch_snapshot(platform="twitch", user="testuser")
    session.get.assert_called()
    call_url = session.get.call_args[0][0]
    assert "twitch" in call_url
    assert "testuser" in call_url
    
    # Reset mock
    session.get.reset_mock()
    
    # Test YouTube endpoint
    await client.async_fetch_snapshot(platform="youtube", user="testuser")
    call_url = session.get.call_args[0][0]
    assert "youtube" in call_url
    assert "testuser" in call_url


@pytest.mark.asyncio
async def test_get_channel_today_constructs_correct_url_for_platform():
    """Test that API client uses platform in channel endpoint."""
    session = AsyncMock(spec=ClientSession)
    session.get = AsyncMock()
    session.get.return_value.__aenter__ = AsyncMock(
        return_value=AsyncMock(
            json=AsyncMock(return_value=1234),
            status=200,
        )
    )
    session.get.return_value.__aexit__ = AsyncMock()
    
    client = TwitchWatchtimeClient(
        host="http://localhost:8765",
        api_key="test_key",
        session=session,
    )
    
    await client.async_get_channel_today(
        platform="youtube",
        channel="testchannel",
        user="testuser",
        window="today",
    )
    
    call_url = session.get.call_args[0][0]
    assert "youtube" in call_url
    assert "testchannel" in call_url
    assert "testuser" in call_url
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api.py::test_fetch_snapshot_constructs_correct_url_for_platform -v
```

Expected output: `FAILED` (method signature mismatch or missing platform parameter)

- [ ] **Step 3: Update API client methods to accept and use platform parameter**

Open `custom_components/twitch_watchtime/api.py` and update both methods:

```python
async def async_fetch_snapshot(
    self, *, platform: str, user: str | None
) -> dict[str, Any]:
    """Fetch watchtime snapshot from backend."""
    user_part = user or "merged"
    url = f"{self._host}/stats/{platform}/{user_part}"
    
    try:
        async with self._session.get(
            url,
            headers={"X-API-Key": self._api_key},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 401:
                raise TwitchWatchtimeAuthError("API key invalid")
            if response.status != 200:
                raise TwitchWatchtimeConnectionError(
                    f"Backend returned {response.status}"
                )
            return await response.json()
    except asyncio.TimeoutError as err:
        raise TwitchWatchtimeConnectionError("Request timeout") from err
    except aiohttp.ClientError as err:
        raise TwitchWatchtimeConnectionError(f"Connection error: {err}") from err


async def async_get_channel_today(
    self,
    *,
    platform: str,
    channel: str,
    user: str | None,
    window: str,
) -> int:
    """Fetch watch time for specific channel in given window."""
    user_part = user or "merged"
    url = f"{self._host}/channel/{platform}/{user_part}/{channel}?window={window}"
    
    try:
        async with self._session.get(
            url,
            headers={"X-API-Key": self._api_key},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 401:
                raise TwitchWatchtimeAuthError("API key invalid")
            if response.status != 200:
                raise TwitchWatchtimeConnectionError(
                    f"Backend returned {response.status}"
                )
            return await response.json()
    except asyncio.TimeoutError as err:
        raise TwitchWatchtimeConnectionError("Request timeout") from err
    except aiohttp.ClientError as err:
        raise TwitchWatchtimeConnectionError(f"Connection error: {err}") from err
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected output: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/twitch_watchtime/api.py tests/test_api.py
git commit -m "feat: parameterize API endpoints by platform in client"
```

---

## Task 4: Add Platform Selection to Config Flow

**Files:**
- Modify: `custom_components/twitch_watchtime/config_flow.py`
- Create: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing test for platform step**

Create `tests/test_config_flow.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from custom_components.twitch_watchtime.config_flow import TwitchWatchtimeConfigFlow
from custom_components.twitch_watchtime.const import CONF_PLATFORM, PLATFORM_TWITCH


@pytest.mark.asyncio
async def test_platform_step_displayed_after_user_step():
    """Test that platform step is shown after health check."""
    flow = TwitchWatchtimeConfigFlow()
    flow.hass = AsyncMock(spec=HomeAssistant)
    
    with patch("custom_components.twitch_watchtime.config_flow.TwitchWatchtimeClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.async_check_health = AsyncMock()
        mock_instance.async_get_users = AsyncMock(return_value=[
            {"username": "user1"},
            {"username": "user2"},
        ])
        mock_client.return_value = mock_instance
        
        # Step 1: user (host + key)
        result = await flow.async_step_user({
            "host": "http://localhost:8765",
            "api_key": "test_key",
        })
        
        # Should transition to platform step
        assert result["type"] == "form"
        assert result["step_id"] == "platform"


@pytest.mark.asyncio
async def test_platform_step_transitions_to_account():
    """Test that platform step transitions to account selection."""
    flow = TwitchWatchtimeConfigFlow()
    flow.hass = AsyncMock(spec=HomeAssistant)
    flow._host = "http://localhost:8765"
    flow._api_key = "test_key"
    flow._users = [
        {"username": "twitch_user1"},
        {"username": "twitch_user2"},
    ]
    
    # Platform step input
    result = await flow.async_step_platform({
        CONF_PLATFORM: PLATFORM_TWITCH,
    })
    
    # Should transition to account step
    assert result["type"] == "form"
    assert result["step_id"] == "account"
    assert flow._platform == PLATFORM_TWITCH
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config_flow.py::test_platform_step_displayed_after_user_step -v
```

Expected output: `FAILED` (async_step_platform not found or wrong flow)

- [ ] **Step 3: Update config flow to add platform step**

Open `custom_components/twitch_watchtime/config_flow.py` and update:

1. Add to imports:

```python
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OPT_IDLE_TIMEOUT,
    OPT_SCAN_INTERVAL,
    PLATFORM_MERGED,
    PLATFORM_TWITCH,
    PLATFORM_YOUTUBE,
    PLATFORMS,
    USER_ALL,
)
```

2. Update `__init__`:

```python
def __init__(self) -> None:
    self._host: str | None = None
    self._api_key: str | None = None
    self._platform: str | None = None
    self._users: list[dict[str, Any]] = []
```

3. Update `async_step_user` to call `async_step_platform` instead of `async_step_account`:

```python
async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
    errors: dict[str, str] = {}
    if user_input is not None:
        host = _normalize_host(user_input[CONF_HOST])
        api_key = user_input[CONF_API_KEY]
        session = async_get_clientsession(self.hass)
        client = TwitchWatchtimeClient(host=host, api_key=api_key, session=session)
        try:
            await client.async_check_health()
            # Don't fetch users yet; platform step happens first
        except TwitchWatchtimeAuthError:
            errors["base"] = "invalid_auth"
        except TwitchWatchtimeConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating watchtime backend")
            errors["base"] = "unknown"
        else:
            self._host = host
            self._api_key = api_key
            return await self.async_step_platform()

    return self.async_show_form(
        step_id="user",
        data_schema=STEP_USER_SCHEMA,
        errors=errors,
    )
```

4. Add new `async_step_platform` method:

```python
async def async_step_platform(self, user_input: dict[str, Any] | None = None) -> FlowResult:
    """Let user pick platform (Twitch/YouTube/Merged)."""
    if user_input is not None:
        self._platform = user_input[CONF_PLATFORM]
        # Now fetch users for this platform
        session = async_get_clientsession(self.hass)
        client = TwitchWatchtimeClient(
            host=self._host, api_key=self._api_key, session=session
        )
        try:
            self._users = await client.async_get_users(platform=self._platform)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Error fetching users for platform")
            return self.async_abort(reason="unknown")
        
        return await self.async_step_account()

    return self.async_show_form(
        step_id="platform",
        data_schema=vol.Schema({
            vol.Required(CONF_PLATFORM): vol.In(PLATFORMS),
        }),
        description_placeholders={
            "platforms": ", ".join(PLATFORMS),
        },
    )
```

5. Update `async_step_account` to use `self._platform`:

```python
async def async_step_account(self, user_input: dict[str, Any] | None = None) -> FlowResult:
    """Let user pick which account to track."""
    if user_input is not None:
        user = user_input[CONF_USER]
        
        # Check if this entry already exists
        await self.async_set_unique_id(f"{self._platform}_{user}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"{self._platform.title()} - {user}",
            data={
                CONF_HOST: self._host,
                CONF_API_KEY: self._api_key,
                CONF_PLATFORM: self._platform,
                CONF_USER: user,
            },
        )

    user_options = [
        (user["username"], user["username"]) for user in self._users
    ]
    user_options.insert(0, (USER_ALL, "All accounts"))

    return self.async_show_form(
        step_id="account",
        data_schema=vol.Schema({
            vol.Required(CONF_USER): vol.In(dict(user_options)),
        }),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config_flow.py -v
```

Expected output: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/twitch_watchtime/config_flow.py tests/test_config_flow.py
git commit -m "feat: add platform selection step to config flow"
```

---

## Task 5: Update Entity Registration in __init__.py

**Files:**
- Modify: `custom_components/twitch_watchtime/__init__.py`
- Create: `tests/test_init.py`

- [ ] **Step 1: Write failing test for device naming**

Create `tests/test_init.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.twitch_watchtime import async_setup_entry
from custom_components.twitch_watchtime.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DOMAIN,
    PLATFORM_TWITCH,
)


@pytest.mark.asyncio
async def test_device_name_includes_platform():
    """Test that device is named with platform prefix."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOST: "http://localhost:8765",
        CONF_API_KEY: "test_key",
        CONF_PLATFORM: PLATFORM_TWITCH,
        CONF_USER: "testuser",
    }
    config_entry.entry_id = "test_entry_id"
    config_entry.options = {}
    
    with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coordinator:
        with patch("custom_components.twitch_watchtime.async_add_entities"):
            mock_instance = AsyncMock()
            mock_instance.last_update_success = True
            mock_coordinator.return_value = mock_instance
            
            result = await async_setup_entry(hass, config_entry)
            
            # Verify coordinator was created with platform
            mock_coordinator.assert_called_once()
            call_kwargs = mock_coordinator.call_args[1]
            assert call_kwargs["platform"] == PLATFORM_TWITCH
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_init.py::test_device_name_includes_platform -v
```

Expected output: `FAILED` (WatchtimeCoordinator not found or incorrect signature)

- [ ] **Step 3: Update __init__.py to pass platform to coordinator and set device name**

Open `custom_components/twitch_watchtime/__init__.py` and update:

1. Update imports:

```python
from .coordinator import WatchtimeCoordinator  # renamed from TwitchWatchtimeCoordinator
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_IDLE_TIMEOUT,
    OPT_SCAN_INTERVAL,
    USER_ALL,
)
```

2. Update `async_setup_entry`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]
    platform = entry.data[CONF_PLATFORM]
    user = entry.data[CONF_USER]
    scan_interval = timedelta(
        seconds=entry.options.get(OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    idle_timeout = entry.options.get(OPT_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)

    session = async_get_clientsession(hass)
    client = TwitchWatchtimeClient(host=host, api_key=api_key, session=session)

    coordinator = WatchtimeCoordinator(
        hass=hass,
        client=client,
        platform=platform,
        user=user if user != USER_ALL else None,
        scan_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "idle_timeout": idle_timeout,
        "platform": platform,
        "user": user,
    }

    device_name = f"{platform.title()} - {user}"
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{platform}_{user}")},
        name=device_name,
    )

    # Set up sensors and binary sensors with platform-aware unique_id
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor", "binary_sensor"],
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True
```

3. Add import for device_registry:

```python
from homeassistant.helpers import device_registry as dr
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_init.py -v
```

Expected output: Test PASSES

- [ ] **Step 5: Commit**

```bash
git add custom_components/twitch_watchtime/__init__.py tests/test_init.py
git commit -m "feat: pass platform to coordinator and create platform-aware devices"
```

---

## Task 6: Update Sensor unique_id Format

**Files:**
- Modify: `custom_components/twitch_watchtime/sensor.py`

- [ ] **Step 1: Review sensor.py for unique_id generation**

Open `custom_components/twitch_watchtime/sensor.py` and look for how `unique_id` is currently constructed. It likely looks like:

```python
self._attr_unique_id = f"{platform}_{user}_{suffix}"
```

or uses a helper method. If entities are added per-entry and user/platform come from config, they should already be scoped correctly.

- [ ] **Step 2: Update unique_id to include platform if not already present**

Check if the base of each sensor has:

```python
self._attr_unique_id = f"{self.coordinator._platform}_{self.coordinator._user}_{sensor_suffix}"
```

If sensors pull platform/user from entry instead of coordinator, update to use coordinator fields:

```python
# In _BaseWatchtimeEntity or each sensor class
self._attr_unique_id = f"{coordinator._platform}_{coordinator._user}_{suffix}"
```

- [ ] **Step 3: Verify with existing tests**

Run existing sensor tests:

```bash
pytest tests/test_sensor.py -v
```

Expected: PASS (if unique_id was already scoped by entry, no change needed)

- [ ] **Step 4: Commit (if changes made)**

```bash
git add custom_components/twitch_watchtime/sensor.py
git commit -m "feat: verify sensor unique_id includes platform"
```

If no changes were needed, skip this commit.

---

## Task 7: Update Binary Sensor unique_id Format

**Files:**
- Modify: `custom_components/twitch_watchtime/binary_sensor.py`

- [ ] **Step 1: Review binary_sensor.py for unique_id generation**

Open `custom_components/twitch_watchtime/binary_sensor.py` and look for `unique_id` construction. Similar to sensors, it should derive from coordinator or entry.

- [ ] **Step 2: Update unique_id to include platform if not already present**

Check and update if needed (same pattern as Task 6):

```python
self._attr_unique_id = f"{coordinator._platform}_{coordinator._user}_{suffix}"
```

- [ ] **Step 3: Verify with existing tests**

```bash
pytest tests/test_binary_sensor.py -v
```

Expected: PASS

- [ ] **Step 4: Commit (if changes made)**

```bash
git add custom_components/twitch_watchtime/binary_sensor.py
git commit -m "feat: verify binary_sensor unique_id includes platform"
```

If no changes were needed, skip this commit.

---

## Task 8: Update README Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update "What you get" section**

Add a note about platform selection:

Find the section "## What you get (per entry)" and add after the first paragraph:

```markdown
Each entry tracks one platform (`Twitch`, `YouTube`, or `Merged`). The device is named as `{Platform} - {Account}` (e.g., `Twitch - jwsoat`, `YouTube - mychannel`, `Merged - all`).
```

- [ ] **Step 2: Update config flow instructions**

Find "## Add the integration" and update Step 2:

```markdown
2. **Step 2** — select a platform: `Twitch`, `YouTube`, or `Merged` (combined).
3. **Step 3** — pick an account from the dropdown for your chosen platform. Choose `All accounts` to pool everyone, or a specific username.
```

- [ ] **Step 3: Add platform examples**

After the automation example, add a new section:

```markdown
## Platform-Specific Examples

### Tracking Twitch and YouTube Separately

Add the integration twice:
- First entry: Platform = `Twitch`, Account = `yourtwitch`
- Second entry: Platform = `YouTube`, Account = `youryt`

This creates two devices:
- `Twitch - yourtwitch` with sensors like `sensor.twitch_yourtwitch_watchtime_today`
- `YouTube - youryt` with sensors like `sensor.youtube_youryt_watchtime_today`

### Tracking Combined Watch Time

Add the integration once with Platform = `Merged`, Account = `all`:
- Device: `Merged - all`
- Sensors like `sensor.merged_all_watchtime_today` combine Twitch + YouTube

Use merged sensors to trigger automations on total watch time regardless of platform.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README for platform selection and merged accounts"
```

---

## Task 9: Add Integration Tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test for full setup flow**

Create `tests/test_integration.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.twitch_watchtime import async_setup_entry
from custom_components.twitch_watchtime.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_USER,
    DOMAIN,
    PLATFORM_MERGED,
    PLATFORM_TWITCH,
    PLATFORM_YOUTUBE,
)


@pytest.mark.asyncio
async def test_setup_twitch_entry():
    """Test complete setup of Twitch entry."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOST: "http://localhost:8765",
        CONF_API_KEY: "test_key",
        CONF_PLATFORM: PLATFORM_TWITCH,
        CONF_USER: "testuser",
    }
    config_entry.entry_id = "test_entry_1"
    config_entry.options = {}
    config_entry.add_update_listener = MagicMock(return_value=AsyncMock())
    
    with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coord:
        with patch("custom_components.twitch_watchtime.device_registry.async_get"):
            mock_instance = AsyncMock()
            mock_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coord.return_value = mock_instance
            
            result = await async_setup_entry(hass, config_entry)
            
            assert result is True
            assert config_entry.entry_id in hass.data[DOMAIN]
            hass.config_entries.async_forward_entry_setups.assert_called_once()


@pytest.mark.asyncio
async def test_setup_youtube_entry():
    """Test complete setup of YouTube entry."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOST: "http://localhost:8765",
        CONF_API_KEY: "test_key",
        CONF_PLATFORM: PLATFORM_YOUTUBE,
        CONF_USER: "mytube",
    }
    config_entry.entry_id = "test_entry_2"
    config_entry.options = {}
    config_entry.add_update_listener = MagicMock(return_value=AsyncMock())
    
    with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coord:
        with patch("custom_components.twitch_watchtime.device_registry.async_get"):
            mock_instance = AsyncMock()
            mock_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coord.return_value = mock_instance
            
            result = await async_setup_entry(hass, config_entry)
            
            assert result is True


@pytest.mark.asyncio
async def test_setup_merged_entry():
    """Test complete setup of Merged entry."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.data = {
        CONF_HOST: "http://localhost:8765",
        CONF_API_KEY: "test_key",
        CONF_PLATFORM: PLATFORM_MERGED,
        CONF_USER: "all",
    }
    config_entry.entry_id = "test_entry_3"
    config_entry.options = {}
    config_entry.add_update_listener = MagicMock(return_value=AsyncMock())
    
    with patch("custom_components.twitch_watchtime.WatchtimeCoordinator") as mock_coord:
        with patch("custom_components.twitch_watchtime.device_registry.async_get"):
            mock_instance = AsyncMock()
            mock_instance.async_config_entry_first_refresh = AsyncMock()
            mock_coord.return_value = mock_instance
            
            result = await async_setup_entry(hass, config_entry)
            
            assert result is True
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_integration.py -v
```

Expected: All three tests PASS

- [ ] **Step 3: Run full test suite to ensure no regressions**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for platform selection"
```

---

## Summary

All tasks complete. The integration now:
- Accepts platform selection (Twitch/YouTube/Merged) in config flow
- Uses platform-specific API endpoints
- Creates separate devices per platform + account
- Names devices as `{Platform} - {Account}`
- Generates platform-aware unique_ids
- Scales to additional platforms without coordinator/sensor refactoring

All code is tested and documented.
