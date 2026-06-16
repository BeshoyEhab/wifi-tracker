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
        """Parse a size string like '1GB', '500M', '1T' into bytes.

        Accepts: TB/T, GB/G, MB/M, KB/K, B, or raw bytes.
        """
        size_upper = size_str.upper().strip()
        try:
            if size_upper.endswith("TB") or size_upper.endswith("T"):
                num = size_upper[:-2] if size_upper.endswith("TB") else size_upper[:-1]
                return int(float(num) * 1024**4)
            elif size_upper.endswith("GB") or size_upper.endswith("G"):
                num = size_upper[:-2] if size_upper.endswith("GB") else size_upper[:-1]
                return int(float(num) * 1024**3)
            elif size_upper.endswith("MB") or size_upper.endswith("M"):
                num = size_upper[:-2] if size_upper.endswith("MB") else size_upper[:-1]
                return int(float(num) * 1024**2)
            elif size_upper.endswith("KB") or size_upper.endswith("K"):
                num = size_upper[:-2] if size_upper.endswith("KB") else size_upper[:-1]
                return int(float(num) * 1024)
            elif size_upper.endswith("B"):
                return int(float(size_upper[:-1]) * 1)
            else:
                return int(float(size_str))
        except ValueError:
            return None

    @staticmethod
    def parse_window(window_str: str) -> Optional[float]:
        """Parse a window string like '1h', '30m', '2d' into hours.

        Accepts: d (days), h (hours), m (minutes), or raw hours.
        """
        w = window_str.lower().strip()
        try:
            if w.endswith("d"):
                return float(w[:-1]) * 24
            elif w.endswith("h"):
                return float(w[:-1])
            elif w.endswith("m"):
                return float(w[:-1]) / 60
            else:
                return float(w)
        except ValueError:
            return None

    @staticmethod
    def format_window(hours: float) -> str:
        """Format a time window in hours into a human-readable string.

        - >= 24h: shows days and hours (e.g. '2d 6h')
        - >= 1h: shows hours and minutes (e.g. '3h 30m')
        - < 1h: shows minutes (e.g. '45m')
        """
        if hours >= 24:
            days = int(hours // 24)
            remaining_hours = hours % 24
            if remaining_hours > 0 and remaining_hours != int(remaining_hours):
                h = int(remaining_hours)
                m = int((remaining_hours - h) * 60)
                return f"{days}d {h}h {m}m"
            elif remaining_hours > 0:
                return f"{days}d {int(remaining_hours)}h"
            else:
                return f"{days}d"
        elif hours >= 1:
            h = int(hours)
            m = int((hours - h) * 60)
            if m > 0:
                return f"{h}h {m}m"
            else:
                return f"{h}h"
        else:
            minutes = round(hours * 60)
            return f"{minutes}m"
