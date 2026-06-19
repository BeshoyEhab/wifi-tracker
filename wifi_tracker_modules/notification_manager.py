"""
Notification Manager Module for WiFi Tracker
Handles system notifications using notify-send.sh, zenity, or plain notify-send
"""

import shutil
import subprocess
import time
from enum import Enum


class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    CRITICAL = "critical"


class NotificationManager:
    """Manages system notifications with interactive action buttons"""

    def __init__(self):
        self._check_dependency()
        self.quiet = False

    def _check_dependency(self):
        """Check available notification tools"""
        self.notify_send = shutil.which("notify-send") is not None
        self.notify_send_sh = shutil.which("notify-send.sh") is not None
        self.zenity = shutil.which("zenity") is not None

    def send_notification(
        self, title: str, message: str, urgency: Urgency = Urgency.NORMAL
    ) -> bool:
        """Send a plain desktop notification (no buttons)."""
        if self.quiet:
            return False
        if not self.notify_send:
            return False
        try:
            subprocess.run(
                [
                    "notify-send",
                    "--app-name=WiFi Tracker",
                    f"--urgency={urgency.value}",
                    title,
                    message,
                ],
                check=True,
                capture_output=True,
            )
            return True
        except Exception:
            return False

    def _ask_with_notify_send_sh(
        self, title: str, body: str, actions: dict, timeout: int = 60
    ) -> str:
        """
        Ask user via notify-send.sh. Retries until timeout or user clicks.
        actions: {label: command, ...}  e.g. {"Trust": "wifi-tracker trust-gateway ..."}
        Returns the label clicked, or "" on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                cmd = [
                    "notify-send.sh",
                    "--urgency=critical",
                    "--app-name=WiFi Tracker",
                ]
                for label, command in actions.items():
                    cmd.append(f"--action={label}:{command}")
                cmd += [title, body]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                choice = result.stdout.strip()
                if choice:
                    return choice
                time.sleep(2)
            except Exception:
                return ""
        return ""

    def _ask_with_zenity(
        self, title: str, body: str, options: list, timeout: int = 60
    ) -> str:
        """
        Ask user via zenity --list. Retries until timeout.
        options: [(TRUE/FALSE, value, label), ...]
        Returns the value selected, or "" on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                cmd = [
                    "zenity",
                    "--list",
                    f"--title={title}",
                    f"--text={body}\n\nWhat would you like to do?",
                    "--column=Select",
                    "--column=Action",
                    "--column=Description",
                    "--radiolist",
                    "--ok-label=Apply",
                    "--cancel-label=Ignore",
                    "--width=450",
                    "--height=300",
                ]
                for selected, value, label in options:
                    cmd += [selected, value, label]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    choice = result.stdout.strip()
                    if choice:
                        return choice
                # Cancelled or closed = return ""
                return ""
            except Exception:
                return ""
        return ""

    def ask_gateway_trust(
        self, ssid: str, gateway_ip: str, mac: str = "", vendor: str = ""
    ) -> str:
        """
        Ask user whether to trust an unknown gateway.
        Returns: "trust", "block", or "ignored"
        """
        if self.quiet:
            return "ignored"
        mac_info = f"\nMAC: {mac}" if mac else ""
        vendor_info = f"\nVendor: {vendor}" if vendor else ""
        body = f"New gateway on {ssid}:\nIP: {gateway_ip}{mac_info}{vendor_info}"
        trust_cmd = f'wifi-tracker trust-gateway "{ssid}" {gateway_ip}'

        # Use notify-send.sh (preferred) or zenity, never both
        if self.notify_send_sh:
            actions = {
                "Trust": trust_cmd,
                "Block": "true",
            }
            choice = self._ask_with_notify_send_sh(
                "Unknown Gateway Detected", body, actions, timeout=60
            )
            if choice == "Trust":
                return "trust"
            elif choice == "Block":
                return "block"
            return "ignored"

        if self.zenity:
            options = [
                ("TRUE", "trust", "Trust Once"),
                ("FALSE", "block", "Block"),
            ]
            choice = self._ask_with_zenity(
                "Unknown Gateway Detected", body, options, timeout=60
            )
            if choice == "trust":
                return "trust"
            elif choice == "block":
                return "block"
            return "ignored"

        # Fallback: plain notification
        self.send_notification(
            "Unknown Gateway Detected",
            f"{body}\nRun: {trust_cmd}",
            Urgency.CRITICAL,
        )
        return "ignored"

    def ask_high_usage_action(
        self, ssid: str, app_name: str, size: str, window: str
    ) -> str:
        """
        Ask user what to do about a high-usage app.
        Returns: "safe_once", "safe_always", "kill_once", "kill_always", or "ignored"
        """
        if self.quiet:
            return "ignored"
        body = f"{app_name} used {size} in {window}!"
        safe_once_cmd = f"wifi-tracker mark-safe {ssid} {app_name}"
        safe_always_cmd = f"wifi-tracker mark-safe {ssid} {app_name} --always"
        kill_once_cmd = f"wifi-tracker kill-app {ssid} {app_name}"
        kill_always_cmd = f"wifi-tracker kill-app {ssid} {app_name} --always"

        # Use notify-send.sh (preferred) or zenity, never both
        if self.notify_send_sh:
            actions = {
                "Safe once": safe_once_cmd,
                "Safe always": safe_always_cmd,
                "Kill once": kill_once_cmd,
                "Kill always": kill_always_cmd,
            }
            choice = self._ask_with_notify_send_sh(
                "High Data Usage Alert", body, actions, timeout=60
            )
            mapping = {
                "Safe once": "safe_once",
                "Safe always": "safe_always",
                "Kill once": "kill_once",
                "Kill always": "kill_always",
            }
            if choice in mapping:
                return mapping[choice]
            return "ignored"

        if self.zenity:
            options = [
                ("TRUE", "safe_once", "Mark safe (once)"),
                ("FALSE", "safe_always", "Mark safe (always)"),
                ("FALSE", "kill_once", "Kill now (once)"),
                ("FALSE", "kill_always", "Kill now (always)"),
            ]
            choice = self._ask_with_zenity(
                "High Data Usage Alert", body, options, timeout=60
            )
            if choice in ("safe_once", "safe_always", "kill_once", "kill_always"):
                return choice
            return "ignored"

        # Fallback: plain notification
        self.send_notification(
            "High Data Usage Alert",
            f"{body}\nSafe: {safe_once_cmd}\nKill: {kill_once_cmd}",
            Urgency.CRITICAL,
        )
        return "ignored"


# Global instance for easy access
notifier = NotificationManager()
