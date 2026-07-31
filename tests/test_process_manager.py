import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules.process_manager import ProcessManager


class TestProcessManagerBase(unittest.TestCase):
    def setUp(self):
        # Isolate XDG paths to a temp dir so Config resolves paths here
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.test_dir) / "cache"
        self.runtime_dir = Path(self.test_dir) / "runtime"
        self.cache_dir.mkdir()
        self.runtime_dir.mkdir()
        self._env_backup = {
            "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR"),
        }
        os.environ["XDG_CACHE_HOME"] = str(self.cache_dir)
        os.environ["XDG_RUNTIME_DIR"] = str(self.runtime_dir)
        self.pm = ProcessManager("wifi-tracker")

    def tearDown(self):
        for key, val in self._env_backup.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        shutil.rmtree(self.test_dir)


class TestPidFile(TestProcessManagerBase):
    def test_pid_file_path_under_runtime_dir(self):
        self.assertEqual(self.pm.pid_file, self.runtime_dir / "wifi-tracker" / "daemon.pid")

    def test_create_and_remove_pid_file(self):
        self.assertFalse(self.pm.pid_file.exists())
        self.pm.create_pid_file()
        self.assertTrue(self.pm.pid_file.exists())
        self.assertEqual(self.pm.pid_file.read_text().strip(), str(os.getpid()))
        self.pm.remove_pid_file()
        self.assertFalse(self.pm.pid_file.exists())

    def test_remove_pid_file_missing_is_noop(self):
        self.assertFalse(self.pm.pid_file.exists())
        self.pm.remove_pid_file()  # should not raise

    def test_is_daemon_running_no_pid_file(self):
        self.assertFalse(self.pm.is_daemon_running())

    def test_is_daemon_running_with_valid_pid(self):
        self.pm.create_pid_file()
        with (
            mock.patch("psutil.pid_exists", return_value=True),
            mock.patch("psutil.Process") as mock_proc,
        ):
            mock_proc.return_value.cmdline.return_value = ["wifi-tracker", "daemon"]
            self.assertTrue(self.pm.is_daemon_running())
            self.assertTrue(self.pm.pid_file.exists())  # left in place

    def test_is_daemon_running_stale_pid_cleans_up(self):
        self.pm.create_pid_file()
        with mock.patch("psutil.pid_exists", return_value=False):
            self.assertFalse(self.pm.is_daemon_running())
        self.assertFalse(self.pm.pid_file.exists())

    def test_is_daemon_running_invalid_content_cleans_up(self):
        self.pm.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pm.pid_file.write_text("not-a-number")
        self.assertFalse(self.pm.is_daemon_running())
        self.assertFalse(self.pm.pid_file.exists())


class TestFindInstances(TestProcessManagerBase):
    def _fake_proc(self, pid, cmdline):
        proc = mock.MagicMock()
        proc.info = {"pid": pid, "name": "wifi-tracker", "cmdline": cmdline}
        proc.pid = pid
        return proc

    @mock.patch("psutil.process_iter")
    def test_finds_matching_instances(self, mock_iter):
        self_proc = self._fake_proc(os.getpid(), [sys.argv[0], "daemon"])
        other = self._fake_proc(9999, ["wifi-tracker", "daemon"])
        mock_iter.return_value = [self_proc, other]
        instances = self.pm.find_all_instances()
        # Self is excluded, matching instance kept
        self.assertEqual([p.pid for p in instances], [9999])

    @mock.patch("psutil.process_iter")
    def test_skips_non_matching_processes(self, mock_iter):
        proc = self._fake_proc(1234, ["firefox", "--headless"])
        mock_iter.return_value = [proc]
        self.assertEqual(self.pm.find_all_instances(), [])

    @mock.patch("psutil.process_iter")
    def test_skips_processes_with_no_cmdline(self, mock_iter):
        proc = mock.MagicMock()
        proc.info = {"pid": 1, "name": "wifi-tracker", "cmdline": []}
        mock_iter.return_value = [proc]
        self.assertEqual(self.pm.find_all_instances(), [])

    @mock.patch("psutil.process_iter")
    def test_handles_no_such_process(self, mock_iter):
        from psutil import NoSuchProcess

        proc = mock.MagicMock()
        proc.pid = 2
        proc.info = mock.MagicMock()
        proc.info.get = mock.MagicMock(side_effect=NoSuchProcess(2))
        mock_iter.return_value = [proc]
        self.assertEqual(self.pm.find_all_instances(), [])


class TestKillAllInstances(TestProcessManagerBase):
    @mock.patch.object(ProcessManager, "find_all_instances")
    def test_no_instances_returns_zero(self, mock_find):
        mock_find.side_effect = [[], [], []]
        self.assertEqual(self.pm.kill_all_instances(), 0)

    @mock.patch("time.sleep")
    @mock.patch.object(ProcessManager, "find_all_instances")
    def test_terminates_and_counts(self, mock_find, mock_sleep):
        victim = mock.MagicMock()
        victim.pid = 555
        victim.cmdline.return_value = ["wifi-tracker", "daemon"]
        victim.is_running.return_value = False
        # Pass 1: one instance, final pass: none left
        mock_find.side_effect = [[victim], [], []]
        killed = self.pm.kill_all_instances()
        self.assertEqual(killed, 1)
        victim.terminate.assert_called_once()


class TestSystemd(TestProcessManagerBase):
    def setUp(self):
        super().setUp()
        self.fake_home = Path(self.test_dir) / "home"
        self.fake_home.mkdir()
        self.home_patcher = mock.patch("pathlib.Path.home", return_value=self.fake_home)
        self.home_patcher.start()
        self.addCleanup(self.home_patcher.stop)

    def test_service_path_under_home_config(self):
        expected = self.fake_home / ".config" / "systemd" / "user" / "wifi-tracker.service"
        self.assertEqual(self.pm.get_systemd_service_path(), expected)

    def test_is_systemd_installed_reflects_file(self):
        service = self.pm.get_systemd_service_path()
        self.assertFalse(service.exists())  # temp HOME-like path
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text("[Unit]")
        self.assertTrue(self.pm.is_systemd_installed())

    @mock.patch("subprocess.run", return_value=mock.MagicMock())
    def test_install_systemd_service(self, mock_run):
        ok = self.pm.install_systemd_service("/usr/bin/wifi-tracker", "daemon")
        self.assertTrue(ok)
        service = self.pm.get_systemd_service_path()
        self.assertTrue(service.exists())
        content = service.read_text()
        self.assertIn("ExecStart=/usr/bin/wifi-tracker daemon", content)
        self.assertEqual(mock_run.call_count, 3)  # reload, enable, start

    @mock.patch("subprocess.run", side_effect=Exception("boom"))
    def test_install_systemd_service_failure(self, mock_run):
        ok = self.pm.install_systemd_service("/usr/bin/wifi-tracker")
        self.assertFalse(ok)

    @mock.patch("subprocess.run", return_value=mock.MagicMock())
    def test_remove_systemd_service(self, mock_run):
        service = self.pm.get_systemd_service_path()
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text("[Unit]")
        ok = self.pm.remove_systemd_service()
        self.assertTrue(ok)
        self.assertFalse(service.exists())


class TestProcessInfo(TestProcessManagerBase):
    @mock.patch.object(ProcessManager, "find_all_instances", return_value=[])
    def test_get_process_info(self, mock_find):
        info = self.pm.get_process_info()
        self.assertEqual(info["current_pid"], os.getpid())
        self.assertFalse(info["daemon_running"])
        self.assertEqual(info["total_instances"], 0)
        self.assertIsInstance(info["log_file"], str)


class TestTopNetworkApps(TestProcessManagerBase):
    @mock.patch("psutil.net_io_counters", return_value=mock.MagicMock(bytes_sent=1, bytes_recv=2))
    @mock.patch("psutil.net_connections", return_value=[])
    def test_empty_connections_returns_empty(self, mock_conns, mock_io):
        self.assertEqual(self.pm.get_top_network_apps(), [])


if __name__ == "__main__":
    unittest.main()
