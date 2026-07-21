"""
App Manager Module for WiFi Tracker
Handles app detection and connection tracking.
"""

from datetime import datetime

from .alert_manager import AlertManager
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
        """Check for apps exceeding the configured usage threshold and notify."""
        try:
            settings = self.data_manager.get_alert_settings()
            threshold = settings["threshold_bytes"]
            window = settings["window_hours"]

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

            high_apps = self.data_manager.get_high_usage_apps(ssid, threshold, window)
            for app in high_apps:
                name = app["name"]
                total = app["total_bytes"]
                if self.data_manager.is_safe_app(ssid, name):
                    continue
                if name not in notified:
                    notified.add(name)
                    total_str = self.display_manager.format_bytes(total)
                    notifier.send_notification(
                        "High App Usage",
                        f"'{name}' used {total_str} on {ssid} in "
                        f"{AlertManager.format_window(window)}.",
                        Urgency.NORMAL,
                    )
        except Exception as e:
            self.process_manager._log_error(f"Error checking high usage apps: {e}")
