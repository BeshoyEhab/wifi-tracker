# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
- Shell completions for bash, zsh, and fish (including --range, --from-date, --to-date)
- XDG Base Directory compliance for all data paths
- Automatic data cleanup (90 days)
- Legacy data migration from `~/.cache/` to XDG locations
- Data backup on save (`.json.bak`)
- `install.sh` script for easy installation with completions
- GitHub Actions CI (lint, format check, test, build)
