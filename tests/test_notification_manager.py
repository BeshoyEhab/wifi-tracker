import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.notification_manager import NotificationManager, Urgency


class TestSendNotification(unittest.TestCase):
    def setUp(self):
        self.nm = NotificationManager()

    def test_quiet_suppresses(self):
        self.nm.quiet = True
        with mock.patch("subprocess.run") as mock_run:
            result = self.nm.send_notification("t", "m")
        self.assertFalse(result)
        mock_run.assert_not_called()

    def test_no_notify_send_returns_false(self):
        self.nm.notify_send = False
        with mock.patch("subprocess.run") as mock_run:
            result = self.nm.send_notification("t", "m")
        self.assertFalse(result)
        mock_run.assert_not_called()

    def test_successful_send(self):
        self.nm.notify_send = True
        with mock.patch("subprocess.run") as mock_run:
            result = self.nm.send_notification("Title", "Body", Urgency.CRITICAL)
        self.assertTrue(result)
        cmd = mock_run.call_args[0][0]
        self.assertIn("Title", cmd)
        self.assertIn("Body", cmd)
        self.assertIn("--urgency=critical", cmd)

    def test_subprocess_error_returns_false(self):
        self.nm.notify_send = True
        with mock.patch("subprocess.run", side_effect=Exception("boom")):
            result = self.nm.send_notification("t", "m")
        self.assertFalse(result)


class TestAskGatewayTrust(unittest.TestCase):
    def setUp(self):
        self.nm = NotificationManager()

    def test_quiet_returns_ignored(self):
        self.nm.quiet = True
        self.assertEqual(self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1"), "ignored")

    def test_notify_send_sh_trust(self):
        self.nm.notify_send_sh = True
        with mock.patch.object(self.nm, "_ask_with_notify_send_sh", return_value="Trust"):
            result = self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1")
        self.assertEqual(result, "trust")

    def test_notify_send_sh_block(self):
        self.nm.notify_send_sh = True
        with mock.patch.object(self.nm, "_ask_with_notify_send_sh", return_value="Block"):
            result = self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1")
        self.assertEqual(result, "block")

    def test_notify_send_sh_ignored(self):
        self.nm.notify_send_sh = True
        with mock.patch.object(self.nm, "_ask_with_notify_send_sh", return_value=""):
            result = self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1")
        self.assertEqual(result, "ignored")

    def test_zenity_trust(self):
        self.nm.notify_send_sh = False
        self.nm.zenity = True
        with mock.patch.object(self.nm, "_ask_with_zenity", return_value="trust"):
            result = self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1")
        self.assertEqual(result, "trust")

    def test_fallback_plain_notification(self):
        self.nm.notify_send_sh = False
        self.nm.zenity = False
        with mock.patch.object(self.nm, "send_notification") as mock_send:
            result = self.nm.ask_gateway_trust("HomeWiFi", "10.0.0.1")
        self.assertEqual(result, "ignored")
        mock_send.assert_called_once()
        self.assertIn("trust-gateway", mock_send.call_args[0][1])


class TestAskHighUsageAction(unittest.TestCase):
    def setUp(self):
        self.nm = NotificationManager()

    def test_quiet_returns_ignored(self):
        self.nm.quiet = True
        self.assertEqual(
            self.nm.ask_high_usage_action("HomeWiFi", "firefox", "1GB", "1h"), "ignored"
        )

    def test_notify_send_sh_safe(self):
        self.nm.notify_send_sh = True
        with mock.patch.object(self.nm, "_ask_with_notify_send_sh", return_value="Safe always"):
            result = self.nm.ask_high_usage_action("HomeWiFi", "firefox", "1GB", "1h")
        self.assertEqual(result, "safe_always")

    def test_notify_send_sh_kill(self):
        self.nm.notify_send_sh = True
        with mock.patch.object(self.nm, "_ask_with_notify_send_sh", return_value="Kill always"):
            result = self.nm.ask_high_usage_action("HomeWiFi", "firefox", "1GB", "1h")
        self.assertEqual(result, "kill_always")

    def test_zenity_safe(self):
        self.nm.notify_send_sh = False
        self.nm.zenity = True
        with mock.patch.object(self.nm, "_ask_with_zenity", return_value="safe_always"):
            result = self.nm.ask_high_usage_action("HomeWiFi", "firefox", "1GB", "1h")
        self.assertEqual(result, "safe_always")

    def test_fallback_plain_notification(self):
        self.nm.notify_send_sh = False
        self.nm.zenity = False
        with mock.patch.object(self.nm, "send_notification") as mock_send:
            result = self.nm.ask_high_usage_action("HomeWiFi", "firefox", "1GB", "1h")
        self.assertEqual(result, "ignored")
        mock_send.assert_called_once()
        self.assertIn("mark-safe", mock_send.call_args[0][1])


class TestAskWithNotifySendSh(unittest.TestCase):
    def setUp(self):
        self.nm = NotificationManager()

    def test_returns_stdout_choice(self):
        result_mock = mock.MagicMock()
        result_mock.stdout.strip.return_value = "Trust"
        with mock.patch("subprocess.run", return_value=result_mock):
            choice = self.nm._ask_with_notify_send_sh("t", "b", {"Trust": "true"})
        self.assertEqual(choice, "Trust")

    def test_timeout_returns_empty(self):
        with mock.patch("subprocess.run", side_effect=Exception("timeout")):
            choice = self.nm._ask_with_notify_send_sh("t", "b", {"Trust": "true"})
        self.assertEqual(choice, "")


class TestAskWithZenity(unittest.TestCase):
    def setUp(self):
        self.nm = NotificationManager()

    def test_returns_choice_on_success(self):
        result_mock = mock.MagicMock()
        result_mock.returncode = 0
        result_mock.stdout.strip.return_value = "trust"
        with (
            mock.patch("subprocess.run", return_value=result_mock),
            mock.patch("wifi_tracker_modules.notification_manager.time.time", return_value=0),
        ):
            choice = self.nm._ask_with_zenity("t", "b", [("TRUE", "trust", "Trust")])
        self.assertEqual(choice, "trust")

    def test_cancelled_returns_empty(self):
        result_mock = mock.MagicMock()
        result_mock.returncode = 1
        with (
            mock.patch("subprocess.run", return_value=result_mock),
            mock.patch("wifi_tracker_modules.notification_manager.time.time", return_value=0),
        ):
            choice = self.nm._ask_with_zenity("t", "b", [])
        self.assertEqual(choice, "")


if __name__ == "__main__":
    unittest.main()
