import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.alert_manager import AlertManager
from wifi_tracker_modules.notification_manager import Urgency


class TestParseSize(unittest.TestCase):
    def test_tb(self):
        self.assertEqual(AlertManager.parse_size("1TB"), 1024**4)

    def test_gb(self):
        self.assertEqual(AlertManager.parse_size("5GB"), 5 * 1024**3)

    def test_g(self):
        self.assertEqual(AlertManager.parse_size("2G"), 2 * 1024**3)

    def test_mb(self):
        self.assertEqual(AlertManager.parse_size("500MB"), 500 * 1024**2)

    def test_kb(self):
        self.assertEqual(AlertManager.parse_size("1KB"), 1024)

    def test_b(self):
        self.assertEqual(AlertManager.parse_size("10B"), 10)

    def test_raw_bytes(self):
        self.assertEqual(AlertManager.parse_size("12345"), 12345)

    def test_decimal(self):
        self.assertEqual(AlertManager.parse_size("1.5GB"), int(1.5 * 1024**3))

    def test_lowercase(self):
        self.assertEqual(AlertManager.parse_size("1gb"), 1024**3)

    def test_invalid(self):
        self.assertIsNone(AlertManager.parse_size("banana"))


class TestParseWindow(unittest.TestCase):
    def test_days(self):
        self.assertEqual(AlertManager.parse_window("2d"), 48.0)

    def test_hours(self):
        self.assertEqual(AlertManager.parse_window("3h"), 3.0)

    def test_minutes(self):
        self.assertEqual(AlertManager.parse_window("30m"), 0.5)

    def test_raw_hours(self):
        self.assertEqual(AlertManager.parse_window("4"), 4.0)

    def test_invalid(self):
        self.assertIsNone(AlertManager.parse_window("zzz"))


class TestFormatWindow(unittest.TestCase):
    def test_days_only(self):
        self.assertEqual(AlertManager.format_window(48.0), "2d")

    def test_days_and_hours(self):
        self.assertEqual(AlertManager.format_window(50.0), "2d 2h")

    def test_days_hours_minutes(self):
        self.assertEqual(AlertManager.format_window(50.5), "2d 2h 30m")

    def test_hours_and_minutes(self):
        self.assertEqual(AlertManager.format_window(3.5), "3h 30m")

    def test_hours_only(self):
        self.assertEqual(AlertManager.format_window(3.0), "3h")

    def test_minutes(self):
        self.assertEqual(AlertManager.format_window(0.75), "45m")


class TestCheckLimits(unittest.TestCase):
    def setUp(self):
        self.data_manager = mock.MagicMock()
        self.pm = mock.MagicMock()
        self.am = AlertManager(self.data_manager, self.pm)

    def _limit_info(self, limit, notified_80=False, notified_100=False):
        return {"limit": limit, "notified_80": notified_80, "notified_100": notified_100}

    def test_no_limit_for_ssid(self):
        self.data_manager.limits_data = {}
        self.am.check_limits("HomeWiFi", 1000)
        self.data_manager.update_limit_status.assert_not_called()

    def test_zero_limit_skipped(self):
        self.data_manager.limits_data = {"HomeWiFi": self._limit_info(0)}
        self.am.check_limits("HomeWiFi", 1000)
        self.data_manager.update_limit_status.assert_not_called()

    def test_100_percent_sends_critical(self):
        self.data_manager.limits_data = {"HomeWiFi": self._limit_info(1000)}
        with mock.patch(
            "wifi_tracker_modules.alert_manager.notifier.send_notification"
        ) as mock_send:
            self.am.check_limits("HomeWiFi", 1000)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][2], Urgency.CRITICAL)
        self.data_manager.update_limit_status.assert_called_once_with(
            "HomeWiFi", "notified_100", True
        )

    def test_80_percent_warning(self):
        self.data_manager.limits_data = {"HomeWiFi": self._limit_info(1000)}
        with mock.patch(
            "wifi_tracker_modules.alert_manager.notifier.send_notification"
        ) as mock_send:
            self.am.check_limits("HomeWiFi", 800)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][2], Urgency.NORMAL)
        self.data_manager.update_limit_status.assert_called_once_with(
            "HomeWiFi", "notified_80", True
        )

    def test_below_80_resets_flags(self):
        self.data_manager.limits_data = {
            "HomeWiFi": self._limit_info(1000, notified_80=True, notified_100=True)
        }
        with mock.patch(
            "wifi_tracker_modules.alert_manager.notifier.send_notification"
        ) as mock_send:
            self.am.check_limits("HomeWiFi", 500)
        mock_send.assert_not_called()
        self.assertEqual(self.data_manager.update_limit_status.call_count, 2)


class TestDailySummary(unittest.TestCase):
    def setUp(self):
        self.data_manager = mock.MagicMock()
        self.pm = mock.MagicMock()
        self.am = AlertManager(self.data_manager, self.pm)

    def test_sends_summary_when_usage(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.data_manager.usage_data = {"HomeWiFi": {"daily": {yesterday: {"rx": 1000, "tx": 500}}}}
        dm = mock.MagicMock()
        dm.format_bytes.side_effect = lambda b: f"{b} bytes"
        with mock.patch(
            "wifi_tracker_modules.alert_manager.notifier.send_notification"
        ) as mock_send:
            self.am.send_daily_summary("HomeWiFi", dm)
        mock_send.assert_called_once()
        self.assertIn("1500 bytes", mock_send.call_args[0][1])

    def test_no_summary_when_no_usage(self):
        self.data_manager.usage_data = {"HomeWiFi": {"daily": {}}}
        with mock.patch(
            "wifi_tracker_modules.alert_manager.notifier.send_notification"
        ) as mock_send:
            self.am.send_daily_summary("HomeWiFi", mock.MagicMock())
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
