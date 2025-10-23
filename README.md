# WiFi Tracker

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

1. Clone or download the repository.
2. Run the installation script:
   ```bash
   ./install.sh
   ```
3. Source your shell config or restart your terminal:
    ```bash
    source ~/.bashrc  # or ~/.zshrc, or for Fish: source ~/.config/fish/config.fish
    ```

The script will:
- Detect your shell (bash or zsh).
- Make the `wifi-tracker` script executable.
- Copy it to `~/.local/share/bin`.
- Add the directory to your PATH.

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

### Options

- `--interface` or `-i`: Specify network interface (auto-detected if not provided).
- `--interval`: Update interval in seconds (default: 0.5).

## Project Structure

- `wifi-tracker`: Main executable script.
- `wifi_tracker_modules/`:
  - `__init__.py`: Package initializer.
  - `data_manager.py`: Handles data persistence and validation.
  - `network_monitor.py`: Monitors network interfaces and collects stats.
  - `process_manager.py`: Manages processes and daemon operations.
  - `display_manager.py`: Handles display formatting and output.

## Requirements

- Python 3.6+
- Linux with wireless tools (`iwconfig`, `iwgetid`)
- `psutil` library (install via `pip install psutil`)

## Data Storage

- Usage data is stored in `~/.cache/wifi_usage.json`.
- Limits are stored in `~/.cache/wifi_limits.json`.
- Logs are in `~/.cache/wifi-tracker_*.log`.

## Contributing

Feel free to submit issues or pull requests on GitHub.

## License

See [LICENSE.md](LICENSE.md) for details.