import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.cli import WiFiTracker


class WiFiTrackerBase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.test_dir) / "data"
        self.runtime_dir = Path(self.test_dir) / "runtime"
        self.data_dir.mkdir()
        self.runtime_dir.mkdir()
        self._env_backup = {
            k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR")
        }
        os.environ["XDG_DATA_HOME"] = str(self.data_dir)
        os.environ["XDG_CACHE_HOME"] = str(Path(self.test_dir) / "cache")
        os.environ["XDG_RUNTIME_DIR"] = str(self.runtime_dir)
        self.tracker = WiFiTracker(interface="wlan0", interval=0.1)

    def tearDown(self):
        for key, val in self._env_backup.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        shutil.rmtree(self.test_dir)

    def capture(self, fn, *args, **kwargs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(*args, **kwargs)
        return buf.getvalue()


class TestSetLimit(WiFiTrackerBase):
    def test_valid_limit(self):
        out = self.capture(self.tracker.set_limit, "TestWiFi", "5GB", "monthly")
        self.assertIn("Set monthly limit", out)
        self.assertEqual(self.tracker.data_manager.limits_data["TestWiFi"]["limit"], 5 * 1024**3)

    def test_invalid_limit_format(self):
        out = self.capture(self.tracker.set_limit, "TestWiFi", "banana", "monthly")
        self.assertIn("Invalid limit format", out)
        self.assertNotIn("TestWiFi", self.tracker.data_manager.limits_data)


class TestRemoveLimit(WiFiTrackerBase):
    def test_remove_existing_limit(self):
        self.tracker.data_manager.set_limit("TestWiFi", 1024**3, "daily")
        out = self.capture(self.tracker.remove_limit, "TestWiFi")
        self.assertIn("Removed limit", out)

    def test_remove_missing_limit(self):
        out = self.capture(self.tracker.remove_limit, "Nonexistent")
        self.assertIn("No limit found", out)


class TestSetUsageFrom(WiFiTrackerBase):
    def test_relative_date(self):
        out = self.capture(self.tracker.set_usage_from, "TestWiFi", "2weeks")
        self.assertIn("✅", out)
        self.assertIn("TestWiFi", self.tracker.data_manager.limits_data)

    def test_absolute_date(self):
        out = self.capture(self.tracker.set_usage_from, "TestWiFi", "2026-01-01")
        self.assertIn("2026-01-01", out)

    def test_invalid_date(self):
        out = self.capture(self.tracker.set_usage_from, "TestWiFi", "not-a-date")
        self.assertIn("Invalid date format", out)


class TestCleanupData(WiFiTrackerBase):
    @mock.patch("wifi_tracker_modules.data_manager.DataManager.cleanup_old_data", return_value=0)
    def test_no_old_data(self, mock_cleanup):
        out = self.capture(self.tracker.cleanup_data, 90)
        self.assertIn("No old data", out)

    @mock.patch("wifi_tracker_modules.data_manager.DataManager.cleanup_old_data", return_value=5)
    @mock.patch("wifi_tracker_modules.data_manager.DataManager.save_data")
    def test_removes_old_data(self, mock_save, mock_cleanup):
        out = self.capture(self.tracker.cleanup_data, 90)
        self.assertIn("Cleaned up 5", out)
        mock_save.assert_called_once()


class TestAlertMode(WiFiTrackerBase):
    def test_show_settings(self):
        out = self.capture(self.tracker.alert_mode, ["show"])
        self.assertIn("Alert threshold", out)

    def test_missing_args(self):
        out = self.capture(self.tracker.alert_mode, [])
        self.assertIn("Usage: wifi-tracker alert", out)

    def test_invalid_threshold(self):
        out = self.capture(self.tracker.alert_mode, ["nope", "1h"])
        self.assertIn("Invalid threshold", out)

    def test_invalid_window(self):
        out = self.capture(self.tracker.alert_mode, ["5GB", "zzz"])
        self.assertIn("Invalid time window", out)

    def test_set_alert(self):
        out = self.capture(self.tracker.alert_mode, ["2GB", "1h"])
        self.assertIn("Alert set", out)
        settings = self.tracker.data_manager.get_alert_settings()
        self.assertEqual(settings["threshold_bytes"], 2 * 1024**3)


class TestStopDaemon(WiFiTrackerBase):
    @mock.patch(
        "wifi_tracker_modules.process_manager.ProcessManager.is_daemon_running",
        return_value=False,
    )
    def test_no_daemon_running(self, mock_running):
        out = self.capture(self.tracker.stop_daemon)
        self.assertIn("No daemon is currently running", out)

    @mock.patch(
        "wifi_tracker_modules.process_manager.ProcessManager.is_daemon_running",
        return_value=True,
    )
    @mock.patch(
        "wifi_tracker_modules.process_manager.ProcessManager.kill_all_instances",
        return_value=1,
    )
    def test_stops_daemon(self, mock_kill, mock_running):
        out = self.capture(self.tracker.stop_daemon)
        self.assertIn("Stopped daemon", out)


class TestTopAppsMode(WiFiTrackerBase):
    @mock.patch("wifi_tracker_modules.cli.perapp.read_snapshot", return_value=None)
    @mock.patch(
        "wifi_tracker_modules.process_manager.ProcessManager.get_top_network_apps",
        return_value=[],
    )
    def test_uses_fallback_estimates(self, mock_apps, mock_snapshot):
        out = self.capture(self.tracker.top_apps_mode)
        self.assertIn("Estimates from rchar-read_bytes", out)

    @mock.patch(
        "wifi_tracker_modules.cli.perapp.read_snapshot",
        return_value={"apps": {"firefox": {"recv": 100, "sent": 50}}},
    )
    def test_uses_conntrack_snapshot(self, mock_snapshot):
        out = self.capture(self.tracker.top_apps_mode)
        self.assertIn("root conntrack collector", out)

    @mock.patch(
        "wifi_tracker_modules.cli.perapp.read_snapshot",
        return_value={
            "apps": {
                "uv": {
                    "sent": 3000,
                    "recv": 30000,
                    "commands": {
                        "uv add": {"sent": 2000, "recv": 20000},
                        "uv sync": {"sent": 1000, "recv": 10000},
                    },
                }
            }
        },
    )
    def test_shows_command_breakdown_for_app(self, mock_snapshot):
        out = self.capture(self.tracker.top_apps_mode, "uv")
        self.assertIn("uv add", out)
        self.assertIn("uv sync", out)
        self.assertNotIn("Data from root conntrack collector", out)

    @mock.patch(
        "wifi_tracker_modules.cli.perapp.read_snapshot",
        return_value={"apps": {"firefox": {"recv": 100, "sent": 50}}},
    )
    def test_unknown_app_reports_not_found(self, mock_snapshot):
        out = self.capture(self.tracker.top_apps_mode, "uv")
        self.assertIn("not found in collector snapshot", out)

    @mock.patch("wifi_tracker_modules.cli.perapp.read_snapshot", return_value=None)
    def test_app_breakdown_requires_collector(self, mock_snapshot):
        out = self.capture(self.tracker.top_apps_mode, "uv")
        self.assertIn("requires the root collector", out)


class TestPerappMode(WiFiTrackerBase):
    @mock.patch("wifi_tracker_modules.cli.perapp.is_root", return_value=True)
    @mock.patch("wifi_tracker_modules.cli.perapp.install_system_service", return_value=(True, "ok"))
    def test_install_as_root(self, mock_install, mock_root):
        out = self.capture(self.tracker.perapp_mode, "install")
        self.assertIn("ok", out)
        mock_install.assert_called_once()

    @mock.patch("wifi_tracker_modules.cli.perapp.is_root", return_value=False)
    @mock.patch("wifi_tracker_modules.cli.perapp.reexec_as_root", return_value=(False, "no"))
    def test_install_reexecs_as_root(self, mock_reexec, mock_root):
        self.capture(self.tracker.perapp_mode, "install")
        mock_reexec.assert_called_once_with("install", "wlan0")

    @mock.patch("wifi_tracker_modules.cli.perapp.is_root", return_value=True)
    @mock.patch(
        "wifi_tracker_modules.cli.perapp.collector_status",
        return_value={
            "installed": True,
            "service_active": True,
            "collector_file": "/run/wifi-tracker/per_app.json",
            "last_snapshot": "2026-01-01 00:00:00",
            "tracked_apps": 3,
        },
    )
    def test_status(self, mock_status, mock_root):
        out = self.capture(self.tracker.perapp_mode, "status")
        self.assertIn("Installed:      yes", out)
        self.assertIn("Tracked apps:   3", out)


class TestNetworksMode(WiFiTrackerBase):
    def test_no_networks(self):
        out = self.capture(self.tracker.networks_mode)
        self.assertIn("No saved networks", out)


class TestRequestShutdown(WiFiTrackerBase):
    def test_sets_running_false(self):
        self.tracker.running = True
        self.tracker._request_shutdown()
        self.assertFalse(self.tracker.running)


class TestMain(unittest.TestCase):
    """Test main() arg parsing and subcommand dispatch."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self._env_backup = {
            k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR")
        }
        os.environ["XDG_DATA_HOME"] = str(Path(self.test_dir) / "data")
        os.environ["XDG_CACHE_HOME"] = str(Path(self.test_dir) / "cache")
        os.environ["XDG_RUNTIME_DIR"] = str(Path(self.test_dir) / "runtime")

    def tearDown(self):
        for key, val in self._env_backup.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        shutil.rmtree(self.test_dir)

    def run_main(self, args):
        from wifi_tracker_modules import cli

        buf = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["wifi-tracker"] + args),
            mock.patch.object(cli, "WiFiTracker") as mock_tracker,
            contextlib.redirect_stdout(buf),
            contextlib.suppress(SystemExit),
        ):
            cli.main()
        return mock_tracker, buf.getvalue()

    def test_no_command_prints_help(self):
        mock_tracker, out = self.run_main([])
        self.assertIn("usage:", out)
        mock_tracker.assert_not_called()

    def test_dispatch_set_limit(self):
        mock_tracker, _ = self.run_main(["limit", "HomeWiFi", "5GB", "monthly"])
        mock_tracker.return_value.set_limit.assert_called_once_with("HomeWiFi", "5GB", "monthly")

    def test_dispatch_remove_limit(self):
        mock_tracker, _ = self.run_main(["remove-limit", "HomeWiFi"])
        mock_tracker.return_value.remove_limit.assert_called_once_with("HomeWiFi")

    def test_dispatch_alias_s_resolves_to_status(self):
        mock_tracker, _ = self.run_main(["s", "--range", "7d"])
        self.assertIn("status_mode", str(mock_tracker.return_value.method_calls))

    def test_dispatch_stop(self):
        mock_tracker, _ = self.run_main(["stop"])
        mock_tracker.return_value.stop_daemon.assert_called_once_with()

    def test_dispatch_cleanup_default_days(self):
        mock_tracker, _ = self.run_main(["cleanup"])
        mock_tracker.return_value.cleanup_data.assert_called_once_with(90)

    def test_dispatch_perapp_status(self):
        mock_tracker, _ = self.run_main(["perapp"])
        mock_tracker.return_value.perapp_mode.assert_called_once()
        args = mock_tracker.return_value.perapp_mode.call_args[0]
        self.assertEqual(args[0], "status")

    def test_dispatch_today(self):
        mock_tracker, _ = self.run_main(["today"])
        mock_tracker.return_value.monitor.get_measurement.return_value = None
        # today without connection prints message via real code path

    def test_dispatch_top_apps_with_app(self):
        mock_tracker, _ = self.run_main(["top-apps", "uv"])
        mock_tracker.return_value.top_apps_mode.assert_called_once_with("uv")

    def test_dispatch_top_apps_without_app(self):
        mock_tracker, _ = self.run_main(["top-apps"])
        mock_tracker.return_value.top_apps_mode.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
