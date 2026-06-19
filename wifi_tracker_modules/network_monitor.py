"""
Network Monitor Module for WiFi Tracker
Handles network interface monitoring and data collection
"""

import re
import subprocess
import time
from datetime import datetime
from typing import Any


class NetworkMonitor:
    """Monitors network interfaces and collects usage statistics"""

    def __init__(self, interface: str | None = None, interval: float = 0.5):
        self.interface = interface or self.detect_wireless_interface()
        self.interval = interval
        self.last_measurement: dict[str, Any] | None = None
        self.start_time = time.time()

    def detect_wireless_interface(self) -> str:
        """Auto-detect the active wireless interface"""
        try:
            result = subprocess.run(
                ["iwconfig"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "IEEE 802.11" in line and "no wireless extensions" not in line:
                    interface = line.split()[0]
                    if interface and not interface.startswith("lo"):
                        return interface
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        # Fallback: try common wireless interface names
        for interface in ["wlan0", "wlp1s0", "wlp2s0", "wlo1"]:
            if self._interface_exists(interface):
                return interface

        return "wlan0"  # Default fallback

    def _interface_exists(self, interface: str) -> bool:
        """Check if network interface exists"""
        try:
            with open(f"/sys/class/net/{interface}/operstate") as _:
                return True
        except FileNotFoundError:
            return False

    def get_interface_stats(self) -> dict[str, int] | None:
        """Get current interface statistics"""
        try:
            with open("/proc/net/dev") as f:
                for line in f:
                    if self.interface in line:
                        parts = line.split()
                        return {
                            "rx_bytes": int(parts[1]),
                            "tx_bytes": int(parts[9]),
                            "rx_packets": int(parts[2]),
                            "tx_packets": int(parts[10]),
                        }
        except (FileNotFoundError, ValueError, IndexError):
            pass
        return None

    def get_current_ssid(self) -> str | None:
        """Get currently connected WiFi SSID"""
        try:
            result = subprocess.run(
                ["iwgetid", "-r"], capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        # Alternative method using iwconfig
        try:
            result = subprocess.run(
                ["iwconfig", self.interface], capture_output=True, text=True, timeout=3
            )
            match = re.search(r'ESSID:"([^"]*)"', result.stdout)
            if match:
                ssid = match.group(1)
                return ssid if ssid != "off/any" else None
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        # Alternative method using nmcli
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("yes:"):
                        return line.split(":")[1]
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        return None

    def get_signal_quality(self) -> dict[str, Any]:
        """
        Get WiFi signal quality information.

        Returns:
            Dict[str, Any]: Dictionary containing signal level, quality, link quality, and noise level.
        """
        quality_info = {
            "signal_level": 0,
            "signal_quality": 0,
            "link_quality": 0,
            "noise_level": 0,
        }

        try:
            result = subprocess.run(
                ["iwconfig", self.interface], capture_output=True, text=True, timeout=3
            )
            output = result.stdout

            # Parse signal level
            signal_match = re.search(r"Signal level=(-?\d+)", output)
            if signal_match:
                quality_info["signal_level"] = int(signal_match.group(1))

            # Parse link quality
            quality_match = re.search(r"Link Quality=(\d+)/(\d+)", output)
            if quality_match:
                quality_info["link_quality"] = int(quality_match.group(1))
                quality_info["signal_quality"] = int(quality_match.group(2))

            # Parse noise level
            noise_match = re.search(r"Noise level=(-?\d+)", output)
            if noise_match:
                quality_info["noise_level"] = int(noise_match.group(1))

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        return quality_info

    def calculate_rates(self, current_stats: dict[str, int]) -> tuple[float, float]:
        """
        Calculate download and upload rates based on previous measurement.

        Args:
            current_stats (Dict[str, int]): Current interface statistics (rx_bytes, tx_bytes).

        Returns:
            Tuple[float, float]: (rx_rate, tx_rate) in bytes per second.
        """
        if not self.last_measurement:
            self.last_measurement = {"stats": current_stats, "timestamp": time.time()}
            return 0.0, 0.0

        time_diff = time.time() - self.last_measurement["timestamp"]
        if time_diff <= 0:
            return 0.0, 0.0

        rx_diff = current_stats["rx_bytes"] - self.last_measurement["stats"]["rx_bytes"]
        tx_diff = current_stats["tx_bytes"] - self.last_measurement["stats"]["tx_bytes"]

        # Handle interface counter resets - don't update last_measurement
        if rx_diff < 0 or tx_diff < 0:
            self.last_measurement = {"stats": current_stats, "timestamp": time.time()}
            return 0.0, 0.0

        rx_rate = max(0, rx_diff / time_diff)
        tx_rate = max(0, tx_diff / time_diff)

        self.last_measurement = {"stats": current_stats, "timestamp": time.time()}

        return rx_rate, tx_rate

    def get_measurement(self) -> dict[str, Any] | None:
        """
        Get complete network measurement including stats, SSID, and rates.

        Returns:
            Optional[Dict[str, Any]]: Dictionary with measurement data or None if failed.
        """
        current_ssid = self.get_current_ssid()
        current_stats = self.get_interface_stats()

        if not current_stats:
            return None

        rx_rate, tx_rate = self.calculate_rates(current_stats)
        quality_info = self.get_signal_quality()
        gateway_ip = self.get_gateway_ip()
        gateway_mac = self.get_gateway_mac(gateway_ip)
        vendor = self.get_vendor_from_mac(gateway_mac)

        return {
            "ssid": current_ssid,
            "timestamp": datetime.now(),
            "rx_bytes": current_stats["rx_bytes"],
            "tx_bytes": current_stats["tx_bytes"],
            "rx_rate": rx_rate,
            "tx_rate": tx_rate,
            "signal_quality": quality_info,
            "interface": self.interface,
            "gateway_ip": gateway_ip,
            "gateway_mac": gateway_mac,
            "vendor": vendor,
        }

    def get_gateway_ip(self) -> str | None:
        """Get the default gateway IP address for the current interface."""
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    parts = line.strip().split()
                    if (
                        len(parts) >= 3
                        and parts[0] == self.interface
                        and parts[1] == "00000000"
                    ):
                        gw_hex = parts[2]
                        gw_bytes = bytes.fromhex(gw_hex)
                        gateway = (
                            f"{gw_bytes[3]}.{gw_bytes[2]}.{gw_bytes[1]}.{gw_bytes[0]}"
                        )
                        if gateway != "0.0.0.0":
                            return gateway
        except (FileNotFoundError, ValueError, IndexError):
            pass

        try:
            result = subprocess.run(
                ["ip", "route", "show", "default", "dev", self.interface],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                match = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        return None

    def get_gateway_mac(self, gateway_ip: str | None = None) -> str | None:
        """Get the MAC address of the gateway from the ARP table."""
        if not gateway_ip:
            gateway_ip = self.get_gateway_ip()
        if not gateway_ip:
            return None

        try:
            with open("/proc/net/arp") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[0] == gateway_ip:
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00":
                            return mac.upper()
        except FileNotFoundError:
            pass

        # Fallback: ping the gateway to populate ARP table, then read again
        try:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", gateway_ip],
                capture_output=True,
                timeout=3,
            )
            with open("/proc/net/arp") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[0] == gateway_ip:
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00":
                            return mac.upper()
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        return None

    def get_vendor_from_mac(self, mac: str | None) -> str | None:
        """Look up the hardware vendor from the MAC address OUI prefix."""
        if not mac:
            return None

        # Common router vendor OUIs (first 3 bytes)
        oui_vendors = {
            "00:14:6C": "Netgear",
            "00:1A:2B": "Ayecom",
            "00:1B:2F": "Netgear",
            "00:26:F2": "Netgear",
            "00:9F:52": "D-Link",
            "04:A1:51": "Netgear",
            "08:36:C9": "Ubiquiti",
            "0C:80:63": "TP-Link",
            "10:0C:6B": "Netgear",
            "10:DA:43": "Netgear",
            "14:59:C0": "Netgear",
            "14:91:82": "Belkin",
            "18:E8:29": "Ubiquiti",
            "1C:3B:F3": "Huawei",
            "20:E5:2A": "Netgear",
            "24:05:0F": "Ubiquiti",
            "28:80:88": "Netgear",
            "2C:B0:5D": "Netgear",
            "30:B5:C2": "TP-Link",
            "34:97:F6": "ASUSTek",
            "38:2C:4A": "ASUSTek",
            "3C:37:86": "Netgear",
            "40:4A:03": "ZyXEL",
            "44:94:FC": "Ubiquiti",
            "48:EE:0C": "D-Link",
            "4C:ED:FB": "ASUSTek",
            "50:6A:0F": "Netgear",
            "54:04:A6": "ASUSTek",
            "58:EF:68": "Belkin",
            "5C:CF:7F": "Espressif",
            "60:38:E0": "Belkin",
            "60:A4:4C": "ASUSTek",
            "60:A4:B7": "TP-Link",
            "64:66:B3": "D-Link",
            "64:FF:0A": "TP-Link",
            "68:72:51": "Ubiquiti",
            "6C:B0:CE": "Netgear",
            "70:4D:7B": "ASUSTek",
            "74:AC:B9": "Ubiquiti",
            "78:8A:20": "Ubiquiti",
            "78:8C:B5": "TP-Link",
            "7C:8B:CA": "TP-Link",
            "80:2A:A8": "Ubiquiti",
            "84:1B:5E": "D-Link",
            "88:DC:96": "EnGenius",
            "8C:3B:AD": "Netgear",
            "90:72:40": "Apple",
            "94:10:3E": "Belkin",
            "98:DE:D0": "TP-Link",
            "9C:3D:CF": "Netgear",
            "A0:04:60": "Netgear",
            "A0:20:A6": "Aruba",
            "A0:63:91": "Netgear",
            "A4:2B:8C": "Netgear",
            "A8:5E:45": "ASUSTek",
            "AC:22:05": "TP-Link",
            "AC:84:C6": "TP-Link",
            "B0:4E:26": "TP-Link",
            "B0:7F:B9": "Netgear",
            "B0:BE:76": "TP-Link",
            "B4:0B:44": "ASUSTek",
            "B8:27:EB": "Raspberry Pi",
            "B8:EE:65": "Netgear",
            "BC:EE:7B": "ASUSTek",
            "C0:25:E9": "TP-Link",
            "C0:4A:00": "TP-Link",
            "C4:6E:1F": "TP-Link",
            "C4:71:54": "TP-Link",
            "C8:3A:35": "Tenda",
            "CC:40:D0": "Netgear",
            "D0:21:F9": "Ubiquiti",
            "D4:6E:0E": "TP-Link",
            "D8:07:B6": "TP-Link",
            "D8:50:E6": "ASUSTek",
            "DC:9F:DB": "Ubiquiti",
            "DC:A6:32": "Raspberry Pi",
            "E0:63:DA": "Ubiquiti",
            "E4:F0:04": "Google",
            "E8:94:F6": "TP-Link",
            "EC:08:6B": "TP-Link",
            "F0:9F:C2": "Ubiquiti",
            "F4:EC:38": "TP-Link",
            "F8:1A:67": "TP-Link",
            "FC:EC:DA": "Ubiquiti",
            "FE:ED:FA": "Ubiquiti",
        }

        # Normalize MAC for lookup (use first 8 chars: XX:XX:XX)
        oui = mac[:8] if len(mac) >= 8 else None
        if oui and oui in oui_vendors:
            return oui_vendors[oui]

        return None
