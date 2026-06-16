# WiFi Tracker

[![CI](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/BeshoyEhab/wifi-tracker/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.md)

A comprehensive tool for monitoring WiFi usage with daemon support, real-time statistics, and data limits.

![Demo](demo.gif)

## Features

- **Real-time Monitoring**: Track WiFi usage in real-time with live rates and session data.
- **Daemon Mode**: Run in the background as a daemon for continuous monitoring.
- **Watch Mode**: Interactive display with live updates.
- **Data Limits**: Set monthly, weekly, or daily data limits with warnings.
- **Historical Data**: View usage statistics for all networks over the last 90 days.
- **Top Apps**: See which applications are using the most network bandwidth.
- **Multi-Interface Support**: Automatically detects and monitors the active wireless interface.

## Installation

The recommended way to install WiFi Tracker is using `pipx`. This ensures it runs in an isolated environment and doesn't conflict with system packages.

1. Install `pipx` if you haven't already:

   ```bash
   sudo apt install pipx  # Debian/Ubuntu
   pipx ensurepath
   ```

2. Install WiFi Tracker:

   ```bash
   pipx install .
   ```

This will automatically install dependencies (`psutil`, `rich`) and make the `wifi-tracker` command available in your PATH.

To upgrade later:

```bash
pipx upgrade wifi-tracker
```

To uninstall:

```bash
pipx uninstall wifi-tracker
```

## Usage

```
wifi-tracker <command> [options]
```

Global options:
- `--interface` / `-i`: Specify network interface (auto-detected if not provided).
- `--interval`: Update interval in seconds (default: 0.5).

### Monitoring

```bash
wifi-tracker daemon                          # Start background monitoring
wifi-tracker watch                           # Live interactive dashboard
wifi-tracker status                          # Show usage statistics
wifi-tracker status --all                    # Show all networks
wifi-tracker status --from-date 2025-06-01   # Stats from a date
wifi-tracker today                           # Quick one-line status
wifi-tracker graph                           # ASCII usage graph (24h)
wifi-tracker graph MyWiFi                    # Graph for specific network
wifi-tracker top-apps                        # Show apps using the network
wifi-tracker networks                        # Show saved networks
```

### Limits & Alerts

```bash
wifi-tracker limit HomeWiFi 5GB monthly      # Set data cap
wifi-tracker remove-limit HomeWiFi           # Remove a limit
wifi-tracker usage-from HomeWiFi 2weeks      # Custom usage start date
wifi-tracker alert 2GB 1h                    # Alert on 2GB/hour
wifi-tracker alert show                      # Show current alert settings
```

### Security

```bash
wifi-tracker trust-gateway HomeWiFi 10.0.0.1 # Trust your router
wifi-tracker trusted-gateways                # List trusted gateways
wifi-tracker mark-safe HomeWiFi firefox      # Mark app as safe
wifi-tracker mark-safe HomeWiFi firefox --always  # Always safe
wifi-tracker safe-apps                       # List trusted apps
wifi-tracker kill-app HomeWiFi malware       # Kill an app
wifi-tracker kill-app HomeWiFi malware --always   # Auto-kill on limit
wifi-tracker kill-list                       # List auto-kill apps
```

### Management

```bash
wifi-tracker stop                            # Stop the daemon
wifi-tracker cleanup                         # Clean data older than 90 days
wifi-tracker cleanup 30                      # Clean data older than 30 days
wifi-tracker install-service                 # Install systemd service
wifi-tracker remove-service                  # Remove systemd service
```

## Project Structure

- `wifi_tracker_modules/`:
  - `__init__.py`: Package initializer.
  - `cli.py`: CLI argument parsing and main entry point.
  - `config.py`: XDG-compliant path configuration.
  - `data_manager.py`: Handles data persistence and validation.
  - `network_monitor.py`: Monitors network interfaces and collects stats.
  - `process_manager.py`: Manages processes and daemon operations.
  - `display_manager.py`: Handles display formatting and output.
  - `notification_manager.py`: Handles system notifications.
- `completions/`: Shell completions for bash, zsh, and fish.
- `tests/`: Unit tests.

## Requirements

- Python 3.12+
- Linux with wireless tools (`iwconfig`, `iwgetid`)
- `psutil` and `rich` libraries (installed automatically).

## Data Storage

Data follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/):

- Usage data: `~/.local/share/wifi-tracker/wifi_usage.json`
- Limits: `~/.local/share/wifi-tracker/wifi_limits.json`
- Logs: `~/.cache/wifi-tracker/daemon.log`

## Contributing

Feel free to submit issues or pull requests on GitHub.

## License

See [LICENSE.md](LICENSE.md) for details.
