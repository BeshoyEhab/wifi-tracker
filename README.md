# WiFi Tracker

[![CI](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.md)

Monitor WiFi usage with live rates, data caps, per-app tracking, rogue gateway detection, and daemon mode.

![Demo](demo.gif)

## Features

- **Live monitoring** — real-time download/upload rates, session totals, lifetime stats
- **Daemon mode** — background collection with double-fork, PID file, and systemd support
- **Interactive dashboard** — Rich-powered `watch` mode with live-updating panels
- **Data limits** — daily, weekly, or monthly caps per SSID with 80%/100% desktop alerts
- **High-usage alerts** — configurable threshold + time window (e.g. 2 GB in 1 hour)
- **Accurate per-app tracking** — root conntrack collector (`perapp`) reads `/proc/net/nf_conntrack` for precise per-process traffic; `/proc/pid/io` fallback is scaled to the real interface delta so browser estimates never overcount
- **Rogue gateway detection** — MITM protection: detects unknown gateways, prompts to trust/block, OUI vendor lookup
- **Historical graphs** — ASCII bar charts at 1h/24h/7d/30d/12m granularity
- **One-line status** — `today` shows today's consumption (midnight→now) with mean rate and daily limit %
- **Desktop notifications** — `notify-send`, `notify-send.sh` (interactive buttons), or `zenity` dialogs
- **Shell completions** — bash, zsh, fish (commands, flags, SSIDs, app names)
- **JSON output** — `--json` flag on `today` and `status` for scripting
- **Systemd integration** — one-command install/remove as a user service
- **XDG compliant** — respects `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR`
- **Auto-cleanup** — old data purged after 90 days (configurable), with backup on save

## Installation

### pipx (recommended)

```bash
sudo apt install pipx   # Debian/Ubuntu
pipx ensurepath
pipx install .
```

Upgrade: `pipx upgrade wifi-tracker`
Uninstall: `pipx uninstall wifi-tracker`

### install.sh (with shell completions)

```bash
git clone https://github.com/BeshoyEhab/wifi-tracker.git
cd wifi-tracker
./install.sh
```

Auto-detects `uv`, `pipx`, or `pip` and sets up bash/zsh/fish completions.

### uv / pip (manual)

```bash
uv tool install .
# or
pip install --user .
```

## Quick Start

```bash
# Start monitoring in background
wifi-tracker daemon

# Quick check
wifi-tracker today

# Interactive dashboard
wifi-tracker watch

# Set a daily data cap
wifi-tracker limit HomeWiFi 2GB daily

# Configure high-usage alert
wifi-tracker alert 500MB 1h

# Install accurate per-app collector (root conntrack service, prompts for sudo)
wifi-tracker perapp install

# Show usage graph
wifi-tracker graph

# View top apps (uses collector data when available)
wifi-tracker top-apps

# Stop the daemon
wifi-tracker stop
```

## Command Reference

Global options:

| Flag | Description |
|------|-------------|
| `--interface`, `-i` | Network interface (auto-detected) |
| `--interval` | Polling interval in seconds (default 0.5) |
| `--quiet`, `-q` | Suppress desktop notifications |
| `--json`, `-j` | Machine-readable JSON output |
| `--version` | Show version and exit |

### Monitoring

| Command | Aliases | Description |
|---------|---------|-------------|
| `daemon` | `d` | Start background monitoring (double-fork, PID file, signal handlers) |
| `watch` | `w` | Live Rich TUI dashboard (rates, session, limits, graphing) |
| `status` | `s` | Usage statistics table with limit percentage per SSID |
| `today` | `t` | Quick one-line status: today's use (midnight→now), mean rate, daily limit %, top app |
| `graph` | `g` | ASCII bar graph for any SSID at 1h (per-minute), 24h, 7d, 30d, or 12m |
| `top-apps` | — | Bandwidth ranking of running processes (PID, user, bytes, connections) |
| `networks` | — | List all known SSIDs with gateway IP, total usage, last seen |

**`status` flags:** `--all`, `--from-date YYYY-MM-DD`, `--to-date YYYY-MM-DD`, `--range {1h,24h,7d,30d,12m}`

**`graph` flags:** `--range {1h,24h,7d,30d,12m}`, optional `SSID` argument

**`today` flags:** `--range` (accepted but ignored — `today` always reads midnight→now)

#### Aliases

```
daemon → d
watch  → w
status → s
today  → t
graph  → g
```

### Limits & Alerts

| Command | Description |
|---------|-------------|
| `limit SSID SIZE INTERVAL` | Set data cap (e.g. `5GB monthly`, `500MB daily`, `1TB weekly`) |
| `remove-limit SSID` | Remove cap for a network |
| `usage-from SSID DATE` | Start counting usage from a date (`YYYY-MM-DD` or relative: `2weeks`, `1month`, `14days`) |
| `alert show` | Display current alert threshold and window |
| `alert THRESHOLD WINDOW` | Set high-usage alert (e.g. `2GB 1h`, `500M 30m`, `5G 2d`) |

### Security

| Command | Description |
|---------|-------------|
| `trust-gateway SSID IP [--mac MAC]` | Mark a gateway as safe (MITM protection) |
| `trusted-gateways [SSID]` | List trusted gateways |
| `untrust-gateway SSID IP` | Remove a trusted gateway |
| `block-gateway SSID IP [--mac MAC]` | Suppress notifications for a gateway |
| `blocked-gateways [SSID]` | List blocked gateways |
| `unblock-gateway SSID IP` | Remove a blocked gateway |
| `mark-safe SSID APP [--always]` | Suppress alerts/kills for an app (once or permanently) |
| `safe-apps [SSID]` | List apps marked safe |
| `kill-app SSID APP [--always]` | Kill an app immediately and optionally auto-kill on future limit breaches |
| `kill-list [SSID]` | List apps set for auto-kill |

### Management

| Command | Description |
|---------|-------------|
| `stop` | Gracefully stop the daemon (SIGTERM + force-kill stragglers) |
| `cleanup [DAYS]` | Purge daily records older than N days (default: 90) |
| `install-service` | Install user systemd unit (`~/.config/systemd/user/wifi-tracker.service`) |
| `remove-service` | Stop, disable, and remove the systemd unit |
| `perapp install [--interface IFACE]` | Install root conntrack collector systemd service (auto-elevates via sudo) |
| `perapp remove` | Stop and remove the root collector service |
| `perapp status` | Show collector install state, service status, last snapshot, tracked apps |

## Architecture

```
wifi_tracker_modules/
├── __init__.py              # Package init, version, re-exports
├── cli.py                   # Argument parsing, WiFiTracker orchestrator
├── config.py                # XDG paths, app-wide constants
├── data_manager.py          # JSON persistence, daily/hourly/minutely tracking, limits
├── network_monitor.py       # Interface stats, SSID, gateway IP/MAC, rates
├── process_manager.py       # Daemonization, PID, systemd, top-apps via /proc
├── display_manager.py       # Rich TUI, ASCII graph, one-line status, JSON formatters
├── alert_manager.py         # Limit checks, high-usage alerts, daily summaries
├── notification_manager.py  # Desktop notifications + interactive dialogs
├── app_manager.py           # New-app detection, high-usage app alerts
├── perapp.py                # Root collector reader + service management (perapp subcommand)
└── perapp_collector.py      # Root conntrack collector (systemd system service)
```

### Module Details

**`cli.py`** — `WiFiTracker` class orchestrates all modes. Parses subcommands via `argparse`, resolves aliases, creates module instances, dispatches to mode handlers (`daemon_mode`, `watch_mode`, `status_mode`, etc.). Shell completion engine in `_handle_completion`, backed by a decorator-registered handler table (`_COMPLETERS`).

**`config.py`** — `Config` class with static methods for XDG-compliant paths:
- `get_data_file()` → `~/.local/share/wifi-tracker/wifi_usage.json`
- `get_limits_file()` → `~/.local/share/wifi-tracker/wifi_limits.json`
- `get_pid_file()` → `$XDG_RUNTIME_DIR/wifi-tracker/daemon.pid`
- `get_log_file()` → `~/.cache/wifi-tracker/daemon.log`
- `get_error_log_file()` → `~/.cache/wifi-tracker/error.log`

Constants: `SAVE_INTERVAL=0.5`, `CLEANUP_DAYS=90`, `MINUTELY_MAX_ENTRIES=120`, `NEW_APP_THRESHOLD=5`.

**`data_manager.py`** — `DataManager` handles all JSON persistence with `fcntl` file locking:
- Usage data: per-SSID tracking of `total_rx/tx`, `daily` dict (keyed by `YYYY-MM-DD`), `hourly`, `minutely`, sessions, peaks
- Per-app tracking: rollup entries per PID with delta accumulation and cutoff cleanup
- `compute_app_scale_factors()` — scales per-app estimates so their sum never exceeds the real interface delta (prevents `/proc/pid/io` overcounting)
- `record_app_deltas()` — stores deltas sourced from the accurate root conntrack collector
- Limits: load/save/update with notification flags (`notified_80`, `notified_100`)
- Gateway lists: `known_gateways`, `blocked_gateways` with IP/MAC/vendor/timestamp
- App lists: `safe_apps`, `safe_apps_onetime`, `kill_apps`, `kill_apps_onetime`
- Migration: auto-migrates from legacy `~/.cache/wifi_usage.json`
- Backup: copies to `.json.bak` before each save

**`network_monitor.py`** — `NetworkMonitor` reads interface stats from `/proc/net/dev`, detects SSID via `iwgetid`/`iwconfig`/`nmcli`, calculates rates from deltas, parses signal quality from `iwconfig`, reads gateway IP from `/proc/net/route` (or `ip route`), looks up MAC via `/proc/net/arp` (with ping fallback to populate the table), and maps OUI prefixes to vendor names.

**`process_manager.py`** — `ProcessManager` handles:
- Daemonization: double-fork, `setsid`, `umask`, stdin/stdout/stderr redirect to `/dev/null`
- Instance management: `find_all_instances`, `kill_all_instances` (SIGTERM → wait → SIGKILL)
- PID file: create, remove, staleness check
- systemd: install/remove user service
- Top apps: iterates `psutil.net_connections("inet")`, reads `/proc/pid/io` for `rchar/wchar` minus `read_bytes/write_bytes` as network-IO approximation (heuristic fallback when the conntrack collector is unavailable)
- Signal handlers: SIGTERM, SIGINT, SIGHUP, SIGUSR1 set a shutdown flag that the main loop honors (no blocking I/O in signal context)
- Logging: `_log_info` / `_log_error` to `daemon.log` / `error.log`

**`display_manager.py`** — `DisplayManager` provides:
- `create_layout()` — Rich `Layout` with header, stats table, live-speed panel, data-limit progress bar
- `build_watch_display()` — plain-text fallback when Rich is unavailable
- `print_detailed_stats()` — Rich `Table` of all SSIDs with total/period/connections/limit
- `print_quick_status()` — one-line `today` output
- `print_ascii_graph()` — Unicode bar chart (█░) with auto-scaled bars
- `format_bytes()` / `format_rate()` / `format_duration()` — human-readable formatting
- `output_json()` / `format_status_json()` / `format_stats_json()` — JSON serialization
- `_calculate_period_usage()` — sums daily records for any interval or date range

**`alert_manager.py`** — `AlertManager` checks limits (80%/100% thresholds), sends daily summary notifications, and provides static parsers (`parse_size`, `parse_window`, `format_window`).

**`notification_manager.py`** — `NotificationManager` wraps `notify-send` (plain notifications), `notify-send.sh` (interactive action buttons for trust/block and safe/kill), and `zenity` (fallback GUI dialogs). Priority: `notify-send.sh` > `zenity` > plain notification. Holds a global singleton `notifier`.

**`app_manager.py`** — `AppManager` tracks new apps (first network access alerts after a 5-app threshold) and checks high-usage apps against the configured alert threshold, respecting safe/kill lists. It prefers accurate per-app data from the root conntrack collector (`_record_from_collector`) and falls back to the scaled `/proc/pid/io` heuristic.

**`perapp.py`** — reader + service manager for the accurate per-app collector. `read_snapshot()` loads the fresh cumulative snapshot from `/run/wifi-tracker/per_app.json`; `install_system_service()`/`remove_system_service()` manage the systemd system unit and enable `nf_conntrack_acct`. `install`/`remove` auto-elevate via `sudo` with `PYTHONDONTWRITEBYTECODE=1` so the tool's own uv install dir never accumulates root-owned `__pycache__` files.

**`perapp_collector.py`** — stdlib-only root service that parses `/proc/net/nf_conntrack`, maps flows to PIDs via local sockets, and atomically writes cumulative per-app byte counts to `/run/wifi-tracker/per_app.json` (mode 0644). Gracefully degrades when run without root (used for local testing).

## Data Flow

```
iwgetid/iwconfig/nmcli         /proc/net/dev
      │                             │
      ▼                             ▼
 NetworkMonitor ──► SSID ──┐  Interface Stats ──┐
                           │                    │
                           ▼                    ▼
                     DataManager.update_usage()
                           │
                    ┌──────┴──────┐
                    ▼              ▼
              wifi_usage.json   Limits checks
              (daily/hourly/    (AlertManager)
               minutely/per-       │
               app data)           ▼
                              Notifications
                              (notify-send/
                               notify-send.sh/
                               zenity)
```

In daemon mode, measurements are collected every `interval` seconds (default 0.5). Deltas are accumulated into daily/hourly/minutely buckets. Per-app data is sampled every 60 seconds via `AppManager.check_high_usage_apps()` — it prefers the root conntrack collector snapshot (when installed and fresh) and otherwise falls back to `/proc/pid/io` estimates scaled to the real interface delta. Data is flushed to disk every `SAVE_INTERVAL` seconds.

## Data Storage

All paths respect `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, and `XDG_RUNTIME_DIR`.

| File | Default Path | Contents |
|------|-------------|----------|
| Usage data | `~/.local/share/wifi-tracker/wifi_usage.json` | Per-SSID totals, daily/hourly/minutely history, app usage, gateway lists, safe/kill lists |
| Limits | `~/.local/share/wifi-tracker/wifi_limits.json` | Per-SSID cap size/interval, notification flags, custom start dates |
| Backup | `~/.local/share/wifi-tracker/wifi_usage.json.bak` | Previous state before each save |
| Daemon log | `~/.cache/wifi-tracker/daemon.log` | INFO-level daemon messages |
| Error log | `~/.cache/wifi-tracker/error.log` | ERROR-level messages (monitoring loop, file I/O, etc.) |
| PID file | `$XDG_RUNTIME_DIR/wifi-tracker/daemon.pid` | Daemon process ID for `stop` and staleness checks |
| Per-app snapshot | `/run/wifi-tracker/per_app.json` | Cumulative per-app byte counts written by the root conntrack collector (mode 0644) |

### JSON Structure (abbreviated)

```json
{
  "HomeWiFi": {
    "total_rx": 150000000000,
    "total_tx": 48000000000,
    "first_seen": "2026-01-15T08:30:00",
    "last_seen": "2026-07-23T13:52:00",
    "connection_count": 847,
    "daily": {
      "2026-07-23": {
        "rx": 5000000000,
        "tx": 2000000000,
        "hourly": { "09": 350000000, "10": 420000000 },
        "minutely": { "09:00": 15000000, "09:01": 12000000 },
        "peak_rx_rate": 125000000,
        "data_points": 7200
      }
    },
    "known_gateways": [{ "ip": "192.168.1.1", "mac": "A4:2B:8C:...", "vendor": "Netgear" }],
    "safe_apps": ["firefox"],
    "app_usage": {
      "firefox": {
        "entries": [{ "ts": "2026-07-23T13:00:00", "sent": 1024, "recv": 4096 }]
      }
    }
  },
  "_metadata": {
    "last_cleanup": "2026-07-22T13:00:00",
    "alert_settings": { "threshold_bytes": 5368709120, "window_hours": 1 }
  }
}
```

## Security Features

### MITM / Rogue Gateway Detection

When the daemon detects a gateway IP that hasn't been seen before on an SSID:

1. If the gateway is in the **trusted** list — silent pass
2. If the gateway is in the **blocked** list — silent pass (notifications suppressed)
3. Otherwise — interactive prompt via `notify-send.sh` (buttons: Trust / Block) or `zenity` (radio list), with a 60-second timeout. If no interactive tool is available, a plain notification is sent with the CLI trust command.

The gateway is identified by **IP** (not MAC), since MACs can change due to ISP equipment swaps.

### App Safe / Kill Lists

- `mark-safe --always` — permanently suppress alerts and auto-kill for an app on a given SSID
- `mark-safe` (without `--always`) — one-time pass (consumed on next match)
- `kill-app --always` — auto-kill the app whenever the limit is exceeded on that SSID
- `kill-app` (without `--always`) — kill once on first limit breach

## Shell Completions

Three completion files are provided in `completions/`:

- `completions/wifi-tracker.bash` — bash
- `completions/_wifi-tracker` — zsh
- `completions/wifi-tracker.fish` — fish

The `install.sh` script copies them to the standard locations automatically.
All three are **fully dynamic**: every command, flag, and argument suggestion is generated live by the CLI's embedded completion engine (`wifi-tracker --complete <shell> ...`), so completions never go stale when new commands or flags are added. This includes SSID names, running app names, data-limit sizes, cleanup day counts, and `perapp` subcommands.

## Desktop Notifications

| Tool | Purpose | Required? |
|------|---------|-----------|
| `notify-send` | Plain notifications (limit warnings, connection changes, daily summary) | Optional (no notifications without it) |
| `notify-send.sh` | Interactive action buttons for gateway trust/block and high-usage safe/kill | Optional (falls back to zenity or plain notification) |
| `zenity` | GUI radio-list dialog for interactive prompts | Optional (falls back to plain notification) |

Priority: `notify-send.sh` > `zenity` > `notify-send` (plain).

Use `--quiet` / `-q` to suppress all notifications.

## Requirements

### Python

- Python 3.12+
- Linux (reads `/proc/net/dev`, `/proc/net/route`, `/proc/net/arp`, `/proc/pid/io`)
- `psutil` (≥7.2.2) — process iteration, network connections, PID management
- `rich` (≥14.3.2) — terminal dashboard, tables, panels (optional, degrades gracefully)

### System Tools

| Tool | Purpose | Required? |
|------|---------|-----------|
| `iwconfig` | Wireless interface detection, signal quality | Yes |
| `iwgetid` | SSID detection | Yes |
| `nmcli` | SSID fallback when `iwgetid` fails | Optional |
| `ip` | Gateway IP detection fallback | Optional |
| `ping` | ARP table population for gateway MAC lookup | Optional |
| `notify-send` | Desktop notifications | Optional |
| `notify-send.sh` | Interactive action buttons in notifications | Optional |
| `zenity` | Alternative interactive dialogs | Optional |
| `systemctl` | Systemd service management | For `install-service` / `perapp` |
| `conntrack` / `nf_conntrack` | Per-app network accounting (`/proc/net/nf_conntrack`) | For `perapp install` (root, enables `nf_conntrack_acct`) |

## Project Structure

```
wifi-tracker/
├── wifi_tracker_modules/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── data_manager.py
│   ├── network_monitor.py
│   ├── process_manager.py
│   ├── display_manager.py
│   ├── alert_manager.py
│   ├── notification_manager.py
│   ├── app_manager.py
│   ├── perapp.py
│   └── perapp_collector.py
├── completions/
│   ├── wifi-tracker.bash
│   ├── _wifi-tracker
│   └── wifi-tracker.fish
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_alert_manager.py
│   ├── test_cli.py
│   ├── test_completions.py
│   ├── test_data_manager.py
│   ├── test_display_manager.py
│   ├── test_network_monitor.py
│   ├── test_notification_manager.py
│   ├── test_perapp.py
│   └── test_process_manager.py
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── .editorconfig
├── install.sh
├── pyproject.toml
├── demo.gif
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
├── SECURITY.md
└── LICENSE.md
```

## Testing

```bash
# Run all tests
uv run pytest tests/

# With coverage
uv run coverage run -m pytest tests/ && uv run coverage report
```

Current test coverage (~68%): `DataManager` (storage CRUD, limits, gateways, app
lists, app scaling), `NetworkMonitor` (interface detection, SSID, rates, gateway
lookup), `perapp`/`perapp_collector` (snapshot parsing, conntrack parsing, service
management), `cli.py` (command handlers + subcommand dispatch + completion engine),
`process_manager` (PID lifecycle, instance discovery/killing, systemd service),
`display_manager` (formatting, graphs, JSON), `alert_manager` (limit thresholds,
size/window parsing), and `notification_manager` (sending, interactive prompts).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, linting, and PR guidelines.

## License

[MIT](LICENSE.md) — Copyright (c) 2025 Bishoy Ehab
