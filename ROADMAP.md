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
- [ ] Unit tests for `alert_manager.py` (limit checking, size parsing)
- [ ] Unit tests for `app_manager.py` (app detection, tracking)
- [ ] Unit tests for `config.py` (XDG paths)
- [ ] Integration test: full daemon cycle (start → collect → stop)
- [x] Add `--json` flag for machine-readable output
- [x] Add `--quiet` flag to suppress notifications
- [x] Add `--version` flag
- [ ] Publish to PyPI

## v0.2.0 — Code Quality & Project Hygiene
- [x] Add ruff config to `pyproject.toml` — rules, exclusions, line length, per-file overrides
- [x] Add pytest config to `pyproject.toml` — test path, markers, options
- [x] Add `tests/__init__.py` — proper package recognition
- [x] Add `conftest.py` — shared fixtures (temp dirs, mock data, mock interfaces)
- [x] Add `py.typed` marker — PEP 561 compliance for type checkers
- [x] Add mypy/pyright config to `pyproject.toml` — enforce type correctness
- [x] Add `SECURITY.md` — vulnerability reporting policy (critical: project has MITM/rogue detection features)
- [x] Add `.editorconfig` — cross-editor consistency
- [x] Fix duplicate entries in `.gitignore` (lines 1-3 and 33-35 are identical)
- [x] Add CONTRIBUTING.md guidance on running pre-commit hooks and CI-equivalent checks locally

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
