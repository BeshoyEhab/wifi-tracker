# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.3] - 2026-07-31

### Added
- Accurate per-app network tracking via a root conntrack collector (`perapp`
  subcommand). The collector runs as a systemd system service, parses
  `/proc/net/nf_conntrack`, and writes a cumulative per-app snapshot to
  `/run/wifi-tracker/per_app.json` (mode 0644) that the user daemon reads.
  High-usage alerts and `top-apps` now prefer this data.
- `perapp install` / `perapp remove` / `perapp status` commands. Install and
  remove auto-elevate via `sudo` with `PYTHONDONTWRITEBYTECODE=1`, so the tool's
  uv install directory never accumulates root-owned `__pycache__` files that
  would block `uv tool install`.

### Changed
- Per-app estimates from `/proc/pid/io` (the fallback path) are now scaled so
  their sum never exceeds the real interface delta. The old `rchar - read_bytes`
  approximation overcounted browser traffic (page cache, IPC) by ~30x, which
  produced false high-usage alerts (e.g. "Brave used 1GB in 1 minute").
- Daemon shutdown signals now set a flag that the main loop honors instead of
  calling cleanup/`sys.exit()` inside the signal handler, avoiding blocking I/O
  during logout/shutdown.
- User systemd service gains `TimeoutStopSec=10` and `KillMode=process`.
- CI updated to Node 24 based actions (`actions/checkout@v5`,
  `actions/setup-python@v6`), removing the Node 20 deprecation warning.
- Shell completions are now fully dynamic. The completion handlers in `cli.py`
  were refactored into a decorator-registered table (`_completer(...)`), and the
  fish completion script now delegates every suggestion to
  `wifi-tracker --complete ...` like bash/zsh already did — no more hardcoded
  `complete -c` lines that can drift out of date with the CLI.

### Fixed
- zsh completions returned columnar (space-padded) output that the completion
  script split on newlines, producing garbage suggestions. `--complete zsh` now
  emits one suggestion per line (like fish). Regression tests added in
  `tests/test_completions.py`.

### Added
- `tests/test_cli.py` (31 tests): `WiFiTracker` command handlers (limit,
  remove-limit, usage-from, cleanup, alert, stop, top-apps, perapp, networks)
  and `main()` subcommand dispatch incl. alias resolution.
- `tests/test_process_manager.py` (20 tests): PID file lifecycle, instance
  discovery, instance killing, systemd install/remove, process info, and top
  network apps. Overall coverage improved from 48% to 58%.

## [0.1.2] - 2026-07-23

### Fixed
- `today` command now reports actual today consumption (midnight→now) instead of
  the last 24h rolling window, so the daily limit percentage is semantically correct
- `today` command now displays the mean transfer rate (daily total ÷ seconds elapsed)
  instead of the instantaneous rate (which was 0 when the daemon was not running)

## [0.1.1] - 2025-06-20

### Added
- High-usage app alerts with per-PID delta tracking via `/proc/pid/io`
- Interactive notify-send.sh/zenity dialogs for gateway trust/block and high-usage actions
- App safe list (`mark-safe`) and auto-kill list (`kill-app`) per SSID
- Gateway trust/untrust/block/unblock CLI commands
- `--json` flag for machine-readable output on `status` and `today`
- `--quiet` flag to suppress desktop notifications
- `--version` flag
- Shell completions for `--range`, `--from-date`, `--to-date`, SSID names, and app names
- Fish shell completions

### Fixed
- Gateway notification spam (deduplication per daemon session)
- Subprocess race condition in gateway trust/block commands
- Interface counter reset detection (large time gaps, sleep/resume)
- Gateway matching by IP only (ignore MAC changes)
- One-shot notification sending (no retry loops)

## [0.1.0] - 2025-06-16

### Added
- Real-time WiFi usage monitoring with live upload/download rates
- Daemon mode with double-fork daemonization and systemd support
- Watch mode with interactive Rich terminal dashboard
- Data limits (daily/weekly/monthly) per SSID with 80%/100% threshold warnings
- High-usage alerts with configurable bandwidth threshold and time window
- Top network apps detection via `/proc/pid/io`
- MITM/rogue gateway detection with OUI vendor lookup
- ASCII usage graph with multi-range support (1h, 24h, 7d, 30d, 12m)
- Per-minute usage tracking for 1h graph granularity
- Desktop notifications via `notify-send`, `notify-send.sh`, or `zenity`
- Interactive gateway trust/block prompts
- App safe list and auto-kill list per SSID
- Shell completions for bash, zsh, and fish
- XDG Base Directory compliance for all data paths
- Automatic data cleanup (90 days)
- Legacy data migration from `~/.cache/` to XDG locations
- Data backup on save (`.json.bak`)
- `install.sh` script for easy installation with completions
- GitHub Actions CI (lint, format check, test, build)
