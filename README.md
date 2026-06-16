# WiFi Tracker

[![CI](https://github.com/Bisho/wifi-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Bisho/wifi-tracker/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.md)

A comprehensive tool for monitoring WiFi usage with daemon support, real-time statistics, and data limits.

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

### Basic Commands

- **Start Daemon Mode** (background monitoring):

  ```bash
  wifi-tracker --daemon
  ```

- **Watch Mode** (interactive display):

  ```bash
  wifi-tracker --watch
  ```

- **Show Status** (current statistics):

  ```bash
  wifi-tracker --status
  ```

- **Stop Daemon**:

  ```bash
  wifi-tracker --stop
  ```

- **Set Data Limit** (e.g., 1GB monthly for "MyWiFi"):

  ```bash
  wifi-tracker --limit MyWiFi 1GB monthly
  ```

- **Remove Limit**:

  ```bash
  wifi-tracker --remove-limit MyWiFi
  ```

- **View All Statistics** (last 90 days):

  ```bash
  wifi-tracker --status-all
  ```

- **Top Network Apps**:

  ```bash
  wifi-tracker --top-apps
  ```

- **Clean Old Data** (e.g., older than 30 days):

  ```bash
  wifi-tracker --cleanup 30
  ```

- **Install/Remove Service (Systemd)**:

  ```bash
  wifi-tracker --install-service
  wifi-tracker --remove-service
  ```

### Options

- `--interface` or `-i`: Specify network interface (auto-detected if not provided).
- `--interval`: Update interval in seconds (default: 0.5).

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
