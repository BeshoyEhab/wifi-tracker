# Roadmap to v1.0.0

## v0.1.0 — Public Release (Current)
- [x] Core monitoring (rates, session, lifetime)
- [x] Daemon mode with systemd support
- [x] Watch mode with Rich dashboard
- [x] Data limits (daily/weekly/monthly)
- [x] High-usage alerts
- [x] Top apps detection + auto-kill
- [x] MITM/rogue gateway detection
- [x] Shell completions (bash/zsh/fish)
- [x] Desktop notifications
- [x] ASCII usage graph
- [x] XDG Base Directory compliance
- [x] GitHub Actions CI
- [x] README with demo GIF
- [x] CHANGELOG, CONTRIBUTING, pre-commit hooks

## v0.2.0 — Test Coverage & Polish
- [ ] Unit tests for `cli.py` (arg parsing, subcommands)
- [ ] Unit tests for `display_manager.py` (formatting, graph)
- [ ] Unit tests for `process_manager.py` (daemon, PID)
- [ ] Unit tests for `notification_manager.py`
- [ ] Unit tests for `config.py` (XDG paths)
- [ ] Integration test: full daemon cycle (start → collect → stop)
- [ ] Add `--json` flag for machine-readable output
- [ ] Add `--quiet` flag to suppress notifications
- [ ] Add `--version` flag
- [ ] Publish to PyPI

## v0.3.0 — User-Requested Features
Based on GitHub issues and community feedback. Possible additions:
- Export data to CSV/JSON
- Multiple interface monitoring
- macOS support (if requested)
- Config file (`~/.config/wifi-tracker/config.toml`)
- Custom thresholds per network
- Weekly/monthly summary reports
- Battery impact warnings for laptop users

## v1.0.0 — Stable Release
- [ ] 80%+ test coverage
- [ ] All v0.2.0 and v0.3.0 features stable
- [ ] No open critical bugs
- [ ] Documentation complete
- [ ] Published on PyPI
- [ ] 30+ GitHub stars (community validation)

## Versioning

Following [Semantic Versioning](https://semver.org/):
- **0.x** — API may change between minor versions
- **1.0** — Stable public API, backward-compatible changes only
