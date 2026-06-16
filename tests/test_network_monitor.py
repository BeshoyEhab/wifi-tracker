import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import subprocess

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.network_monitor import NetworkMonitor


class TestNetworkMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = NetworkMonitor("wlan0")

    @patch("subprocess.run")
    def test_get_ssid_success(self, mock_run):
        """Test getting SSID successfully"""
        # Mock successful iwgetid result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "TestWiFi"
        mock_run.return_value = mock_result

        ssid = self.monitor.get_current_ssid()
        self.assertEqual(ssid, "TestWiFi")

    @patch("subprocess.run")
    def test_get_ssid_failure(self, mock_run):
        """Test getting SSID failure"""
        # Create a mock CalledProcessError
        error = subprocess.CalledProcessError(1, ["iwgetid"])
        mock_run.side_effect = error

        ssid = self.monitor.get_current_ssid()
        self.assertIsNone(ssid)

    @patch("builtins.open")
    def test_get_interface_stats(self, mock_open):
        """Test reading interface statistics"""
        # Mock /proc/net/dev content
        # Format: interface: bytes packets errs drop fifo frame compressed multicast ...
        # wlan0: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
        mock_file = MagicMock()
        mock_file.__enter__.return_value = [
            "Inter-|   Receive                                                |  Transmit",
            " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed",
            "  wlan0:    1000      10    0    0    0     0          0         0     2000      20    0    0    0     0       0          0",
        ]
        mock_open.return_value = mock_file

        stats = self.monitor.get_interface_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats["rx_bytes"], 1000)
        self.assertEqual(stats["tx_bytes"], 2000)

    @patch("builtins.open")
    def test_get_interface_stats_error(self, mock_open):
        """Test reading interface statistics error"""
        mock_open.side_effect = FileNotFoundError("File not found")

        stats = self.monitor.get_interface_stats()
        self.assertIsNone(stats)


if __name__ == "__main__":
    unittest.main()
