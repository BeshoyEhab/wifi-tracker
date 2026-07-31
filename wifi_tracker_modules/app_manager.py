"""
App Manager Module for WiFi Tracker
Handles app detection and connection tracking.
"""

from datetime import datetime

from . import perapp
from .alert_manager import AlertManager
from .config import Config
from .notification_manager import Urgency, notifier


class AppManager:
    """Manages app detection and connection tracking."""

    def __init__(self, data_manager, process_manager, display_manager):
        self.data_manager = data_manager
        self.process_manager = process_manager
        self.display_manager = display_manager
        self._collector_prev: dict[str, dict[str, int]] | None = None

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

    def check_high_usage_apps(
        self,
        ssid: str,
        notified: set[str],
        real_rx_delta: int | None = None,
        real_tx_delta: int | None = None,
    ) -> None:
        """Check for apps exceeding the configured usage threshold and notify."""
        try:
            settings = self.data_manager.get_alert_settings()
            threshold = settings["threshold_bytes"]
            window = settings["window_hours"]

            now = datetime.now()

            # Prefer accurate per-app data from the root conntrack collector
            # when available; fall back to the /proc/{pid}/io heuristic.
            collector_used = self._record_from_collector(ssid, now)

            if not collector_used:
                top_apps = self.process_manager.get_top_network_apps(limit=20, ssid=ssid)

                # Scale per-app estimates so they never exceed the real network
                # delta (the /proc/{pid}/io heuristic overcounts for browsers).
                scale_sent, scale_recv = self.data_manager.compute_app_scale_factors(
                    ssid, top_apps, real_rx_delta, real_tx_delta
                )

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
                        scale_sent=scale_sent,
                        scale_recv=scale_recv,
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

    def _record_from_collector(self, ssid: str, now: datetime) -> bool:
        """
        Record usage from the root conntrack collector snapshot.

        The collector writes cumulative per-app byte counts; compute the
        delta since the previous check and store it. Returns True when the
        collector data was used.
        """
        snapshot = perapp.read_snapshot()
        if not snapshot:
            return False
        apps = snapshot.get("apps") or {}
        if not apps:
            return False

        deltas: dict[str, dict[str, int]] = {}
        prev = self._collector_prev
        for name, cur in apps.items():
            sent = cur.get("sent", 0)
            recv = cur.get("recv", 0)
            if not prev or name not in prev:
                continue
            prev_app = prev[name]
            prev_sent = prev_app.get("sent", 0)
            prev_recv = prev_app.get("recv", 0)
            if sent < prev_sent or recv < prev_recv:
                delta_sent, delta_recv = sent, recv
            else:
                delta_sent, delta_recv = sent - prev_sent, recv - prev_recv
            if delta_sent or delta_recv:
                deltas[name] = {"sent": delta_sent, "recv": delta_recv}

        self._collector_prev = {name: dict(counts) for name, counts in apps.items()}
        if deltas:
            self.data_manager.record_app_deltas(ssid, deltas, now)
        return True
