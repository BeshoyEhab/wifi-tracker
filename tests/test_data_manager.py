import json
import shutil

# Import modules to test
# We need to add project root to path relative to tests/
import sys
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(self.data_manager.usage_data[ssid]["total_rx"], 1000)  # Unchanged

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

    def test_blocked_gateways_empty_by_default(self):
        """Test that blocked gateways list is empty for new SSID"""
        self.assertEqual(self.data_manager.get_blocked_gateways("TestWiFi"), [])

    def test_add_and_check_blocked_gateway(self):
        """Test adding and checking a blocked gateway"""
        ssid = "TestWiFi"
        ip = "192.168.1.1"
        mac = "AA:BB:CC:DD:EE:FF"

        self.data_manager.add_blocked_gateway(ssid, ip, mac, "TP-Link")

        self.assertTrue(self.data_manager.is_blocked_gateway(ssid, ip, mac))
        self.assertTrue(self.data_manager.is_blocked_gateway(ssid, ip))
        self.assertTrue(self.data_manager.is_blocked_gateway(ssid, ip, "XX:YY:ZZ"))

    def test_blocked_gateway_no_duplicates(self):
        """Test that adding the same blocked gateway twice doesn't duplicate"""
        ssid = "TestWiFi"
        ip = "192.168.1.1"

        self.data_manager.add_blocked_gateway(ssid, ip, "AA:BB:CC:DD:EE:FF")
        self.data_manager.add_blocked_gateway(ssid, ip, "AA:BB:CC:DD:EE:FF")

        blocked = self.data_manager.get_blocked_gateways(ssid)
        self.assertEqual(len(blocked), 1)

    def test_remove_blocked_gateway(self):
        """Test removing a blocked gateway"""
        ssid = "TestWiFi"
        ip = "192.168.1.1"

        self.data_manager.add_blocked_gateway(ssid, ip, "AA:BB:CC:DD:EE:FF")
        self.assertTrue(self.data_manager.remove_blocked_gateway(ssid, ip))

        self.assertFalse(self.data_manager.is_blocked_gateway(ssid, ip))
        self.assertEqual(len(self.data_manager.get_blocked_gateways(ssid)), 0)

    def test_remove_blocked_gateway_not_found(self):
        """Test removing a non-existent blocked gateway returns False"""
        result = self.data_manager.remove_blocked_gateway("TestWiFi", "10.0.0.1")
        self.assertFalse(result)

    def test_remove_known_gateway(self):
        """Test removing a trusted gateway"""
        ssid = "TestWiFi"
        ip = "192.168.1.1"

        self.data_manager.add_known_gateway(ssid, ip, "AA:BB:CC:DD:EE:FF")
        self.assertTrue(self.data_manager.remove_known_gateway(ssid, ip))

        self.assertFalse(self.data_manager.is_known_gateway(ssid, ip))

    def test_blocked_gateway_persists_to_disk(self):
        """Test that blocked gateways are saved and loaded from disk"""
        ssid = "TestWiFi"
        ip = "192.168.1.1"

        self.data_manager.add_blocked_gateway(ssid, ip, "AA:BB:CC:DD:EE:FF", "Router")
        self.data_manager.save_data()

        new_manager = DataManager(str(self.data_file))
        new_manager.load_data()

        self.assertTrue(new_manager.is_blocked_gateway(ssid, ip))

    def test_known_and_blocked_independent(self):
        """Test that known and blocked gateway lists are independent"""
        ssid = "TestWiFi"

        self.data_manager.add_known_gateway(ssid, "192.168.1.1", "AA:BB:CC:DD:EE:FF")
        self.data_manager.add_blocked_gateway(ssid, "192.168.1.2", "11:22:33:44:55:66")

        self.assertTrue(self.data_manager.is_known_gateway(ssid, "192.168.1.1"))
        self.assertFalse(self.data_manager.is_known_gateway(ssid, "192.168.1.2"))
        self.assertTrue(self.data_manager.is_blocked_gateway(ssid, "192.168.1.2"))
        self.assertFalse(self.data_manager.is_blocked_gateway(ssid, "192.168.1.1"))

    def test_update_app_usage_first_call_sets_baseline(self):
        """First call to update_app_usage establishes baseline, no entry recorded"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)
        self.data_manager.update_app_usage("TestWiFi", "brave", 0, 10_000, pid=1234)

        entries = self.data_manager.usage_data["TestWiFi"]["app_usage"]["brave"]["entries"]
        self.assertEqual(entries, [])
        pids = self.data_manager.usage_data["TestWiFi"]["app_usage"]["brave"]["pids"]
        self.assertEqual(pids["1234"], {"sent": 0, "recv": 10_000})

    def test_update_app_usage_scale_factors(self):
        """scale_sent/scale_recv are applied to the delta before recording"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)
        self.data_manager.update_app_usage("TestWiFi", "brave", 0, 1_000_000, pid=1234)

        # Delta of 10_000 bytes with scale_recv=0.1 -> 1_000 bytes recorded
        self.data_manager.update_app_usage(
            "TestWiFi", "brave", 0, 1_010_000, pid=1234, scale_sent=1.0, scale_recv=0.1
        )

        entries = self.data_manager.usage_data["TestWiFi"]["app_usage"]["brave"]["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["recv"], 1_000)
        # Next cycle tracks from raw cumulative values, not scaled ones
        self.data_manager.update_app_usage(
            "TestWiFi", "brave", 0, 1_020_000, pid=1234, scale_sent=1.0, scale_recv=0.5
        )
        entries = self.data_manager.usage_data["TestWiFi"]["app_usage"]["brave"]["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["recv"], 5_000)

    def test_compute_app_scale_factors_caps_estimate(self):
        """When the estimate exceeds the real network delta, scale it down"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)
        self.data_manager.update_app_usage("TestWiFi", "brave", 0, 1_000_000, pid=1234)

        apps = [
            {
                "pid": 1234,
                "name": "brave",
                "bytes_sent": 0,
                "bytes_recv": 2_000_000,  # +1_000_000 estimated delta
            }
        ]
        scale_sent, scale_recv = self.data_manager.compute_app_scale_factors(
            "TestWiFi", apps, real_rx_delta=100_000, real_tx_delta=0
        )
        self.assertEqual(scale_sent, 1.0)
        self.assertAlmostEqual(scale_recv, 0.1)

    def test_compute_app_scale_factors_under_estimate_unchanged(self):
        """When the estimate is below the real network delta, no scaling"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)
        self.data_manager.update_app_usage("TestWiFi", "brave", 0, 1_000, pid=1234)

        apps = [
            {
                "pid": 1234,
                "name": "brave",
                "bytes_sent": 0,
                "bytes_recv": 2_000,  # +1_000 estimated delta
            }
        ]
        scale_sent, scale_recv = self.data_manager.compute_app_scale_factors(
            "TestWiFi", apps, real_rx_delta=10_000_000, real_tx_delta=5_000_000
        )
        self.assertEqual((scale_sent, scale_recv), (1.0, 1.0))

    def test_compute_app_scale_factors_first_seen_pid(self):
        """A first-seen PID contributes no estimate, so no scaling kicks in"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)

        apps = [
            {
                "pid": 9999,
                "name": "brave",
                "bytes_sent": 0,
                "bytes_recv": 500_000_000,  # huge cumulative, but never seen before
            }
        ]
        scale_sent, scale_recv = self.data_manager.compute_app_scale_factors(
            "TestWiFi", apps, real_rx_delta=10_000, real_tx_delta=10_000
        )
        self.assertEqual((scale_sent, scale_recv), (1.0, 1.0))

    def test_compute_app_scale_factors_without_real_delta(self):
        """No real delta provided -> no scaling"""
        self.data_manager.update_usage("TestWiFi", 1000, 1000)
        self.data_manager.update_app_usage("TestWiFi", "brave", 0, 1_000_000, pid=1234)

        apps = [
            {
                "pid": 1234,
                "name": "brave",
                "bytes_sent": 0,
                "bytes_recv": 2_000_000,
            }
        ]
        scale_sent, scale_recv = self.data_manager.compute_app_scale_factors("TestWiFi", apps)
        self.assertEqual((scale_sent, scale_recv), (1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
