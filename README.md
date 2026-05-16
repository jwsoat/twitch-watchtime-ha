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
| `sensor.<prefix>_watchtime_week` | Total watch time this week |
| `sensor.<prefix>_watchtime_month` | Total watch time this month |
| `sensor.<prefix>_watchtime_all` | Total watch time all-time |

### Top channel

| Entity | What |
|---|---|
| `sensor.<prefix>_top_channel_daily` | Most-watched channel today |
| `sensor.<prefix>_top_channel_weekly` | Most-watched channel this week |
| `sensor.<prefix>_top_channel_monthly` | Most-watched channel this month |
| `sensor.<prefix>_top_channel_all_time` | Most-watched channel all-time |

### Top category

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_top_category_today` | Most-watched category today |
| `sensor.<prefix>_watchtime_top_category_week` | Most-watched category this week |
| `sensor.<prefix>_watchtime_top_category_month` | Most-watched category this month |
| `sensor.<prefix>_watchtime_top_category_all` | Most-watched category all-time |

### Live status

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_now_watching` | Current channel name, or `idle` |
| `binary_sensor.<prefix>_watchtime_active` | `on` whenever the backend saw a heartbeat in the last 2 minutes |

### Current channel (per-user entries only)

| Entity | What |
|---|---|
| `sensor.<prefix>_watchtime_current_channel_today` | Time watched today on the active channel |
| `sensor.<prefix>_watchtime_current_channel_week` | Time watched this week on the active channel |
| `sensor.<prefix>_watchtime_current_channel_month` | Time watched this month on the active channel |
| `sensor.<prefix>_watchtime_current_channel_all_time` | All-time watch time on the active channel |

`<prefix>` is the Twitch login (or `all_accounts` if the entry is set to pool everything).

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
4. **Step 2** — pick an account from the dropdown. Choose `All accounts` to pool everyone (including legacy anonymous heartbeats), or a specific Twitch login.
5. Done. Add the integration again for each Twitch account you want to track separately.

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
