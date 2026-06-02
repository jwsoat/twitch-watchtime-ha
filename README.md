# Twitch Watchtime — Home Assistant Integration

Home Assistant custom integration for the self-hosted
[twitch-watchtime](https://github.com/jwsoat/twitch-watchtime) backend. Tracks
Twitch watch time per account and exposes it as Home Assistant sensors you can
graph, automate, and put on a dashboard.

## What you get (per entry)

### Watch time totals

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_today` | Total watch time today |
| `sensor.<prefix>_watchtime_week` | Total watch time over the last 7 days |
| `sensor.<prefix>_watchtime_month` | Total watch time over the last 30 days |
| `sensor.<prefix>_watchtime_all` | Total watch time all-time |

### Top channel

| Entity | What |
|---|---|
| `sensor.<prefix>_top_channel_daily` | Most-watched channel today |
| `sensor.<prefix>_top_channel_weekly` | Most-watched channel over the last 7 days |
| `sensor.<prefix>_top_channel_monthly` | Most-watched channel over the last 30 days |
| `sensor.<prefix>_top_channel_all_time` | Most-watched channel all-time |

### Top category

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_top_category_today` | Most-watched category today |
| `sensor.<prefix>_watchtime_top_category_week` | Most-watched category over the last 7 days |
| `sensor.<prefix>_watchtime_top_category_month` | Most-watched category over the last 30 days |
| `sensor.<prefix>_watchtime_top_category_all` | Most-watched category all-time |

### Live status

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_now_watching` | Current channel name, or `idle` |
| `sensor.<prefix>_watchtime_now_category` | Current category name, or `idle` |
| `binary_sensor.<prefix>_watchtime_active` | `on` whenever the backend saw a heartbeat in the last 2 minutes |

### Current channel

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_current_channel_today` | Time watched today on the active channel |
| `sensor.<prefix>_watchtime_current_channel_week` | Time watched on the active channel over the last 7 days |
| `sensor.<prefix>_watchtime_current_channel_month` | Time watched on the active channel over the last 30 days |
| `sensor.<prefix>_watchtime_current_channel_all_time` | All-time watch time on the active channel |

`<prefix>` is derived from the device name: for "Twitch - jwsoat" it's `twitch_jwsoat`, for "Merged - all" it's `merged_all`, etc.

## Requirements

- Home Assistant Core 2024.10 or newer.
- A running [twitch-watchtime](https://github.com/jwsoat/twitch-watchtime) backend (FastAPI on Proxmox or similar) reachable from your HA host.
- The API key you've configured for that backend.

## Install via HACS (custom repository)

1. In Home Assistant, open **HACS**.
2. Click the 3-dot menu (top-right) → **Custom repositories**.
3. Paste `https://github.com/jwsoat/twitch-watchtime-ha`, category **Integration**, click **Add**.
4. Back in HACS, search for **Twitch Watchtime**, click it → **Download**.
5. Restart Home Assistant.

## Add the integration

1. **Settings → Devices & Services → Add Integration**.
2. Search **Twitch Watchtime**.
3. **Step 1** — paste your backend URL (e.g. `http://192.168.1.100:8765`) and your API key. The integration calls `/health` and `/stats/users` to verify both.
4. **Step 2** — choose a platform:
   - **Twitch** — Twitch watchtime only
   - **YouTube** — YouTube watchtime only
   - **Merged** — Combined Twitch + YouTube watchtime (if backend provides merged data)
5. **Step 3** — pick an account from the dropdown. Choose `All accounts` to pool everyone (including legacy anonymous heartbeats), or a specific login.
6. Done. Add the integration again for each platform+account combination you want to track separately (e.g., one entry for Twitch-jwsoat, another for YouTube-myaccount, another for Merged-all).

## Platform behavior

Each integration entry tracks one platform+account combination. The integration will create a device per entry:

- **Twitch entry** creates device "Twitch - <account>"
- **YouTube entry** creates device "YouTube - <account>"
- **Merged entry** creates device "Merged - <account>"

All sensors refer to the same sensor names (watchtime_today, top_channel_weekly, etc.), but each device's sensors only show data for that entry's platform.

**Merged mode:** If your backend provides `/stats/merged/*` endpoints, the Merged platform gives you a single set of sensors combining both Twitch and YouTube. This is useful if you want one unified dashboard for cross-platform watch time.

**Multiple entries:** Create separate entries for separate tracking. For example:
- Twitch - jwsoat (tracks only your Twitch time)
- YouTube - myaccount (tracks only your YouTube time)
- Merged - all (tracks combined time if you want one unified view)

Each entry polls independently on the configured scan interval.

After install, click the entry's **Configure** button to tweak:
- **Scan interval** (default `60`s, range `15`–`600`).
- **Idle timeout** (default `120`s, matching the backend's `/stats/now` window).

## Example automation

Turn the office light purple when you start watching:

```yaml
automation:
  - alias: "Office light purple when watching Twitch"
    trigger:
      - platform: state
        entity_id: binary_sensor.jwsoat_watchtime_active
        to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.office
        data:
          rgb_color: [145, 70, 255]
          brightness_pct: 80
```

## Troubleshooting

- **"Cannot connect"** at install — the backend's `/health` endpoint isn't reachable. Confirm the URL and that your HA host can hit it on the network.
- **"Invalid auth"** — the API key was rejected. Use the same key you put in the dashboard and the Chrome extension.
- **Entities show as `unavailable`** — usually a transient network blip; HA will recover on the next poll. Check **Settings → System → Logs** for `twitch_watchtime` entries.
- **Updates not appearing** — restart Home Assistant after HACS updates the integration.

## License

MIT.
