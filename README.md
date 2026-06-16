# WiFi Tracker

[![CI](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.md)

A comprehensive tool for monitoring WiFi usage with daemon support, real-time statistics, and data limits.

![Demo](demo.gif)

## Features

- **Real-time Monitoring**: Track WiFi usage with live upload/download rates and session data.
- **Daemon Mode**: Run in the background for continuous monitoring (supports systemd).
- **Watch Mode**: Interactive terminal dashboard with live-updating stats.
- **Data Limits**: Set daily, weekly, or monthly data caps per network with 80%/100% threshold warnings.
- **High-Usage Alerts**: Configure bandwidth threshold alerts (e.g. alert on 2GB/hour).
- **Top Apps**: See which applications consume the most network bandwidth, with option to auto-kill offenders.
- **MITM/Rogue Gateway Detection**: Detects unknown gateways, prompts to trust or block, with OUI vendor lookup.
- **Historical Data**: View usage statistics for all networks over the last 90 days (auto-cleaned).
- **ASCII Usage Graph**: Visual 24-hour usage graph per network.
- **Shell Completions**: Tab completion for bash, zsh, and fish.
- **Desktop Notifications**: Alerts via `notify-send`, `notify-send.sh`, or `zenity`.
- **Systemd Integration**: Install as a persistent system service.
- **XDG Compliant**: Respects `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, and `XDG_RUNTIME_DIR`.

## Installation

### pipx (Recommended)

```bash
sudo apt install pipx   # Debian/Ubuntu
pipx ensurepath
pipx install .
```

To upgrade: `pipx upgrade wifi-tracker`
To uninstall: `pipx uninstall wifi-tracker`

### install.sh (with shell completions)

```bash
git clone https://github.com/BeshoyEhab/wifi-tracker.git
cd wifi-tracker
./install.sh
```

This installs via `uv`, `pipx`, or `pip` (whichever is available) and sets up shell completions.

### From PyPI (when published)

```bash
pipx install wifi-tracker
```

## Usage

```
wifi-tracker <command> [options]
```

**Global options:**
- `--interface` / `-i`: Specify network interface (auto-detected if not provided).
- `--interval`: Update interval in seconds (default: 0.5).

### Monitoring

```bash
wifi-tracker daemon                              # Start background monitoring
wifi-tracker watch                               # Live interactive dashboard
wifi-tracker status                              # Show usage statistics
wifi-tracker status --all                        # Show all networks
wifi-tracker status --from-date 2025-06-01       # Stats from a date
wifi-tracker status --from-date 2025-06-01 --to-date 2025-06-15  # Date range
wifi-tracker today                               # Quick one-line status
wifi-tracker graph                               # ASCII usage graph (24h)
wifi-tracker graph MyWiFi                        # Graph for specific network
wifi-tracker top-apps                            # Show apps using the network
wifi-tracker networks                            # Show saved networks
```

**Aliases:** `d` (daemon), `w` (watch), `s` (status), `t` (today), `g` (graph)

### Limits & Alerts

```bash
wifi-tracker limit HomeWiFi 5GB monthly          # Set data cap
wifi-tracker remove-limit HomeWiFi               # Remove a limit
wifi-tracker usage-from HomeWiFi 2weeks          # Custom usage start date
wifi-tracker alert 2GB 1h                        # Alert on 2GB/hour
wifi-tracker alert show                          # Show current alert settings
```

### Security

```bash
wifi-tracker trust-gateway HomeWiFi 10.0.0.1     # Trust your router
wifi-tracker trusted-gateways                    # List trusted gateways
wifi-tracker mark-safe HomeWiFi firefox          # Mark app as safe
wifi-tracker mark-safe HomeWiFi firefox --always # Always safe (not just once)
wifi-tracker safe-apps                           # List trusted apps
wifi-tracker kill-app HomeWiFi malware           # Kill an app
wifi-tracker kill-app HomeWiFi malware --always  # Auto-kill on limit
wifi-tracker kill-list                           # List auto-kill apps
```

### Management

```bash
wifi-tracker stop                                # Stop the daemon
wifi-tracker cleanup                             # Clean data older than 90 days
wifi-tracker cleanup 30                          # Clean data older than 30 days
wifi-tracker install-service                     # Install systemd service
wifi-tracker remove-service                      # Remove systemd service
```

## Requirements

### Required

- Python 3.12+
- Linux
- `psutil` and `rich` (installed automatically)

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
| `systemctl` | Systemd service management | For `install-service` |

## Project Structure

```
wifi-tracker/
├── wifi_tracker_modules/
│   ├── __init__.py           # Package initializer
│   ├── cli.py                # CLI argument parsing and main entry point
│   ├── config.py             # XDG-compliant path configuration
│   ├── data_manager.py       # Data persistence, limits, app tracking
│   ├── network_monitor.py    # Interface detection, stats, gateway lookup
│   ├── process_manager.py    # Daemonization, PID management, systemd
│   ├── display_manager.py    # Rich terminal UI, ASCII graph
│   └── notification_manager.py  # Desktop notifications
├── completions/
│   ├── wifi-tracker.bash     # Bash completions
│   ├── _wifi-tracker         # Zsh completions
│   └── wifi-tracker.fish     # Fish completions
├── tests/
│   ├── test_data_manager.py  # DataManager unit tests
│   └── test_network_monitor.py  # NetworkMonitor unit tests
├── .github/workflows/ci.yml  # GitHub Actions CI
├── install.sh                # Install script with completion setup
├── pyproject.toml            # Package config and dependencies
├── demo.gif                  # Terminal demo
└── LICENSE.md                # MIT License
```

## Data Storage

Data follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/):

| File | Default Path |
|------|-------------|
| Usage data | `~/.local/share/wifi-tracker/wifi_usage.json` |
| Limits | `~/.local/share/wifi-tracker/wifi_limits.json` |
| Data backup | `~/.local/share/wifi-tracker/wifi_usage.json.bak` |
| Daemon log | `~/.cache/wifi-tracker/daemon.log` |
| Error log | `~/.cache/wifi-tracker/error.log` |
| PID file | `$XDG_RUNTIME_DIR/wifi-tracker/daemon.pid` |

All paths respect `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, and `XDG_RUNTIME_DIR` environment variables.

## Contributing

Feel free to submit issues or pull requests on GitHub.

## License

See [LICENSE.md](LICENSE.md) for details.
