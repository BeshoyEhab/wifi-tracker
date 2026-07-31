"""
Per-app collector integration for WiFi Tracker.

Reads the cumulative per-app snapshot written by the root conntrack
collector (perapp_collector.py) and manages the systemd system service
that runs it. All unprivileged wifi-tracker code should read data via
read_snapshot(); install/remove require root.
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

COLLECTOR_PATH = "/run/wifi-tracker/per_app.json"
COLLECTOR_INSTALL_PATH = "/usr/local/lib/wifi-tracker/perapp_collector.py"
SYSTEMD_SERVICE_PATH = "/etc/systemd/system/wifi-tracker-perapp.service"
SYSCTL_PATH = "/etc/sysctl.d/99-wifi-tracker-perapp.conf"

SERVICE_TEMPLATE = """\
[Unit]
Description=WiFi Tracker per-app network collector
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {collector} --interface {interface}
Restart=on-failure
RestartSec=5
RuntimeDirectory=wifi-tracker
RuntimeDirectoryMode=0755
ProtectSystem=full
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def snapshot_file() -> str:
    """Path to the collector snapshot (overridable via env for testing)."""
    return os.environ.get("WIFI_TRACKER_PERAPP_FILE") or COLLECTOR_PATH


def read_snapshot(max_age: float = 15.0):
    """
    Read the latest collector snapshot if it is fresh.

    Returns a dict like {"timestamp", "interface", "apps": {name: {"sent", "recv"}}}
    or None when missing, stale, or unreadable.
    """
    path = snapshot_file()
    try:
        if time.time() - os.stat(path).st_mtime > max_age:
            return None
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("apps"), dict):
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def _is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def is_root() -> bool:
    """True when running as root (public wrapper)."""
    return _is_root()


def reexec_as_root(action: str, interface: str | None = None) -> None:
    """
    Re-run the current command under sudo with bytecode writes disabled.

    Running the tool itself under sudo makes Python write root-owned
    __pycache__ files into the (user-owned) uv tool install dir, which later
    breaks `uv tool install`. Re-executing via
    `sudo env PYTHONDONTWRITEBYTECODE=1` avoids that. Never returns on success.
    """
    args = [action]
    if interface:
        args += ["--interface", interface]
    cmd = [
        "sudo",
        "env",
        "PYTHONDONTWRITEBYTECODE=1",
        sys.executable,
        "-m",
        "wifi_tracker_modules.cli",
        "perapp",
        *args,
    ]
    try:
        os.execvpe("sudo", cmd, os.environ)
    except OSError as e:
        print(f"Failed to re-exec under sudo: {e}", file=sys.stderr)
        sys.exit(1)


def _exists(path: str) -> bool:
    """Like Path.exists() but never raises (Python 3.13+ propagates EACCES)."""
    try:
        return os.path.exists(path)
    except OSError:
        return False


def install_system_service(interface: str = "") -> tuple[bool, str]:
    """
    Install and start the root collector as a systemd system service.
    Requires root. Returns (ok, message).
    """
    if not _is_root():
        return False, "must run as root (wifi-tracker perapp install auto-elevates via sudo)"

    collector_src = Path(__file__).parent / "perapp_collector.py"
    if not collector_src.exists():
        return False, f"collector not found at {collector_src}"

    try:
        install_dir = Path(COLLECTOR_INSTALL_PATH).parent
        install_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(install_dir, 0o755)
        shutil.copy2(collector_src, COLLECTOR_INSTALL_PATH)
        os.chmod(COLLECTOR_INSTALL_PATH, 0o755)

        Path(SYSTEMD_SERVICE_PATH).write_text(
            SERVICE_TEMPLATE.format(
                collector=COLLECTOR_INSTALL_PATH,
                interface=interface or "auto",
            )
        )

        Path(SYSCTL_PATH).write_text("net.netfilter.nf_conntrack_acct=1\n")
        subprocess.run(["sysctl", "--system"], capture_output=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", "wifi-tracker-perapp"], check=True)
        subprocess.run(["systemctl", "start", "wifi-tracker-perapp"], check=True)
        return True, f"installed and started (interface={interface or 'auto'})"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def remove_system_service() -> tuple[bool, str]:
    """Stop and remove the root collector service. Requires root."""
    if not _is_root():
        return False, "must run as root (wifi-tracker perapp remove auto-elevates via sudo)"

    try:
        subprocess.run(["systemctl", "stop", "wifi-tracker-perapp"], capture_output=True)
        subprocess.run(["systemctl", "disable", "wifi-tracker-perapp"], capture_output=True)
        Path(SYSTEMD_SERVICE_PATH).unlink(missing_ok=True)
        Path(SYSCTL_PATH).unlink(missing_ok=True)
        Path(COLLECTOR_INSTALL_PATH).unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            Path(COLLECTOR_INSTALL_PATH).parent.rmdir()
        with contextlib.suppress(OSError):
            Path(COLLECTOR_PATH).parent.rmdir()
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        return True, "removed"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def collector_status() -> dict:
    """Return a status dict for the `perapp status` command."""
    info: dict[str, object] = {
        "installed": _exists(SYSTEMD_SERVICE_PATH),
        "collector_file": COLLECTOR_INSTALL_PATH if _exists(COLLECTOR_INSTALL_PATH) else None,
        "snapshot_file": snapshot_file(),
    }
    snapshot = read_snapshot(max_age=3600)
    if snapshot:
        info["last_snapshot"] = snapshot.get("timestamp")
        info["tracked_apps"] = len(snapshot.get("apps", {}))
    else:
        info["last_snapshot"] = None
        info["tracked_apps"] = 0
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "wifi-tracker-perapp"],
            capture_output=True,
            text=True,
        )
        info["service_active"] = result.stdout.strip() or "inactive"
    except (subprocess.SubprocessError, OSError):
        info["service_active"] = "unknown"
    return info


def main(argv=None) -> int:
    """Entry point for the perapp subcommand. Returns exit code."""
    action = argv[0] if argv else "status"
    if action in ("install", "remove") and not _is_root():
        reexec_as_root(action, argv[1] if len(argv) > 1 else None)
    if action == "install":
        interface = argv[1] if len(argv) > 1 else ""
        ok, msg = install_system_service(interface)
        print(f"{'OK' if ok else 'FAILED'}: {msg}")
        return 0 if ok else 1
    if action == "remove":
        ok, msg = remove_system_service()
        print(f"{'OK' if ok else 'FAILED'}: {msg}")
        return 0 if ok else 1

    status = collector_status()
    print(f"Installed:      {'yes' if status['installed'] else 'no'}")
    print(f"Service active: {status['service_active']}")
    print(f"Collector file: {status['collector_file'] or 'not installed'}")
    print(f"Last snapshot:  {status['last_snapshot'] or 'never'}")
    print(f"Tracked apps:   {status['tracked_apps']}")
    if not status["installed"]:
        print("Run: wifi-tracker perapp install")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
