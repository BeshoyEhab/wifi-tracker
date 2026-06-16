import unittest
import shutil
import json
import tempfile
from pathlib import Path


# Import modules to test
# We need to add project root to path relative to tests/
import sys

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.data_file = Path(self.test_dir) / "wifi_usage.json"
        self.limits_file = Path(self.test_dir) / "wifi_limits.json"

        # Create empty file to prevent legacy migration
        with open(self.data_file, "w") as f:
            json.dump({}, f)
        with open(self.limits_file, "w") as f:
            json.dump({}, f)

        # Initialize DataManager with test file and limits file
        self.data_manager = DataManager(str(self.data_file), str(self.limits_file))

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)

    def test_init_creates_empty_data(self):
        """Test that initializing DataManager creates empty data structures"""
        self.assertEqual(self.data_manager.usage_data, {})
        self.assertEqual(self.data_manager.limits_data, {})

    def test_update_usage_new_ssid(self):
        """Test updating usage for a new SSID"""
        ssid = "TestWiFi"
        rx_bytes = 1000
        tx_bytes = 500

        self.data_manager.update_usage(ssid, rx_bytes, tx_bytes)

        self.assertIn(ssid, self.data_manager.usage_data)
        self.assertEqual(
            self.data_manager.usage_data[ssid]["total_rx"], 0
        )  # First update sets baseline
        self.assertEqual(self.data_manager.usage_data[ssid]["total_tx"], 0)

        # Second update should add usage
        new_rx = 2000
        new_tx = 1000
        self.data_manager.update_usage(ssid, new_rx, new_tx)

        self.assertEqual(self.data_manager.usage_data[ssid]["total_rx"], 1000)
        self.assertEqual(self.data_manager.usage_data[ssid]["total_tx"], 500)

    def test_update_usage_session_reset(self):
        """Test handling of interface counter reset"""
        ssid = "TestWiFi"
        # Initial: 1000, 1000
        self.data_manager.update_usage(ssid, 1000, 1000)

        # Normal update: 2000, 2000 (+1000 each)
        self.data_manager.update_usage(ssid, 2000, 2000)
        self.assertEqual(self.data_manager.usage_data[ssid]["total_rx"], 1000)

        # Reset: 100, 100 (Should be treated as new session, 0 delta)
        self.data_manager.update_usage(ssid, 100, 100)
        self.assertEqual(
            self.data_manager.usage_data[ssid]["total_rx"], 1000
        )  # Unchanged

        # New usage: 200, 200 (+100 each)
        self.data_manager.update_usage(ssid, 200, 200)
        self.assertEqual(self.data_manager.usage_data[ssid]["total_rx"], 1100)

    def test_set_and_get_limit(self):
        """Test setting and retrieving limits"""
        ssid = "LimitedWiFi"
        limit = 1024 * 1024 * 1024  # 1GB

        self.data_manager.set_limit(ssid, limit, "monthly")

        limit_data = self.data_manager.get_limit(ssid)
        self.assertIsNotNone(limit_data)
        self.assertEqual(limit_data["limit"], limit)
        self.assertEqual(limit_data["interval"], "monthly")

    def test_save_and_load_data(self):
        """Test persistence of data"""
        ssid = "PersistWiFi"
        self.data_manager.update_usage(ssid, 1000, 1000)  # Init
        self.data_manager.update_usage(ssid, 2000, 2000)  # +1000
        self.data_manager.save_data()

        # Create new manager hitting same file
        new_manager = DataManager(str(self.data_file))
        new_manager.load_data()

        self.assertIn(ssid, new_manager.usage_data)
        self.assertEqual(new_manager.usage_data[ssid]["total_rx"], 1000)

    def test_get_usage_for_graph_24h(self):
        """Test hourly graph data returns list of (label, bytes) tuples"""
        ssid = "GraphWiFi"
        self.data_manager.update_usage(ssid, 1000, 1000)
        self.data_manager.update_usage(ssid, 2000, 2000)
        result = self.data_manager.get_usage_for_graph(ssid, "24h")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertEqual(len(result[0]), 2)

    def test_get_usage_for_graph_1h(self):
        """Test minute graph data"""
        ssid = "MinuteWiFi"
        self.data_manager.update_usage(ssid, 1000, 1000)
        self.data_manager.update_usage(ssid, 2000, 2000)
        result = self.data_manager.get_usage_for_graph(ssid, "1h")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_usage_for_graph_7d(self):
        """Test daily graph data"""
        ssid = "DayWiFi"
        self.data_manager.update_usage(ssid, 1000, 1000)
        result = self.data_manager.get_usage_for_graph(ssid, "7d")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_usage_for_graph_unknown_ssid(self):
        """Test graph for unknown SSID returns zeros"""
        result = self.data_manager.get_usage_for_graph("Nonexistent", "24h")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0][1], 0)


if __name__ == "__main__":
    unittest.main()
