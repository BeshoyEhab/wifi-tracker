"""
App Manager Module for WiFi Tracker
Handles app detection and connection tracking.
"""

from datetime import datetime

from .config import Config
from .notification_manager import Urgency, notifier


class AppManager:
    """Manages app detection and connection tracking."""

    def __init__(self, data_manager, process_manager, display_manager):
        self.data_manager = data_manager
        self.process_manager = process_manager
        self.display_manager = display_manager

    def check_new_apps(self, ssid: str, known_apps: set[str]) -> None:
        """Alert when a new app first accesses the network."""
        try:
            top_apps = self.process_manager.get_top_network_apps(limit=20, ssid=ssid)
            for app in top_apps:
                app_name = app.get("name", "unknown")
                if app_name not in known_apps:
                    known_apps.add(app_name)
                    if len(known_apps) > Config.NEW_APP_THRESHOLD:
                        notifier.send_notification(
                            "New App Detected",
                            f"'{app_name}' just accessed {ssid}",
                            Urgency.NORMAL,
                        )
        except Exception:
            pass

    def check_high_usage_apps(self, ssid: str, notified: set[str]) -> None:
        """Record app connection data for historical tracking.

        Per-app bytes are approximated via (rchar - read_bytes) from
        /proc/{pid}/io, which filters out disk I/O and gives mostly
        network bytes. Interface-level alerts via AlertManager still
        provide the most accurate total usage.
        """
        try:
            top_apps = self.process_manager.get_top_network_apps(limit=20, ssid=ssid)
            now = datetime.now()
            for app in top_apps:
                if app.get("pid", 0) == 0:
                    continue
                self.data_manager.update_app_usage(
                    ssid,
                    app.get("name", "unknown"),
                    app.get("bytes_sent", 0),
                    app.get("bytes_recv", 0),
                    now,
                    pid=app.get("pid", 0),
                )
        except Exception as e:
            self.process_manager._log_error(f"Error checking high usage apps: {e}")
