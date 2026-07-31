import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from wifi_tracker_modules import perapp
from wifi_tracker_modules import perapp_collector as pc
from wifi_tracker_modules.app_manager import AppManager
from wifi_tracker_modules.data_manager import DataManager

TCP_FLOW = (
    "ipv4 2 tcp 6 431999 ESTABLISHED src=192.168.1.100 dst=142.214.1.4 sport=8080 "
    "dport=443 packets=12 bytes=1234 src=142.214.1.4 dst=192.168.1.100 sport=443 "
    "dport=8080 packets=45 bytes=67890 [ASSURED] mark=0 zone=0 use=2"
)

UDP_FLOW = (
    "ipv4 2 udp 17 29 src=192.168.1.100 dst=8.8.8.8 sport=5353 dport=53 packets=1 "
    "bytes=50 src=8.8.8.8 dst=192.168.1.100 sport=53 dport=5353 packets=1 bytes=200 "
    "mark=0 zone=0 use=2"
)


class TestPerappParsers(unittest.TestCase):
    def test_parse_conntrack_tcp(self):
        proto, t0, t1 = pc.parse_conntrack_line(TCP_FLOW)
        self.assertEqual(proto, "tcp")
        self.assertEqual(t0["src"], "192.168.1.100")
        self.assertEqual(t0["sport"], "8080")
        self.assertEqual(t0["bytes"], "1234")
        self.assertEqual(t1["src"], "142.214.1.4")
        self.assertEqual(t1["bytes"], "67890")

    def test_parse_conntrack_udp(self):
        proto, t0, t1 = pc.parse_conntrack_line(UDP_FLOW)
        self.assertEqual(proto, "udp")
        self.assertEqual(t0["bytes"], "50")
        self.assertEqual(t1["bytes"], "200")

    def test_parse_conntrack_without_accounting(self):
        # No bytes= counters (accounting disabled) -> None
        line = (
            "ipv4 2 tcp 6 431999 ESTABLISHED src=1.2.3.4 dst=5.6.7.8 sport=100 dport=80 "
            "src=5.6.7.8 dst=1.2.3.4 sport=80 dport=100 [ASSURED] mark=0 zone=0 use=2"
        )
        self.assertIsNone(pc.parse_conntrack_line(line))

    def test_parse_conntrack_garbage(self):
        self.assertIsNone(pc.parse_conntrack_line("not a conntrack line"))
        self.assertIsNone(pc.parse_conntrack_line(""))

    def test_hex_ip_v4(self):
        self.assertEqual(pc.hex_ip(False, "6401A8C0"), "192.168.1.100")
        self.assertEqual(pc.hex_ip(False, "0100007F"), "127.0.0.1")

    def test_hex_ip_v6(self):
        self.assertEqual(pc.hex_ip(True, "20010db8000000000000000000000001"), "2001:db8::1")

    def test_parse_proc_net(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(
                "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when "
                "retrnsmt   uid  timeout inode\n"
                "   3: 6401A8C0:1F90 0401D68E:01BB 01 00000000:00000000 00:00000000 "
                "00000000  1000        0 5678 1 0000000000000000 100 0 0 10 0\n"
            )
            path = f.name
        try:
            result = pc.parse_proc_net(path)
            self.assertEqual(result[5678], ("192.168.1.100", 8080, "142.214.1.4", 443))
        finally:
            os.unlink(path)

    def test_flow_to_socket_connected(self):
        proto, t0, t1 = pc.parse_conntrack_line(TCP_FLOW)
        sockets = {
            "6": {5678: ("192.168.1.100", 8080, "142.214.1.4", 443)},
            "17": {},
        }
        index = pc.build_socket_index(sockets)
        self.assertEqual(pc.flow_to_socket(proto, t0, t1, index), (5678, True))

    def test_flow_to_socket_unconnected_udp(self):
        proto, t0, t1 = pc.parse_conntrack_line(UDP_FLOW)
        # Local UDP socket bound but not connected (raddr 0.0.0.0:0)
        sockets = {
            "6": {},
            "17": {999: ("192.168.1.100", 5353, "0.0.0.0", 0)},
        }
        index = pc.build_socket_index(sockets)
        self.assertEqual(pc.flow_to_socket(proto, t0, t1, index), (999, True))

    def test_flow_to_socket_no_match(self):
        proto, t0, t1 = pc.parse_conntrack_line(TCP_FLOW)
        index = pc.build_socket_index({"6": {}, "17": {}})
        self.assertIsNone(pc.flow_to_socket(proto, t0, t1, index))


class TestCollectorAccumulation(unittest.TestCase):
    def test_collector_baselines_then_accumulates(self):
        collector = pc.Collector(interface="wlan0", interval=1)
        sockets = {
            "6": {5678: ("192.168.1.100", 8080, "142.214.1.4", 443)},
            "17": {},
        }
        original_read_flows = pc.read_flows
        original_read_sockets = pc.read_sockets
        original_pid_map = pc.build_pid_map
        original_process_name = pc.process_name
        try:

            def fake_flows_1():
                return [pc.parse_conntrack_line(TCP_FLOW)]

            pc.read_flows = fake_flows_1
            pc.read_sockets = lambda: sockets
            pc.build_pid_map = lambda: {5678: 1234}
            pc.process_name = lambda pid: "brave"

            # First sample: baselines all flows, records nothing
            collector.sample()
            self.assertEqual(collector.app_cum, {})

            def fake_flows_2():
                line = TCP_FLOW.replace("bytes=1234", "bytes=2234").replace(
                    "bytes=67890", "bytes=77890"
                )
                return [pc.parse_conntrack_line(line)]

            pc.read_flows = fake_flows_2
            collector.sample()
            self.assertEqual(collector.app_cum, {"brave": {"sent": 1000, "recv": 10000}})
        finally:
            pc.read_flows = original_read_flows
            pc.read_sockets = original_read_sockets
            pc.build_pid_map = original_pid_map
            pc.process_name = original_process_name


class TestPerappSnapshot(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.snap = Path(self.test_dir) / "per_app.json"
        self.snap.write_text(
            json.dumps(
                {
                    "timestamp": "2026-07-31T23:00:00",
                    "interface": "wlan0",
                    "apps": {"brave": {"sent": 10, "recv": 20}},
                }
            )
        )
        os.environ["WIFI_TRACKER_PERAPP_FILE"] = str(self.snap)

    def tearDown(self):
        os.environ.pop("WIFI_TRACKER_PERAPP_FILE", None)
        shutil.rmtree(self.test_dir)

    def test_read_snapshot_fresh(self):
        snapshot = perapp.read_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["apps"]["brave"]["recv"], 20)

    def test_read_snapshot_stale(self):
        old = time.time() - 100
        os.utime(self.snap, (old, old))
        self.assertIsNone(perapp.read_snapshot())

    def test_read_snapshot_missing(self):
        self.snap.unlink()
        self.assertIsNone(perapp.read_snapshot())

    def test_read_snapshot_invalid_json(self):
        self.snap.write_text("not json")
        self.assertIsNone(perapp.read_snapshot())


class _FakeProcessManager:
    def _log_error(self, msg):
        pass

    def get_top_network_apps(self, limit=10, ssid=None):
        return []


class _FakeDisplayManager:
    def format_bytes(self, size):
        return str(size)


class TestAppManagerCollector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_file = Path(self.test_dir) / "usage.json"
        self.limits_file = Path(self.test_dir) / "limits.json"
        self.data_file.write_text("{}")
        self.limits_file.write_text("{}")
        self.data_manager = DataManager(str(self.data_file), str(self.limits_file))
        self.snap = Path(self.test_dir) / "per_app.json"

    def tearDown(self):
        os.environ.pop("WIFI_TRACKER_PERAPP_FILE", None)
        shutil.rmtree(self.test_dir)

    def _write_snapshot(self, recv):
        self.snap.write_text(
            json.dumps(
                {
                    "timestamp": "2026-07-31T23:00:00",
                    "interface": "wlan0",
                    "apps": {"brave": {"sent": 0, "recv": recv}},
                }
            )
        )

    def test_check_high_usage_uses_collector(self):
        os.environ["WIFI_TRACKER_PERAPP_FILE"] = str(self.snap)
        self.data_manager.update_usage("TestNet", 1000, 1000)
        app_manager = AppManager(self.data_manager, _FakeProcessManager(), _FakeDisplayManager())

        # First check: baseline, nothing recorded
        self._write_snapshot(1000)
        app_manager.check_high_usage_apps("TestNet", set())
        self.assertEqual(self.data_manager.usage_data["TestNet"].get("app_usage", {}), {})

        # Second check: delta of 4000 recorded
        self._write_snapshot(5000)
        app_manager.check_high_usage_apps("TestNet", set())
        entries = self.data_manager.usage_data["TestNet"]["app_usage"]["brave"]["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["recv"], 4000)

    def test_check_high_usage_falls_back_without_collector(self):
        app_manager = AppManager(self.data_manager, _FakeProcessManager(), _FakeDisplayManager())
        self.data_manager.update_usage("TestNet", 1000, 1000)
        app_manager.check_high_usage_apps("TestNet", set())
        # No snapshot file -> no collector data recorded, no crash
        self.assertEqual(self.data_manager.usage_data["TestNet"].get("app_usage", {}), {})


class TestRecordAppDeltas(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_file = Path(self.test_dir) / "usage.json"
        self.limits_file = Path(self.test_dir) / "limits.json"
        self.data_file.write_text("{}")
        self.limits_file.write_text("{}")
        self.data_manager = DataManager(str(self.data_file), str(self.limits_file))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_record_app_deltas(self):
        self.data_manager.update_usage("TestNet", 1000, 1000)
        self.data_manager.record_app_deltas(
            "TestNet", {"brave": {"sent": 0, "recv": 100}, "spotify": {"sent": 5, "recv": 0}}
        )
        usage = self.data_manager.usage_data["TestNet"]["app_usage"]
        self.assertEqual(usage["brave"]["entries"][0]["recv"], 100)
        self.assertEqual(usage["spotify"]["entries"][0]["sent"], 5)

    def test_record_app_deltas_ignores_zero(self):
        self.data_manager.update_usage("TestNet", 1000, 1000)
        self.data_manager.record_app_deltas("TestNet", {"idle": {"sent": 0, "recv": 0}})
        self.assertEqual(self.data_manager.usage_data["TestNet"].get("app_usage", {}), {})


if __name__ == "__main__":
    unittest.main()
