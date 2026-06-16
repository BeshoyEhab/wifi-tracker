"""
Alert Manager Module for WiFi Tracker
Handles data limit checking, high-usage alerts, and daily summaries.
"""

from datetime import datetime, timedelta
from typing import Optional

from .notification_manager import notifier, Urgency


class AlertManager:
    """Manages data limits, high-usage alerts, and daily summaries."""

    def __init__(self, data_manager, process_manager):
        self.data_manager = data_manager
        self.process_manager = process_manager

    def check_limits(self, ssid: str, current_usage: int) -> None:
        """Check data limits and notify if needed."""
        if ssid not in self.data_manager.limits_data:
            return

        limit_info = self.data_manager.limits_data[ssid]
        limit = limit_info.get("limit", 0)
        if limit <= 0:
            return

        percent = (current_usage / limit) * 100

        if percent >= 100 and not limit_info.get("notified_100", False):
            notifier.send_notification(
                "Data Limit Reached",
                f"You have reached your data limit for {ssid}!",
                Urgency.CRITICAL,
            )
            self.data_manager.update_limit_status(ssid, "notified_100", True)
        elif 80 <= percent < 100 and not limit_info.get("notified_80", False):
            notifier.send_notification(
                "Data Limit Warning",
                f"You have used {percent:.1f}% of your data limit for {ssid}.",
                Urgency.NORMAL,
            )
            self.data_manager.update_limit_status(ssid, "notified_80", True)
        elif percent < 80:
            if limit_info.get("notified_80", False):
                self.data_manager.update_limit_status(ssid, "notified_80", False)
            if limit_info.get("notified_100", False):
                self.data_manager.update_limit_status(ssid, "notified_100", False)

    def get_current_period_usage(self, ssid: str, display_manager) -> int:
        """Get current usage based on limit interval."""
        if ssid not in self.data_manager.limits_data:
            return 0
        interval = self.data_manager.limits_data[ssid].get("interval", "monthly")
        ssid_data = self.data_manager.usage_data.get(ssid, {})
        return display_manager._calculate_period_usage(ssid_data, interval)

    def send_daily_summary(self, ssid: str, display_manager) -> None:
        """Send a daily usage summary notification."""
        try:
            ssid_data = self.data_manager.usage_data.get(ssid, {})
            daily = ssid_data.get("daily", {})
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            day_data = daily.get(yesterday, {})
            rx = day_data.get("rx", 0)
            tx = day_data.get("tx", 0)
            total = rx + tx

            if total > 0:
                rx_str = display_manager.format_bytes(rx)
                tx_str = display_manager.format_bytes(tx)
                total_str = display_manager.format_bytes(total)
                notifier.send_notification(
                    "Daily WiFi Summary",
                    f"{ssid} yesterday:\n"
                    f"  Total: {total_str}\n"
                    f"  Download: {rx_str}\n"
                    f"  Upload: {tx_str}",
                    Urgency.NORMAL,
                )
        except Exception:
            pass

    @staticmethod
    def parse_size(size_str: str) -> Optional[int]:
        """Parse a size string like '1GB', '500MB' into bytes."""
        size_upper = size_str.upper()
        try:
            if size_upper.endswith("GB"):
                return int(float(size_upper[:-2]) * 1024**3)
            elif size_upper.endswith("MB"):
                return int(float(size_upper[:-2]) * 1024**2)
            elif size_upper.endswith("KB"):
                return int(float(size_upper[:-2]) * 1024)
            else:
                return int(size_str)
        except ValueError:
            return None

    @staticmethod
    def parse_threshold(threshold_str: str) -> Optional[int]:
        """Parse a threshold string like '5GB', '500MB' into bytes."""
        t = threshold_str.upper()
        multiplier = 1
        if t.endswith("TB"):
            multiplier = 1024**4
            t = t[:-2]
        elif t.endswith("GB"):
            multiplier = 1024**3
            t = t[:-2]
        elif t.endswith("MB"):
            multiplier = 1024**2
            t = t[:-2]
        elif t.endswith("KB"):
            multiplier = 1024
            t = t[:-2]
        elif t.endswith("B"):
            t = t[:-1]
        try:
            return int(float(t) * multiplier)
        except ValueError:
            return None

    @staticmethod
    def parse_window(window_str: str) -> Optional[float]:
        """Parse a window string like '1h', '30m' into hours."""
        w = window_str.lower()
        try:
            if w.endswith("h"):
                return float(w[:-1])
            elif w.endswith("m"):
                return float(w[:-1]) / 60
            else:
                return float(w)
        except ValueError:
            return None
