# Contributing to WiFi Tracker

Thanks for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/wifi-tracker.git
   cd wifi-tracker
   ```
3. Create a branch:
   ```bash
   git checkout -b my-feature
   ```

## Development Setup

```bash
pip install psutil rich pytest ruff
```

## Making Changes

- Follow existing code style (no comments unless asked)
- Run the linter before committing:
  ```bash
  ruff check .
  ```
- Run tests:
  ```bash
  python -m pytest tests/
  ```
- Make sure both pass before submitting a PR

## Pull Requests

- Keep PRs focused on one change
- Write a clear description of what changed and why
- Reference any related issues

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS and Python version

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
