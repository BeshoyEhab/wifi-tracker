"""
Data Manager Module for WiFi Tracker
Handles data persistence, validation, and management
"""

import json
import shutil
import fcntl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

from wifi_tracker_modules.config import Config


class DataManager:
    """
    Manages WiFi usage data persistence and validation.

    Attributes:
        data_file (Path): Path to the main usage data JSON file.
        limits_file (Path): Path to the limits data JSON file.
        usage_data (Dict): In-memory storage of usage data.
        limits_data (Dict): In-memory storage of limits data.
    """

    def __init__(
        self, data_file: Optional[str] = None, limits_file: Optional[str] = None
    ):
        """
        Initialize the Data Manager.

        Args:
            data_file (str, optional): Path to the WiFi usage data file.
            limits_file (str, optional): Path to the data limits file.
        """
        self.data_file = Path(data_file) if data_file else Config.get_data_file()
        self.limits_file = (
            Path(limits_file) if limits_file else Config.get_limits_file()
        )

        # Check for legacy data and migrate if needed
        self._check_and_migrate_legacy_data()

        # Initialize data structures
        self.usage_data = {}
        self.limits_data = {}
        self._metadata = {}  # Track cleanup and other metadata
        self._alert_settings = {
            "threshold_bytes": 5 * 1024**3,  # 5GB default
            "window_hours": 1,               # 1 hour default
        }

        # Load existing data
        self.load_data()
        self.load_limits()
        self._load_alert_settings()

    def _check_and_migrate_legacy_data(self) -> None:
        """
        Check for legacy data in ~/.cache and migrate to new XDG location if found.
        Only migrates if the new data file doesn't already exist.
        """
        if self.data_file.exists():
            return

        legacy_data = Path.home() / ".cache" / "wifi_usage.json"
        legacy_limits = Path.home() / ".cache" / "wifi_limits.json"

        if legacy_data.exists():
            print(f"📦 Migrating data from {legacy_data} to {self.data_file}...")
            try:
                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(legacy_data), str(self.data_file))
                if legacy_limits.exists():
                    shutil.move(str(legacy_limits), str(self.limits_file))
                print("✅ Migration successful")
            except Exception as e:
                print(f"❌ Migration failed: {e}")

    def load_data(self) -> Dict[str, Any]:
        """
        Load usage data from file with validation and migration.

        Returns:
            Dict[str, Any]: The loaded usage data.
        """
        try:
            if self.data_file.exists():
                with open(self.data_file, "r") as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)

                if "_metadata" in data:
                    self._metadata = data["_metadata"]
                    del data["_metadata"]
                else:
                    self._metadata = {}

                self.usage_data = self._validate_and_migrate_data(data)
            else:
                self.usage_data = {}
                self._metadata = {}

        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Warning: Could not load data file: {e}")
            self.usage_data = {}
            self._metadata = {}

        return self.usage_data

    def load_limits(self) -> Dict[str, Any]:
        """
        Load limits data from file with file locking.

        Returns:
            Dict[str, Any]: The loaded limits data.
        """
        try:
            if self.limits_file.exists():
                with open(self.limits_file, "r") as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        self.limits_data = json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            else:
                self.limits_data = {}

        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Warning: Could not load limits file: {e}")
            self.limits_data = {}

        return self.limits_data

    def save_data(self) -> bool:
        """
        Save usage data to file with file locking.

        Returns:
            bool: True if save was successful, False otherwise.
        """
        try:
            if self.data_file.exists():
                backup_file = self.data_file.with_suffix(".json.bak")
                try:
                    shutil.copy2(self.data_file, backup_file)
                except OSError:
                    pass

            data_to_save = self.usage_data.copy()
            data_to_save["_metadata"] = self._metadata

            with open(self.data_file, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    json.dump(data_to_save, f, indent=2, default=str)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            return True

        except (PermissionError, OSError) as e:
            print(f"Error saving data: {e}")
            return False

    def save_limits(self) -> bool:
        """
        Save limits data to file with file locking.

        Returns:
            bool: True if save was successful, False otherwise.
        """
        try:
            with open(self.limits_file, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    json.dump(self.limits_data, f, indent=2)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return True

        except (PermissionError, OSError) as e:
            print(f"Error saving limits: {e}")
            return False

    def _load_alert_settings(self) -> None:
        """Load alert settings from metadata."""
        saved = self._metadata.get("alert_settings", {})
        if "threshold_bytes" in saved:
            self._alert_settings["threshold_bytes"] = saved["threshold_bytes"]
        if "window_hours" in saved:
            self._alert_settings["window_hours"] = saved["window_hours"]

    def set_alert_settings(self, threshold_bytes: Optional[int] = None, window_hours: Optional[int] = None) -> None:
        """
        Configure high-usage alert threshold and time window.

        Args:
            threshold_bytes: Usage threshold in bytes. None keeps current value.
            window_hours: Time window in hours. None keeps current value.
        """
        if threshold_bytes is not None:
            self._alert_settings["threshold_bytes"] = threshold_bytes
        if window_hours is not None:
            self._alert_settings["window_hours"] = window_hours
        self._metadata["alert_settings"] = self._alert_settings
        self.save_data()

    def get_alert_settings(self) -> Dict[str, Any]:
        """Get current alert settings."""
        return self._alert_settings.copy()

    # --- Gateway management ---

    def get_known_gateways(self, ssid: str) -> List[Dict[str, Any]]:
        """Get known safe gateways for an SSID."""
        if ssid not in self.usage_data:
            return []
        return self.usage_data[ssid].get("known_gateways", [])

    def is_known_gateway(self, ssid: str, gateway_ip: str, gateway_mac: Optional[str] = None) -> bool:
        """Check if a gateway is already marked as safe."""
        known = self.get_known_gateways(ssid)
        for gw in known:
            if gw.get("ip") == gateway_ip:
                if gateway_mac and gw.get("mac"):
                    return gw["mac"] == gateway_mac
                return True
        return False

    def add_known_gateway(self, ssid: str, gateway_ip: str, gateway_mac: Optional[str] = None,
                          vendor: Optional[str] = None) -> None:
        """Mark a gateway as safe for an SSID."""
        if ssid not in self.usage_data:
            self.usage_data[ssid] = {}
        gateways = self.usage_data[ssid].setdefault("known_gateways", [])
        # Don't add duplicates
        for gw in gateways:
            if gw.get("ip") == gateway_ip:
                return
        gateways.append({
            "ip": gateway_ip,
            "mac": gateway_mac,
            "vendor": vendor,
            "added": datetime.now().isoformat(),
        })
        self.save_data()

    def remove_known_gateway(self, ssid: str, gateway_ip: str) -> bool:
        """Remove a gateway from the safe list."""
        if ssid not in self.usage_data:
            return False
        gateways = self.usage_data[ssid].get("known_gateways", [])
        for i, gw in enumerate(gateways):
            if gw.get("ip") == gateway_ip:
                gateways.pop(i)
                self.save_data()
                return True
        return False

    # --- App safe-list and kill-list ---

    def is_safe_app(self, ssid: str, app_name: str) -> bool:
        """Check if an app is marked as safe (won't trigger alert or kill)."""
        if ssid not in self.usage_data:
            return False
        ssid_data = self.usage_data[ssid]
        if app_name in ssid_data.get("safe_apps", []):
            return True
        if app_name in ssid_data.get("safe_apps_onetime", []):
            return True
        return False

    def consume_safe_onetime(self, ssid: str, app_name: str) -> None:
        """Remove app from one-time safe list after use."""
        if ssid not in self.usage_data:
            return
        one_time = self.usage_data[ssid].get("safe_apps_onetime", [])
        if app_name in one_time:
            one_time.remove(app_name)
            self.save_data()

    def mark_app_safe(self, ssid: str, app_name: str, always: bool = False) -> None:
        """Mark an app as safe for an SSID.

        Args:
            ssid: Network SSID.
            app_name: Process/command name.
            always: If True, permanent. If False, one-time (consumed on next match).
        """
        if ssid not in self.usage_data:
            self.usage_data[ssid] = {}
        if always:
            safe_apps = self.usage_data[ssid].setdefault("safe_apps", [])
            if app_name not in safe_apps:
                safe_apps.append(app_name)
        else:
            safe_onetime = self.usage_data[ssid].setdefault("safe_apps_onetime", [])
            if app_name not in safe_onetime:
                safe_onetime.append(app_name)
        self.save_data()

    def is_kill_app(self, ssid: str, app_name: str) -> bool:
        """Check if an app should be auto-killed when exceeding limits."""
        if ssid not in self.usage_data:
            return False
        ssid_data = self.usage_data[ssid]
        if app_name in ssid_data.get("kill_apps", []):
            return True
        if app_name in ssid_data.get("kill_apps_onetime", []):
            return True
        return False

    def consume_kill_onetime(self, ssid: str, app_name: str) -> None:
        """Remove app from one-time kill list after use."""
        if ssid not in self.usage_data:
            return
        one_time = self.usage_data[ssid].get("kill_apps_onetime", [])
        if app_name in one_time:
            one_time.remove(app_name)
            self.save_data()

    def mark_app_kill(self, ssid: str, app_name: str, always: bool = False) -> None:
        """Mark an app to be killed when exceeding limits.

        Args:
            ssid: Network SSID.
            app_name: Process/command name.
            always: If True, permanent. If False, one-time (consumed on next match).
        """
        if ssid not in self.usage_data:
            self.usage_data[ssid] = {}
        if always:
            kill_apps = self.usage_data[ssid].setdefault("kill_apps", [])
            if app_name not in kill_apps:
                kill_apps.append(app_name)
        else:
            kill_onetime = self.usage_data[ssid].setdefault("kill_apps_onetime", [])
            if app_name not in kill_onetime:
                kill_onetime.append(app_name)
        self.save_data()

    def kill_app(self, app_name: str) -> int:
        """Kill all processes with the given name. Returns number killed."""
        import psutil as _psutil
        killed = 0
        for proc in _psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == app_name:
                    proc.kill()
                    killed += 1
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue
        return killed

    def _validate_and_migrate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and migrate data structure for backward compatibility.

        Args:
            data (Dict[str, Any]): The raw loaded data.

        Returns:
            Dict[str, Any]: Validated and structured data.
        """
        validated_data = {}

        for ssid, ssid_data in data.items():
            if not isinstance(ssid_data, dict):
                continue

            # Initialize validated SSID data
            validated_ssid = {
                "total_rx": ssid_data.get("total_rx", 0),
                "total_tx": ssid_data.get("total_tx", 0),
                "first_seen": ssid_data.get("first_seen", datetime.now().isoformat()),
                "last_seen": ssid_data.get("last_seen", datetime.now().isoformat()),
                "connection_count": ssid_data.get("connection_count", 1),
                "daily": ssid_data.get("daily", {}),
                "sessions": ssid_data.get("sessions", []),
                "peak_rx_rate": ssid_data.get("peak_rx_rate", 0),
                "peak_tx_rate": ssid_data.get("peak_tx_rate", 0),
                "last_interface_rx": ssid_data.get("last_interface_rx", 0),
                "last_interface_tx": ssid_data.get("last_interface_tx", 0),
                "session_start_rx": ssid_data.get("session_start_rx", 0),
                "session_start_tx": ssid_data.get("session_start_tx", 0),
                "gateway_ip": ssid_data.get("gateway_ip"),
                "app_usage": ssid_data.get("app_usage", {}),
                "known_gateways": ssid_data.get("known_gateways", []),
                "safe_apps": ssid_data.get("safe_apps", []),
                "safe_apps_onetime": ssid_data.get("safe_apps_onetime", []),
                "kill_apps": ssid_data.get("kill_apps", []),
                "kill_apps_onetime": ssid_data.get("kill_apps_onetime", []),
                "accuracy_stats": ssid_data.get(
                    "accuracy_stats",
                    {
                        "total_measurements": 0,
                        "successful_measurements": 0,
                        "last_accuracy_check": datetime.now().isoformat(),
                        "accuracy_score": 1.0,
                    },
                ),
            }

            # Validate daily data structure - preserve all fields
            validated_daily = {}
            for date, daily_data in validated_ssid["daily"].items():
                if isinstance(daily_data, dict):
                    validated_daily[date] = {
                        "rx": daily_data.get("rx", 0),
                        "tx": daily_data.get("tx", 0),
                        "sessions": daily_data.get("sessions", 0),
                        "first_connection": daily_data.get("first_connection"),
                        "last_connection": daily_data.get("last_connection"),
                        "date": daily_data.get("date"),
                        "peak_rx_rate": daily_data.get("peak_rx_rate", 0),
                        "peak_tx_rate": daily_data.get("peak_tx_rate", 0),
                        "connection_duration": daily_data.get("connection_duration", 0),
                        "data_points": daily_data.get("data_points", 0),
                        "hourly": daily_data.get("hourly", {}),
                    }

            validated_ssid["daily"] = validated_daily
            validated_data[ssid] = validated_ssid

        return validated_data

    def update_usage(
        self,
        ssid: str,
        rx_bytes: int,
        tx_bytes: int,
        timestamp: Optional[datetime] = None,
        rx_rate: float = 0,
        tx_rate: float = 0,
        gateway_ip: Optional[str] = None,
    ) -> None:
        """
        Update usage data for a specific SSID using delta-based tracking.

        Args:
            ssid (str): The SSID name.
            rx_bytes (int): Current total RX bytes from interface.
            tx_bytes (int): Current total TX bytes from interface.
            timestamp (datetime, optional): Measurement timestamp. Defaults to now.
            rx_rate (float, optional): Current download rate. Defaults to 0.
            tx_rate (float, optional): Current upload rate. Defaults to 0.
        """
        if timestamp is None:
            timestamp = datetime.now()

        today = timestamp.strftime("%Y-%m-%d")

        # Auto-cleanup old data (90 days) once per day
        self._auto_cleanup_if_needed()

        # Initialize SSID data if not exists
        if ssid not in self.usage_data:
            self.usage_data[ssid] = {
                "total_rx": 0,
                "total_tx": 0,
                "first_seen": timestamp.isoformat(),
                "last_seen": timestamp.isoformat(),
                "connection_count": 1,
                "daily": {},
                "sessions": [],
                "peak_rx_rate": 0,
                "peak_tx_rate": 0,
                "last_interface_rx": rx_bytes,
                "last_interface_tx": tx_bytes,
                "session_start_rx": rx_bytes,
                "session_start_tx": tx_bytes,
                "gateway_ip": gateway_ip,
                "app_usage": {},
                "accuracy_stats": {
                    "total_measurements": 0,
                    "successful_measurements": 0,
                    "last_accuracy_check": timestamp.isoformat(),
                    "accuracy_score": 1.0,
                },
            }
        else:
            # Ensure fields exist (for backward compatibility)
            ssid_data = self.usage_data[ssid]
            for field, default in [
                ("peak_rx_rate", 0),
                ("peak_tx_rate", 0),
                ("gateway_ip", None),
                ("app_usage", {}),
            ]:
                if field not in ssid_data:
                    ssid_data[field] = default
            # Update gateway IP if we have one
            if gateway_ip:
                ssid_data["gateway_ip"] = gateway_ip

        ssid_data = self.usage_data[ssid]

        # Calculate deltas from last measurement
        last_rx = ssid_data.get("last_interface_rx", rx_bytes)
        last_tx = ssid_data.get("last_interface_tx", tx_bytes)

        # Handle interface counter resets (when current < last)
        if rx_bytes < last_rx or tx_bytes < last_tx:
            # Interface counters were reset (e.g. interface restart, system reboot).
            # We cannot know how much traffic occurred between the last measurement
            # and the reset, so that traffic is permanently lost.
            # Log the event and start fresh from the new counter values.
            lost_rx = max(0, last_rx)
            lost_tx = max(0, last_tx)
            print(
                f"[WARN] Interface counter reset detected for {ssid}. "
                f"Lost ~{lost_rx + lost_tx} bytes of unrecorded traffic."
            )

            # Start new session tracking from the reset point
            ssid_data["session_start_rx"] = rx_bytes
            ssid_data["session_start_tx"] = tx_bytes
            rx_delta = 0
            tx_delta = 0
        else:
            # Normal case: calculate deltas
            rx_delta = rx_bytes - last_rx
            tx_delta = tx_bytes - last_tx

        # Update totals with deltas
        ssid_data["total_rx"] += rx_delta
        ssid_data["total_tx"] += tx_delta
        ssid_data["last_seen"] = timestamp.isoformat()

        # Update interface tracking
        ssid_data["last_interface_rx"] = rx_bytes
        ssid_data["last_interface_tx"] = tx_bytes

        # Initialize daily data if not exists for today
        if today not in ssid_data["daily"]:
            ssid_data["daily"][today] = {
                "rx": 0,
                "tx": 0,
                "sessions": 0,
                "first_connection": timestamp.isoformat(),
                "last_connection": timestamp.isoformat(),
                "date": today,
                "peak_rx_rate": 0,
                "peak_tx_rate": 0,
                "connection_duration": 0,
                "data_points": 0,
                "hourly": {},
            }

        # Get daily data and update it
        daily_data = ssid_data["daily"][today]
        daily_data["rx"] = daily_data.get("rx", 0) + rx_delta
        daily_data["tx"] = daily_data.get("tx", 0) + tx_delta
        daily_data["last_connection"] = timestamp.isoformat()

        # Track hourly data for graph fallback
        hour_key = timestamp.strftime("%H")
        hourly = daily_data.setdefault("hourly", {})
        hourly[hour_key] = hourly.get(hour_key, 0) + rx_delta + tx_delta

        # Safely update peak rates
        current_peak_rx = daily_data.get("peak_rx_rate", 0) or 0
        current_peak_tx = daily_data.get("peak_tx_rate", 0) or 0
        daily_data["peak_rx_rate"] = max(current_peak_rx, rx_rate)
        daily_data["peak_tx_rate"] = max(current_peak_tx, tx_rate)

        # Update data points counter
        daily_data["data_points"] = daily_data.get("data_points", 0) + 1

        # Update accuracy stats
        accuracy_stats = ssid_data["accuracy_stats"]
        accuracy_stats["total_measurements"] += 1
        accuracy_stats["successful_measurements"] += 1
        accuracy_stats["last_accuracy_check"] = timestamp.isoformat()

        # Calculate accuracy score (simple heuristic)
        if accuracy_stats["total_measurements"] > 0:
            accuracy_stats["accuracy_score"] = min(
                1.0,
                accuracy_stats["successful_measurements"]
                / accuracy_stats["total_measurements"],
            )

    def get_session_usage(self, ssid: str, current_rx: int, current_tx: int) -> tuple:
        """
        Get current session usage for an SSID.

        Args:
            ssid (str): The SSID name.
            current_rx (int): Current interface RX bytes.
            current_tx (int): Current interface TX bytes.

        Returns:
            tuple: (session_rx, session_tx) usage in bytes.
        """
        if ssid not in self.usage_data:
            return 0, 0

        ssid_data = self.usage_data[ssid]
        session_start_rx = ssid_data.get("session_start_rx", current_rx)
        session_start_tx = ssid_data.get("session_start_tx", current_tx)

        # Calculate session usage (current interface stats - session start)
        session_rx = max(0, current_rx - session_start_rx)
        session_tx = max(0, current_tx - session_start_tx)

        return session_rx, session_tx

    def update_app_usage(
        self, ssid: str, app_name: str, bytes_sent: int, bytes_recv: int,
        timestamp: Optional[datetime] = None, pid: int = 0
    ) -> None:
        """
        Track per-app network usage with a rolling 1-hour window.
        Stores DELTAS (usage since last check), not cumulative values.
        Tracks by PID to handle multiple processes with the same name.

        Args:
            ssid: The SSID name.
            app_name: Process/command name.
            bytes_sent: Cumulative bytes sent by this app (from /proc/pid/io).
            bytes_recv: Cumulative bytes received by this app (from /proc/pid/io).
            timestamp: Current timestamp.
            pid: Process ID for accurate delta tracking.
        """
        if ssid not in self.usage_data:
            return

        if timestamp is None:
            timestamp = datetime.now()

        ssid_data = self.usage_data[ssid]
        app_usage = ssid_data.setdefault("app_usage", {})

        if app_name not in app_usage:
            app_usage[app_name] = {"entries": [], "pids": {}}

        app_data = app_usage[app_name]
        entries = app_data["entries"]
        pids = app_data.setdefault("pids", {})
        cutoff = timestamp - timedelta(days=90)
        cutoff_iso = cutoff.isoformat()

        # Remove entries older than 90 days
        entries[:] = [e for e in entries if e.get("ts", "") > cutoff_iso]

        # Track delta per PID
        pid_key = str(pid)
        pids.setdefault(pid_key, {"sent": 0, "recv": 0})
        prev_sent = pids[pid_key]["sent"]
        prev_recv = pids[pid_key]["recv"]

        # First time seeing this PID: save baseline, don't record entry
        if prev_sent == 0 and prev_recv == 0 and pid > 0:
            pids[pid_key] = {"sent": bytes_sent, "recv": bytes_recv}
            return

        delta_sent = max(0, bytes_sent - prev_sent)
        delta_recv = max(0, bytes_recv - prev_recv)

        # Handle counter reset (process restarted)
        if bytes_sent < prev_sent or bytes_recv < prev_recv:
            delta_sent = bytes_sent
            delta_recv = bytes_recv

        # Save current cumulative for this PID
        pids[pid_key] = {"sent": bytes_sent, "recv": bytes_recv}

        # Only add entry if there was actual usage
        if delta_sent > 0 or delta_recv > 0:
            entries.append({
                "ts": timestamp.isoformat(),
                "sent": delta_sent,
                "recv": delta_recv,
            })

    def get_high_usage_apps(self, ssid: str, threshold_bytes: int = 5 * 1024**3, window_hours: int = 1) -> List[Dict[str, Any]]:
        """
        Get apps that exceed a data usage threshold within a time window.

        Args:
            ssid: The SSID name.
            threshold_bytes: Usage threshold in bytes (default 5GB).
            window_hours: Time window in hours (default 1).

        Returns:
            List of dicts with app name and usage info.
        """
        if ssid not in self.usage_data:
            return []

        app_usage = self.usage_data[ssid].get("app_usage", {})
        high_apps = []
        now = datetime.now()
        cutoff = now - timedelta(hours=window_hours)
        cutoff_iso = cutoff.isoformat()

        for app_name, data in app_usage.items():
            entries = data.get("entries", [])
            total_sent = 0
            total_recv = 0
            for entry in entries:
                if entry.get("ts", "") > cutoff_iso:
                    total_sent += entry.get("sent", 0)
                    total_recv += entry.get("recv", 0)

            total = total_sent + total_recv
            if total >= threshold_bytes:
                high_apps.append({
                    "name": app_name,
                    "bytes_sent": total_sent,
                    "bytes_recv": total_recv,
                    "total_bytes": total,
                })

        return sorted(high_apps, key=lambda x: x["total_bytes"], reverse=True)

    def get_app_usage_range(
        self,
        ssid: str,
        app_name: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get app usage entries for any time range.

        Args:
            ssid: The SSID name.
            app_name: Specific app name, or None for all apps.
            start: Start of time range (default: 24h ago).
            end: End of time range (default: now).

        Returns:
            Dict with app_name -> {entries, total_sent, total_recv, total}.
        """
        if ssid not in self.usage_data:
            return {}

        now = datetime.now()
        if start is None:
            start = now - timedelta(hours=24)
        if end is None:
            end = now

        start_iso = start.isoformat()
        end_iso = end.isoformat()

        app_usage = self.usage_data[ssid].get("app_usage", {})
        result = {}

        for name, data in app_usage.items():
            if app_name and name != app_name:
                continue

            entries = data.get("entries", [])
            filtered = [
                e for e in entries
                if start_iso <= e.get("ts", "") <= end_iso
            ]

            total_sent = sum(e.get("sent", 0) for e in filtered)
            total_recv = sum(e.get("recv", 0) for e in filtered)

            result[name] = {
                "entries": filtered,
                "total_sent": total_sent,
                "total_recv": total_recv,
                "total": total_sent + total_recv,
            }

        return result

    def get_hourly_usage_for_graph(
        self, ssid: str, hours: int = 24
    ) -> list:
        """
        Get hourly usage data for the graph, built from app_usage entries.

        Args:
            ssid: The SSID name.
            hours: Number of hours to look back (default 24).

        Returns:
            List of (hour_label, bytes_used) tuples.
        """
        now = datetime.now()
        hourly = []

        for h in range(hours, 0, -1):
            ts = now - timedelta(hours=h)
            hour_start = ts.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)

            total = 0
            if ssid in self.usage_data:
                app_usage = self.usage_data[ssid].get("app_usage", {})
                for data in app_usage.values():
                    for entry in data.get("entries", []):
                        entry_ts = entry.get("ts", "")
                        if hour_start.isoformat() <= entry_ts < hour_end.isoformat():
                            total += entry.get("sent", 0) + entry.get("recv", 0)

                # Fall back to daily hourly data if no app_usage entries
                if total == 0:
                    day_key = ts.strftime("%Y-%m-%d")
                    hour_key = ts.strftime("%H")
                    daily = self.usage_data[ssid].get("daily", {})
                    day_data = daily.get(day_key, {})
                    total = day_data.get("hourly", {}).get(hour_key, 0)

            hourly.append((ts.strftime("%H:%M"), total))

        return hourly

    def get_networks(self) -> List[Dict[str, Any]]:
        """Get all saved networks with their gateway IPs and SSIDs."""
        networks = []
        for ssid, data in self.usage_data.items():
            if ssid.startswith("_"):
                continue
            networks.append({
                "ssid": ssid,
                "gateway_ip": data.get("gateway_ip"),
                "total_rx": data.get("total_rx", 0),
                "total_tx": data.get("total_tx", 0),
                "last_seen": data.get("last_seen"),
            })
        return networks

    def get_usage_summary(self, ssid: str = "") -> Dict[str, Any]:
        """
        Get usage summary for specific SSID or all SSIDs.

        Args:
            ssid (str, optional): Specific SSID to summarize. Defaults to None (all SSIDs).

        Returns:
            Dict[str, Any]: Summary dictionary.
        """
        if ssid:
            return self.usage_data.get(ssid, {})

        # Return summary for all SSIDs
        summary = {}
        total_rx = total_tx = 0

        for ssid_name, ssid_data in self.usage_data.items():
            summary[ssid_name] = {
                "total_usage": ssid_data["total_rx"] + ssid_data["total_tx"],
                "total_rx": ssid_data["total_rx"],
                "total_tx": ssid_data["total_tx"],
                "connection_count": ssid_data["connection_count"],
                "first_seen": ssid_data["first_seen"],
                "last_seen": ssid_data["last_seen"],
            }
            total_rx += ssid_data["total_rx"]
            total_tx += ssid_data["total_tx"]

        summary["_totals"] = {
            "total_rx": total_rx,
            "total_tx": total_tx,
            "total_usage": total_rx + total_tx,
            "ssid_count": len(self.usage_data),
        }

        return summary

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """
        Clean up old daily data beyond specified days.

        Args:
            days_to_keep (int, optional): Number of days to keep. Defaults to 30.

        Returns:
            int: Number of day records removed.
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        removed_count = 0

        for ssid, ssid_data in self.usage_data.items():
            if "daily" in ssid_data:
                dates_to_remove = []
                for date in ssid_data["daily"].keys():
                    if date < cutoff_str:
                        dates_to_remove.append(date)

                for date in dates_to_remove:
                    del ssid_data["daily"][date]
                    removed_count += 1

        # Update last cleanup timestamp
        if not hasattr(self, "_metadata"):
            self._metadata = {}
        self._metadata["last_cleanup"] = datetime.now().isoformat()

        return removed_count

    def _auto_cleanup_if_needed(self) -> None:
        """
        Automatically cleanup old data if it's been more than a day since last cleanup.
        """
        if not hasattr(self, "_metadata"):
            self._metadata = {}

        last_cleanup_str = self._metadata.get("last_cleanup")

        # Check if we need to run cleanup (once per day)
        should_cleanup = False
        if not last_cleanup_str:
            should_cleanup = True
        else:
            try:
                last_cleanup = datetime.fromisoformat(last_cleanup_str)
                # Run cleanup if it's been more than 24 hours
                if datetime.now() - last_cleanup > timedelta(hours=24):
                    should_cleanup = True
            except ValueError:
                should_cleanup = True

        if should_cleanup:
            removed_count = self.cleanup_old_data(90)  # Keep 90 days of data
            if removed_count > 0:
                print(
                    f"🧹 Auto-cleanup: Removed {removed_count} old daily records (>90 days)"
                )
                self.save_data()  # Save after cleanup

    def update_limit_status(self, ssid: str, key: str, value: Any) -> None:
        """
        Update a specific status flag for an SSID limit.

        Args:
            ssid (str): The SSID to update.
            key (str): The status key (e.g., 'notified_80').
            value (Any): The value to set.
        """
        if ssid in self.limits_data:
            self.limits_data[ssid][key] = value
            self.save_limits()

    def set_limit(
        self,
        ssid: str,
        limit_bytes: int,
        interval: str = "monthly",
        usage_from: str = None,
    ) -> None:
        """
        Set data limit for specific SSID.

        Args:
            ssid (str): SSID to set limit for.
            limit_bytes (int): Limit in bytes.
            interval (str, optional): Interval ('daily', 'weekly', 'monthly'). Defaults to 'monthly'.
            usage_from (str, optional): Custom start date for usage calculation (YYYY-MM-DD).
        """
        if ssid in self.limits_data:
            self.limits_data[ssid]["limit"] = limit_bytes
            self.limits_data[ssid]["interval"] = interval
            # Reset notification flags when limit changes
            self.limits_data[ssid]["notified_80"] = False
            self.limits_data[ssid]["notified_100"] = False
            if usage_from:
                self.limits_data[ssid]["usage_from"] = usage_from
        else:
            self.limits_data[ssid] = {
                "limit": limit_bytes,
                "interval": interval,
                "created": datetime.now().isoformat(),
                "notified_80": False,
                "notified_100": False,
            }
            if usage_from:
                self.limits_data[ssid]["usage_from"] = usage_from
        self.save_limits()

    def get_limit(self, ssid: str) -> Optional[Dict[str, Any]]:
        """
        Get data limit for specific SSID.

        Args:
            ssid (str): SSID to get limit for.

        Returns:
            Optional[Dict[str, Any]]: Limit data or None.
        """
        return self.limits_data.get(ssid)

    def remove_limit(self, ssid: str) -> bool:
        """
        Remove data limit for specific SSID.

        Args:
            ssid (str): SSID to remove limit for.

        Returns:
            bool: True if limit was removed, False if not found.
        """
        if ssid in self.limits_data:
            del self.limits_data[ssid]
            self.save_limits()
            return True
        return False
