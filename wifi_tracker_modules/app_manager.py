"""
App Manager Module for WiFi Tracker
Handles app detection, high-usage alerts, safe/kill lists.
"""

from datetime import datetime
from typing import Set

from .notification_manager import notifier, Urgency


class AppManager:
    """Manages app detection, safe lists, and kill lists."""

    def __init__(self, data_manager, process_manager, display_manager):
        self.data_manager = data_manager
        self.process_manager = process_manager
        self.display_manager = display_manager

    def check_new_apps(self, ssid: str, known_apps: Set[str]) -> None:
        """Alert when a new app first accesses the network."""
        try:
            top_apps = self.process_manager.get_top_network_apps(limit=20, ssid=ssid)
            for app in top_apps:
                app_name = app.get("name", "unknown")
                if app_name not in known_apps:
                    known_apps.add(app_name)
                    if len(known_apps) > 5:
                        notifier.send_notification(
                            "New App Detected",
                            f"'{app_name}' just accessed {ssid}",
                            Urgency.NORMAL,
                        )
        except Exception:
            pass

    def check_high_usage_apps(self, ssid: str, notified: Set[str]) -> None:
        """Check for apps exceeding the configured data usage threshold."""
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
                app_name = app["name"]
                total_bytes = app["total_bytes"]

                if self.data_manager.is_safe_app(ssid, app_name):
                    self.data_manager.consume_safe_onetime(ssid, app_name)
                    continue

                if self.data_manager.is_kill_app(ssid, app_name):
                    self.data_manager.consume_kill_onetime(ssid, app_name)
                    killed = self.data_manager.kill_app(app_name)
                    if killed:
                        self.process_manager._log_info(
                            f"Auto-killed {app_name} ({killed} processes) for exceeding limit on {ssid}"
                        )
                    continue

                if app_name in notified:
                    continue

                size = self.display_manager.format_bytes(total_bytes)
                window_msg = f"{window}h" if window >= 1 else f"{round(window * 60)}m"

                choice = notifier.ask_high_usage_action(ssid, app_name, size, window_msg)

                if choice == "safe_once":
                    self.data_manager.mark_app_safe(ssid, app_name, always=False)
                    self.process_manager._log_info(f"User marked {app_name} as safe (once) on {ssid}")
                elif choice == "safe_always":
                    self.data_manager.mark_app_safe(ssid, app_name, always=True)
                    self.process_manager._log_info(f"User marked {app_name} as safe (always) on {ssid}")
                elif choice == "kill_once":
                    killed = self.data_manager.kill_app(app_name)
                    self.data_manager.mark_app_kill(ssid, app_name, always=False)
                    self.process_manager._log_info(f"User killed {app_name} ({killed} procs) on {ssid}")
                elif choice == "kill_always":
                    killed = self.data_manager.kill_app(app_name)
                    self.data_manager.mark_app_kill(ssid, app_name, always=True)
                    self.process_manager._log_info(f"User killed {app_name} ({killed} procs, always) on {ssid}")
                else:
                    self.process_manager._log_info(f"High usage alert for {app_name} ({size}) on {ssid} - ignored")

                notified.add(app_name)

        except Exception as e:
            self.process_manager._log_error(f"Error checking high usage apps: {e}")
