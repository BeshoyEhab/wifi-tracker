#!/usr/bin/env python3
"""
WiFi Tracker per-app network collector (runs as root).

Samples per-process network usage from the kernel conntrack table
(/proc/net/nf_conntrack) with per-connection byte accounting enabled,
maps each flow to its owning process via /proc/net/{tcp,tcp6,udp,udp6}
and /proc/<pid>/fd socket inodes, and writes cumulative per-app byte
counts to /run/wifi-tracker/per_app.json for the unprivileged
wifi-tracker daemon to consume.

Self-contained (stdlib only) so it can be installed to a system-wide
path and run with the system Python under a systemd system service.
"""

import argparse
import contextlib
import glob
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

CONNTRACK_FILE = "/proc/net/nf_conntrack"
OUTPUT_PATH = "/run/wifi-tracker/per_app.json"
SAMPLE_LIMIT = 100000
INTERVAL = 10

_PROTO_TCP = "6"
_PROTO_UDP = "17"

# /proc/net/{tcp,tcp6,udp,udp6} state codes that can carry data (excludes
# 0A=LISTEN and 07=CLOSE).
_ACTIVE_STATES = {"01", "02", "03", "04", "05", "06", "08", "09", "0B", "0C"}


def parse_conntrack_line(line):
    """Parse one /proc/net/nf_conntrack line.

    Returns (proto, tuple0, tuple1) where each tuple is a dict with
    src/dst/sport/dport/packets/bytes. Returns None if unparseable or the
    per-connection accounting counters are missing (accounting disabled).
    """
    parts = line.split()
    if len(parts) < 8 or parts[0] not in ("ipv4", "ipv6"):
        return None
    if "src=" not in line:
        return None
    src_idx = [i for i, p in enumerate(parts) if p.startswith("src=")]
    if len(src_idx) != 2:
        return None
    proto = parts[2]

    def _tuple(start, end):
        t = {}
        for p in parts[start:end]:
            if "=" in p:
                k, v = p.split("=", 1)
                if k in ("src", "dst", "sport", "dport", "packets", "bytes"):
                    t[k] = v
        return t

    t0 = _tuple(src_idx[0], src_idx[1])
    t1 = _tuple(src_idx[1], len(parts))
    if "bytes" not in t0 or "bytes" not in t1:
        return None
    return proto, t0, t1


def hex_ip(is_v6, hex_str):
    """Convert the hex address in /proc/net/{tcp,tcp6,udp,udp6} to a string."""
    raw = bytes.fromhex(hex_str)
    if is_v6:
        return socket.inet_ntop(socket.AF_INET6, raw)
    return socket.inet_ntop(socket.AF_INET, raw[::-1])


def parse_proc_net(path, is_v6=False):
    """Parse /proc/net/{tcp,tcp6,udp,udp6} into {inode: (laddr, lport, raddr, rport)}."""
    out = {}
    try:
        with open(path) as f:
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) < 10 or parts[3] not in _ACTIVE_STATES:
                    continue
                try:
                    laddr, lport = parts[1].split(":")
                    raddr, rport = parts[2].split(":")
                    inode = int(parts[9])
                except ValueError:
                    continue
                out[inode] = (
                    hex_ip(is_v6, laddr),
                    int(lport, 16),
                    hex_ip(is_v6, raddr),
                    int(rport, 16),
                )
    except (FileNotFoundError, OSError):
        pass
    return out


def read_flows():
    """Read all conntrack flows. Returns a list of (proto, tuple0, tuple1)."""
    flows = []
    try:
        with open(CONNTRACK_FILE) as f:
            for line in f:
                parsed = parse_conntrack_line(line)
                if parsed:
                    flows.append(parsed)
                    if len(flows) >= SAMPLE_LIMIT:
                        break
    except (FileNotFoundError, OSError):
        pass
    return flows


def read_sockets():
    """Read all local sockets. Returns {proto: {inode: (laddr, lport, raddr, rport)}}."""
    sockets = {_PROTO_TCP: {}, _PROTO_UDP: {}}
    for pkey, proto, v6 in (
        (_PROTO_TCP, "tcp", False),
        (_PROTO_TCP, "tcp6", True),
        (_PROTO_UDP, "udp", False),
        (_PROTO_UDP, "udp6", True),
    ):
        sockets[pkey].update(parse_proc_net(f"/proc/net/{proto}", v6))
    return sockets


def build_socket_index(sockets):
    """Index sockets by (proto, laddr, lport) -> [(inode, raddr, rport)]."""
    index = {}
    for pkey, sock_map in sockets.items():
        for inode, (laddr, lport, raddr, rport) in sock_map.items():
            index.setdefault((pkey, laddr, lport), []).append((inode, raddr, rport))
    return index


def build_pid_map():
    """Map socket inode -> pid by scanning /proc/*/fd symlinks."""
    pid_map = {}
    for fd in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:["):
            try:
                inode = int(target[8:-1])
                pid = int(fd.split("/")[2])
            except ValueError:
                continue
            pid_map.setdefault(inode, pid)
    return pid_map


def process_name(pid):
    """Get the process comm for a PID."""
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip() or "unknown"
    except (OSError, ValueError):
        return "unknown"


def process_command(pid):
    """Get a short command-line grouping key for a PID.

    Reads /proc/<pid>/cmdline and returns the executable basename plus its
    first non-flag argument (e.g. "uv add", "uv sync"). Falls back to the
    process name when the cmdline is empty or unreadable.
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read().split(b"\x00")
        parts = [p.decode(errors="replace") for p in raw if p]
    except (OSError, ValueError):
        return process_name(pid)
    if not parts:
        return process_name(pid)
    base = os.path.basename(parts[0]) or process_name(pid)
    key = f"{base} {parts[1]}" if len(parts) >= 2 and not parts[1].startswith("-") else base
    return key[:60]


def flow_to_socket(proto, t0, t1, index):
    """Map a conntrack flow to a local socket.

    Returns (inode, is_orig_ours). is_orig_ours is True when the flow's
    original-direction source is our local socket (we initiated).
    Returns None if no local socket matches.
    """
    if proto not in ("tcp", "udp"):
        return None
    pkey = _PROTO_TCP if proto == "tcp" else _PROTO_UDP
    for src_t, is_orig in ((t0, True), (t1, False)):
        try:
            cands = index.get((pkey, src_t["src"], int(src_t["sport"])))
        except (KeyError, ValueError):
            continue
        if not cands:
            continue
        dst = src_t["dst"]
        try:
            dport = int(src_t["dport"])
        except (KeyError, ValueError):
            continue
        fallback = None
        for inode, raddr, rport in cands:
            if raddr not in ("0.0.0.0", "::") and rport != 0:
                if raddr == dst and rport == dport:
                    return inode, is_orig
            elif fallback is None:
                fallback = inode
        if fallback is not None:
            return fallback, is_orig
    return None


def enable_accounting():
    """Enable per-connection conntrack byte accounting. Best effort."""
    try:
        with open("/proc/sys/net/netfilter/nf_conntrack_acct", "w") as f:
            f.write("1")
        return True
    except OSError as e:
        sys.stderr.write(f"[perapp] could not enable conntrack accounting: {e}\n")
        return False


def detect_interface():
    """Best-effort wifi interface detection (informational only)."""
    try:
        result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.split("\n"):
            if "IEEE 802.11" in line and "no wireless extensions" not in line:
                return line.split()[0]
    except (subprocess.SubprocessError, OSError):
        pass
    return "wlan0"


class Collector:
    """Samples conntrack flows and aggregates per-app cumulative byte counts."""

    def __init__(self, interface="", interval=INTERVAL):
        self.interface = interface or detect_interface()
        self.interval = interval
        self.prev_flow = {}
        self.app_cum = {}

    def sample(self):
        flows = read_flows()
        sockets = read_sockets()
        index = build_socket_index(sockets)
        pid_map = build_pid_map()

        current_keys = set()
        deltas = []
        for proto, t0, t1 in flows:
            try:
                key = (proto, t0["src"], t0["sport"], t0["dst"], t0["dport"])
                cur = (int(t0["bytes"]), int(t1["bytes"]))
            except (KeyError, ValueError):
                continue
            current_keys.add(key)
            prev = self.prev_flow.get(key)
            if prev is None:
                self.prev_flow[key] = cur
                continue
            d0 = max(0, cur[0] - prev[0])
            d1 = max(0, cur[1] - prev[1])
            self.prev_flow[key] = cur
            if d0 or d1:
                deltas.append((proto, t0, t1, d0, d1))

        self.prev_flow = {k: v for k, v in self.prev_flow.items() if k in current_keys}

        for proto, t0, t1, d0, d1 in deltas:
            match = flow_to_socket(proto, t0, t1, index)
            if match is None:
                continue
            inode, is_orig_ours = match
            pid = pid_map.get(inode)
            if pid is None:
                continue
            if is_orig_ours:
                sent, recv = d0, d1
            else:
                sent, recv = d1, d0
            if sent or recv:
                name = process_name(pid)
                entry = self.app_cum.setdefault(name, {"sent": 0, "recv": 0, "commands": {}})
                entry["sent"] += sent
                entry["recv"] += recv
                cmd = process_command(pid)
                cmd_entry = entry["commands"].setdefault(cmd, {"sent": 0, "recv": 0})
                cmd_entry["sent"] += sent
                cmd_entry["recv"] += recv

    def write_output(self):
        data = {
            "timestamp": datetime.now().isoformat(),
            "interface": self.interface,
            "cumulative": True,
            "apps": {
                name: dict(counts)
                for name, counts in sorted(
                    self.app_cum.items(),
                    key=lambda item: -(item[1]["sent"] + item[1]["recv"]),
                )
            },
        }
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        tmp = OUTPUT_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, OUTPUT_PATH)


def main():
    parser = argparse.ArgumentParser(
        description="WiFi Tracker per-app network collector (run as root)"
    )
    parser.add_argument("--interface", default="", help="WiFi interface (informational)")
    parser.add_argument("--interval", type=float, default=INTERVAL, help="Sample interval (s)")
    args = parser.parse_args()

    enable_accounting()
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        subprocess.run(["modprobe", "nf_conntrack"], capture_output=True, timeout=10)

    collector = Collector(args.interface, args.interval)
    sys.stderr.write(f"[perapp] started, interface={collector.interface}\n")
    while True:
        try:
            collector.sample()
            collector.write_output()
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[perapp] sample error: {e}\n")
        time.sleep(max(1.0, collector.interval))


if __name__ == "__main__":
    main()
