# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
