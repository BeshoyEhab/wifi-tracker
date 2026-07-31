import contextlib
import io
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.display_manager import DisplayManager


class TestFormatBytes(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def test_zero(self):
        self.assertEqual(self.dm.format_bytes(0), "0 B")

    def test_bytes(self):
        self.assertEqual(self.dm.format_bytes(500), "500 B")

    def test_kb(self):
        self.assertEqual(self.dm.format_bytes(2048), "2.0 KB")

    def test_mb(self):
        self.assertEqual(self.dm.format_bytes(1024 * 1024 * 5), "5.0 MB")

    def test_gb(self):
        self.assertEqual(self.dm.format_bytes(1024**3 * 10), "10.0 GB")

    def test_tb(self):
        self.assertEqual(self.dm.format_bytes(1024**4 * 2), "2.0 TB")


class TestFormatRate(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def test_rate(self):
        self.assertEqual(self.dm.format_rate(1024), "1.0 KB/s")

    def test_zero_rate(self):
        self.assertEqual(self.dm.format_rate(0), "0 B/s")


class TestFormatDuration(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def test_seconds(self):
        self.assertEqual(self.dm.format_duration(timedelta(seconds=45)), "45s")

    def test_minutes(self):
        self.assertEqual(self.dm.format_duration(timedelta(seconds=125)), "2m 5s")

    def test_hours(self):
        self.assertEqual(self.dm.format_duration(timedelta(seconds=7200 + 180)), "2h 3m")


class TestCalculatePeriodUsage(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def _ssid_data(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return {"daily": {today: {"rx": 1000, "tx": 500}}}

    def test_daily(self):
        usage = self.dm._calculate_period_usage(self._ssid_data(), "daily")
        self.assertEqual(usage, 1500)

    def test_weekly_sums_today(self):
        usage = self.dm._calculate_period_usage(self._ssid_data(), "weekly")
        self.assertEqual(usage, 1500)

    def test_monthly_sums_today(self):
        usage = self.dm._calculate_period_usage(self._ssid_data(), "monthly")
        self.assertEqual(usage, 1500)

    def test_custom_range(self):
        start = datetime.now() - timedelta(days=2)
        end = datetime.now()
        data = {"daily": {datetime.now().strftime("%Y-%m-%d"): {"rx": 10, "tx": 10}}}
        usage = self.dm._calculate_period_usage(data, "monthly", start, end)
        self.assertEqual(usage, 20)


class TestBuildWatchDisplay(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def _args(self, **overrides):
        defaults = {
            "interface": "wlan0",
            "pid": 123,
            "current_time": datetime(2026, 1, 1, 10, 30, 0),
            "uptime": timedelta(hours=1, minutes=5),
            "update_count": 42,
            "current_ssid": "HomeWiFi",
            "last_save_time": 0.0,
            "ssid_data": {"total_rx": 1024, "total_tx": 512},
            "rx_rate": 100.0,
            "tx_rate": 50.0,
            "limits_data": {},
            "interval": 0.5,
            "session_rx": 2048,
            "session_tx": 1024,
        }
        defaults.update(overrides)
        return defaults

    def test_connected_display(self):
        out = self.dm.build_watch_display(**self._args())
        self.assertIn("Network Interface: wlan0", out)
        self.assertIn("Connected to HomeWiFi", out)
        self.assertIn("Session Usage", out)
        self.assertIn("Press Ctrl+C to exit", out)

    def test_disconnected_display(self):
        out = self.dm.build_watch_display(**self._args(current_ssid=None))
        self.assertIn("Disconnected", out)
        self.assertNotIn("Session Usage", out)


class TestPrintAsciiGraph(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def test_empty_data_no_output(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.dm.print_ascii_graph([], "TestWiFi")
        self.assertEqual(buf.getvalue(), "")

    def test_builds_graph_lines(self):
        data = [("00:00", 100), ("01:00", 200)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.dm.print_ascii_graph(data, "TestWiFi", range_label="24h")
        out = buf.getvalue()
        self.assertIn("Usage graph for TestWiFi", out)
        self.assertIn("00:00", out)
        self.assertIn("01:00", out)


class TestPrintQuickStatus(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def capture(self, fn, *args, **kwargs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(*args, **kwargs)
        return buf.getvalue()

    def test_basic_status(self):
        out = self.capture(self.dm.print_quick_status, "HomeWiFi", 1000, 5000, 10.0, 20.0)
        self.assertIn("HomeWiFi", out)
        self.assertIn("Today", out)

    def test_status_with_limit_and_top_app(self):
        out = self.capture(
            self.dm.print_quick_status,
            "HomeWiFi",
            1000,
            5000,
            10.0,
            20.0,
            limit=2000,
            top_app="firefox",
        )
        self.assertIn("Limit: 50%", out)
        self.assertIn("firefox", out)


class TestPrintAppCommands(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def capture(self, fn, *args, **kwargs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(*args, **kwargs)
        return buf.getvalue()

    def test_shows_all_commands_sorted_by_total(self):
        out = self.capture(
            self.dm.print_app_commands,
            "uv",
            {
                "uv sync": {"sent": 1000, "recv": 10000},
                "uv add": {"sent": 2000, "recv": 20000},
            },
        )
        self.assertIn("uv add", out)
        self.assertIn("uv sync", out)
        # uv add total = 22000 -> 21.5 KB; uv sync total = 11000 -> 10.7 KB
        self.assertIn("21.5 KB", out)
        self.assertIn("10.7 KB", out)
        # Larger total sorts first (uv add before uv sync)
        self.assertLess(out.index("uv add"), out.index("uv sync"))

    def test_empty_commands(self):
        out = self.capture(self.dm.print_app_commands, "uv", {})
        self.assertIn("No command data for uv", out)


class TestJsonHelpers(unittest.TestCase):
    def setUp(self):
        self.dm = DisplayManager()

    def test_format_status_json(self):
        data = self.dm.format_status_json("HomeWiFi", 1000, 5000, 10.0, 20.0)
        self.assertEqual(data["ssid"], "HomeWiFi")
        self.assertEqual(data["usage_bytes"], 1000)
        self.assertNotIn("limit", data)

    def test_format_status_json_with_limit(self):
        data = self.dm.format_status_json("HomeWiFi", 1000, 5000, 10.0, 20.0, limit=2000)
        self.assertEqual(data["limit_bytes"], 2000)
        self.assertEqual(data["limit_percent"], 50.0)

    def test_format_status_json_with_top_app(self):
        data = self.dm.format_status_json("HomeWiFi", 1000, 5000, 0, 0, top_app="brave")
        self.assertEqual(data["top_app"], "brave")

    def test_format_stats_json(self):
        usage = {"HomeWiFi": {"total_rx": 1000, "total_tx": 500, "connection_count": 3}}
        limits = {"HomeWiFi": {"limit": 5000, "interval": "monthly"}}
        data = self.dm.format_stats_json(usage, limits, current_ssid="HomeWiFi")
        self.assertEqual(data["current_ssid"], "HomeWiFi")
        self.assertEqual(len(data["networks"]), 1)
        net = data["networks"][0]
        self.assertTrue(net["is_current"])
        self.assertIn("limit", net)

    def test_output_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.dm.output_json({"a": 1})
        self.assertIn('"a"', buf.getvalue())


if __name__ == "__main__":
    unittest.main()
