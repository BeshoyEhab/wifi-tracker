#!/usr/bin/env python3
"""
Enhanced WiFi Usage Tracker - Modular Version
A comprehensive tool for monitoring WiFi usage with daemon support
"""

import argparse
import sys
import time
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path
import psutil
from typing import Optional

try:
    from .data_manager import DataManager
    from .display_manager import DisplayManager, RICH_AVAILABLE
    from .network_monitor import NetworkMonitor
    from .process_manager import ProcessManager
    from .notification_manager import notifier, Urgency
    from .alert_manager import AlertManager
    from .app_manager import AppManager
except ImportError as e:
    try:
        from wifi_tracker_modules.data_manager import DataManager
        from wifi_tracker_modules.display_manager import DisplayManager, RICH_AVAILABLE
        from wifi_tracker_modules.network_monitor import NetworkMonitor
        from wifi_tracker_modules.process_manager import ProcessManager
        from wifi_tracker_modules.notification_manager import notifier, Urgency
        from wifi_tracker_modules.alert_manager import AlertManager
        from wifi_tracker_modules.app_manager import AppManager
    except ImportError:
        print(f"Error importing modules: {e}")
        print(
            "Please ensure wifi_tracker_modules directory exists with all required modules."
        )
        sys.exit(1)


class WiFiTracker:
    """Main WiFi Tracker application class"""

    def __init__(self, interface: str = "", interval: float = 0.5):
        """
        Initialize the WiFi Tracker application.

        Args:
            interface (str): Network interface to monitor. Auto-detected if empty.
            interval (float): Monitoring interval in seconds.
        """
        self.interface = interface
        self.interval = interval
        self.running = False
        self.start_time = datetime.now()
        self.last_ssid = None

        # Initialize modules
        self.monitor = NetworkMonitor(interface, interval)
        self.process_manager = ProcessManager("wifi-tracker")
        self.data_manager = DataManager()
        self.display_manager = DisplayManager()
        self.alert_manager = AlertManager(self.data_manager, self.process_manager)
        self.app_manager = AppManager(self.data_manager, self.process_manager, self.display_manager)

        # Update interface from monitor if auto-detected
        if not self.interface:
            self.interface = self.monitor.interface

        # Check dependencies
        if not RICH_AVAILABLE:
            print(
                "⚠️ 'rich' library not found. Installing it is recommended for a better experience."
            )
            if shutil.which("uv"):
                print("Tip: Run 'uv pip install rich' to install it.")
            else:
                print("Tip: Run 'pip install rich' to install it.")
            time.sleep(1)

    def _check_connection_change(self, current_ssid: str) -> None:
        if current_ssid != self.last_ssid:
            if current_ssid:
                notifier.send_notification(
                    "WiFi Connected", f"Connected to {current_ssid}", Urgency.NORMAL
                )
            elif self.last_ssid:
                notifier.send_notification(
                    "WiFi Disconnected",
                    f"Disconnected from {self.last_ssid}",
                    Urgency.NORMAL,
                )
            self.last_ssid = current_ssid

    def daemon_mode(self) -> None:
        """
        Run in daemon mode (background).

        Handles:
        1. Stopping existing instances
        2. Daemonizing the process
        3. Setting up signal handlers
        4. Starting the monitoring loop
        """
        print("🚀 Starting WiFi Tracker daemon...")

        # Kill all existing instances
        try:
            killed_count = self.process_manager.kill_all_instances()
            if killed_count > 0:
                print(f"✅ Killed {killed_count} existing instance(s)")
                time.sleep(2)

            # Double-check no instances remain
            remaining = self.process_manager.find_all_instances()
            if remaining:
                print(f"⚠️ Warning: {len(remaining)} instance(s) may still be running")
                for proc in remaining:
                    try:
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                time.sleep(1)

            if self.process_manager.is_daemon_running():
                print("❌ Daemon is already running!")
                return
        except Exception as e:
            print(f"❌ Error preparing daemon: {e}")
            return

        print(f"📡 Monitoring interface: {self.interface}")
        print(f"📊 Data will be saved to: {self.data_manager.data_file}")

        # Notify start
        notifier.send_notification(
            "WiFi Tracker", "Daemon started in background", Urgency.LOW
        )

        # Daemonize (skip if run from systemd — it manages the process)
        if os.environ.get("INVOCATION_ID"):
            print("📦 Running under systemd, skipping daemonize...")
        else:
            print("🔄 Daemonizing process...")
            try:
                self.process_manager.daemonize()
            except Exception as e:
                print(f"❌ Failed to daemonize: {e}")
                return

        # Setup daemon environment
        self.process_manager.create_pid_file()
        self.process_manager.setup_signal_handlers(self._cleanup)

        # Set running flag and start monitoring
        self.running = True
        self._daemon_monitoring_loop()

    def _daemon_monitoring_loop(self) -> None:
        """Main monitoring loop for daemon mode"""
        save_interval = 0.5
        last_save_time = time.time()
        last_app_check_time = 0
        notified_high_usage = set()
        known_apps = set()
        last_daily_summary_hour = -1

        while self.running:
            try:
                measurement = self.monitor.get_measurement()
                current_ssid = measurement.get("ssid") if measurement else None

                self._monitoring_tick(measurement, current_ssid, notified_high_usage)

                if measurement and current_ssid:
                    last_app_check_time = self._check_high_usage_periodically(
                        current_ssid, notified_high_usage, last_app_check_time
                    )
                    self.app_manager.check_new_apps(current_ssid, known_apps)

                    now_hour = datetime.now().hour
                    if now_hour == 0 and last_daily_summary_hour != 0:
                        self.alert_manager.send_daily_summary(current_ssid, self.display_manager)
                    last_daily_summary_hour = now_hour

                current_time = time.time()
                if current_time - last_save_time >= save_interval:
                    self.data_manager.save_data()
                    last_save_time = current_time

                time.sleep(self.interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.process_manager._log_error(f"Error in monitoring loop: {e}")
                time.sleep(1)

        self._cleanup()

    def _monitoring_tick(self, measurement: dict, current_ssid: str, notified_high_usage: set) -> None:
        """Single iteration of the monitoring loop (shared by daemon and watch mode)."""
        self._check_connection_change(current_ssid)

        if measurement and current_ssid:
            self._check_gateway(current_ssid, measurement)

            self.data_manager.update_usage(
                current_ssid,
                measurement["rx_bytes"],
                measurement["tx_bytes"],
                measurement["timestamp"],
                measurement["rx_rate"],
                measurement["tx_rate"],
                measurement.get("gateway_ip"),
            )

            current_usage = self.alert_manager.get_current_period_usage(current_ssid, self.display_manager)
            self.alert_manager.check_limits(current_ssid, current_usage)

    def _check_high_usage_periodically(self, current_ssid: str, notified_high_usage: set,
                                        last_check_time: float, interval: float = 60) -> float:
        """Check high-usage apps if enough time has passed. Returns updated last_check_time."""
        now = time.time()
        if now - last_check_time >= interval:
            self.app_manager.check_high_usage_apps(current_ssid, notified_high_usage)
            return now
        return last_check_time

    def _check_gateway(self, ssid: str, measurement: dict) -> None:
        """Verify gateway is legitimate. Prompt user if unknown."""
        gateway_ip = measurement.get("gateway_ip")
        gateway_mac = measurement.get("gateway_mac")
        vendor = measurement.get("vendor")

        if not gateway_ip:
            return

        # Skip if already known safe
        if self.data_manager.is_known_gateway(ssid, gateway_ip, gateway_mac):
            return

        # Unknown gateway - ask user
        choice = notifier.ask_gateway_trust(ssid, gateway_ip, gateway_mac or "", vendor or "")

        if choice == "trust":
            self.data_manager.add_known_gateway(ssid, gateway_ip, gateway_mac, vendor)
            self._log_info(f"User trusted gateway {gateway_ip} ({gateway_mac}) on {ssid}")
        elif choice == "block":
            self._log_info(f"User blocked gateway {gateway_ip} ({gateway_mac}) on {ssid}")
        else:
            self._log_info(f"Unknown gateway {gateway_ip} ({gateway_mac}) [{vendor}] on {ssid} - notification sent"                )

    def watch_mode(self) -> None:
        """Run in watch mode (interactive display)"""
        if RICH_AVAILABLE:
            from rich.live import Live

        print("Starting watch mode...")
        print("Press Ctrl+C to exit")
        time.sleep(1)

        self.running = True
        last_save_time = time.time()
        save_interval = 0.5
        update_count = 0
        last_app_check_time = 0
        notified_high_usage = set()
        current_pid = self.process_manager.get_process_info()["current_pid"]

        context = Live(auto_refresh=False) if RICH_AVAILABLE else open(os.devnull, "w")

        try:
            with context as live:
                while self.running:
                    current_time = datetime.now()
                    uptime = current_time - self.start_time
                    update_count += 1

                    measurement = self.monitor.get_measurement()
                    current_ssid = measurement.get("ssid") if measurement else None

                    self._monitoring_tick(measurement, current_ssid, notified_high_usage)

                    if measurement and current_ssid:
                        last_app_check_time = self._check_high_usage_periodically(
                            current_ssid, notified_high_usage, last_app_check_time
                        )

                    ssid_data = (
                        self.data_manager.usage_data.get(current_ssid, {})
                        if current_ssid
                        else {}
                    )
                    rx_rate = measurement.get("rx_rate", 0) if measurement else 0
                    tx_rate = measurement.get("tx_rate", 0) if measurement else 0

                    session_rx, session_tx = 0, 0
                    if measurement and current_ssid:
                        session_rx, session_tx = self.data_manager.get_session_usage(
                            current_ssid,
                            measurement["rx_bytes"],
                            measurement["tx_bytes"],
                        )

                    if RICH_AVAILABLE:
                        layout = self.display_manager.create_layout(
                            self.interface,
                            current_pid,
                            current_time,
                            uptime,
                            update_count,
                            current_ssid,
                            ssid_data,
                            rx_rate,
                            tx_rate,
                            self.data_manager.limits_data,
                            session_rx,
                            session_tx,
                        )
                        live.update(layout, refresh=True)
                    else:
                        display_content = self.display_manager.build_watch_display(
                            self.interface,
                            current_pid,
                            current_time,
                            uptime,
                            update_count,
                            current_ssid,
                            last_save_time,
                            ssid_data,
                            rx_rate,
                            tx_rate,
                            self.data_manager.limits_data,
                            self.interval,
                            session_rx,
                            session_tx,
                        )
                        self.display_manager.clear_screen()
                        print(display_content)

                    current_timestamp = time.time()
                    if current_timestamp - last_save_time >= save_interval:
                        self.data_manager.save_data()
                        last_save_time = current_timestamp

                    time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n👋 Exiting watch mode...")
            self.running = False
        finally:
            if not RICH_AVAILABLE:
                try:
                    context.close()
                except Exception:
                    pass

    # Reuse existing methods for stats, cleaning, etc.
    # Note: status_mode and status_all_mode use display_manager.print_detailed_stats which we updated

    def status_mode(
        self,
        custom_start_date: Optional[datetime] = None,
        custom_end_date: Optional[datetime] = None,
    ) -> None:
        """Show current status and statistics"""
        # Logic remains mostly same, just delegating to improved display manager
        try:
            self.data_manager.load_data()
            current_measurement = self.monitor.get_measurement()
            current_ssid = (
                current_measurement.get("ssid") if current_measurement else None
            )

            if current_measurement and current_ssid:
                self.data_manager.update_usage(
                    current_ssid,
                    current_measurement.get("rx_bytes", 0),
                    current_measurement.get("tx_bytes", 0),
                    current_measurement.get("timestamp", datetime.now()),
                    current_measurement.get("rx_rate", 0),
                    current_measurement.get("tx_rate", 0),
                    current_measurement.get("gateway_ip"),
                )

            if (
                not custom_start_date
                and current_ssid
                and current_ssid in self.data_manager.limits_data
            ):
                usage_from_str = self.data_manager.limits_data[current_ssid].get(
                    "usage_from"
                )
                if usage_from_str:
                    custom_start_date = datetime.strptime(usage_from_str, "%Y-%m-%d")

            self.display_manager.print_detailed_stats(
                self.data_manager.usage_data,
                self.data_manager.limits_data,
                current_ssid,
                current_measurement,
                custom_start_date,
                custom_end_date,
            )

            # Print process info (could be moved to display manager too, but fine here)
            process_info = self.process_manager.get_process_info()

            # Check for systemd
            systemd_status = (
                "Installed"
                if self.process_manager.is_systemd_installed()
                else "Not Installed"
            )

            print("\n🔧 Process Information:")
            print(f"Current PID: {process_info['current_pid']}")
            print(
                f"Daemon running: {'Yes' if process_info['daemon_running'] else 'No'}"
            )
            print(f"Systemd Service: {systemd_status}")
            print(f"Total instances: {process_info['total_instances']}")

        except Exception as e:
            print(f"❌ Error displaying status: {e}")

    def status_all_mode(self) -> None:
        """Show detailed statistics for all SSIDs"""
        self.display_manager.print_detailed_stats(
            self.data_manager.usage_data,
            self.data_manager.limits_data,
        )

    def top_apps_mode(self) -> None:
        """Show top 10 applications"""
        try:
            ssid = self.monitor.get_current_ssid()
            top_apps = self.process_manager.get_top_network_apps(limit=10, ssid=ssid)
            self.display_manager.print_top_network_apps(top_apps)
        except Exception as e:
            print(f"❌ Error getting top apps: {e}")

    def stop_daemon(self):
        """Stop daemon mode"""
        if not self.process_manager.is_daemon_running():
            print("❌ No daemon is currently running")
            return

        killed_count = self.process_manager.kill_all_instances()
        if killed_count > 0:
            print(f"✅ Stopped daemon (killed {killed_count} instance(s))")
            notifier.send_notification("WiFi Tracker", "Daemon stopped", Urgency.LOW)
        else:
            print("❌ Failed to stop daemon")

    def set_limit(self, ssid: str, limit: str, interval: str = "monthly"):
        """Set data limit for SSID"""
        limit_bytes = AlertManager.parse_size(limit)
        if limit_bytes is None:
            print(f"Invalid limit format: {limit}")
            print("Use format like: 1GB, 500MB, 1024KB, or raw bytes")
            return

        self.data_manager.set_limit(ssid, limit_bytes, interval)
        print(
            f"Set {interval} limit for '{ssid}': {self.display_manager.format_bytes(limit_bytes)}"
        )

    def remove_limit(self, ssid: str):
        """Remove data limit for SSID"""
        if self.data_manager.remove_limit(ssid):
            print(f"✅ Removed limit for '{ssid}'")
        else:
            print(f"❌ No limit found for '{ssid}'")

    def set_usage_from(self, ssid: str, date: str):
        """Set custom start date for usage calculation for SSID"""
        date_lower = date.lower()

        if date_lower.endswith("weeks"):
            weeks = int(date_lower[:-5])
            start_date = datetime.now() - timedelta(weeks=weeks)
            date_str = start_date.strftime("%Y-%m-%d")
        elif date_lower.endswith("week"):
            weeks = int(date_lower[:-4])
            start_date = datetime.now() - timedelta(weeks=weeks)
            date_str = start_date.strftime("%Y-%m-%d")
        elif date_lower.endswith("months"):
            months = int(date_lower[:-6])
            start_date = datetime.now() - timedelta(days=months * 30)
            date_str = start_date.strftime("%Y-%m-%d")
        elif date_lower.endswith("month"):
            months = int(date_lower[:-5])
            start_date = datetime.now() - timedelta(days=months * 30)
            date_str = start_date.strftime("%Y-%m-%d")
        elif date_lower.endswith("days"):
            days = int(date_lower[:-4])
            start_date = datetime.now() - timedelta(days=days)
            date_str = start_date.strftime("%Y-%m-%d")
        elif date_lower.endswith("day"):
            days = int(date_lower[:-3])
            start_date = datetime.now() - timedelta(days=days)
            date_str = start_date.strftime("%Y-%m-%d")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
                date_str = date
            except ValueError:
                print(
                    f"❌ Invalid date format: {date}. Use YYYY-MM-DD or relative like 2weeks, 1month, 14days"
                )
                return

        self.data_manager.set_limit(ssid, 0, "monthly", date_str)
        print(f"✅ Set usage start date for '{ssid}' to {date_str} (relative: {date})")

    def cleanup_data(self, days: int = 30):
        """Clean up old data"""
        removed_count = self.data_manager.cleanup_old_data(days)
        if removed_count > 0:
            self.data_manager.save_data()
            print(
                f"✅ Cleaned up {removed_count} old daily records (older than {days} days)"
            )
        else:
            print(f"ℹ️ No old data to clean up (older than {days} days)")

    def install_service(self):
        """Install systemd service"""
        exe_path = str(Path(sys.argv[0]).resolve())
        # If running via pipx or normal python script, execution path might vary
        # Using sys.argv[0] is generally safe for finding the startup command
        self.process_manager.install_systemd_service(exe_path)

    def remove_service(self):
        """Remove systemd service"""
        self.process_manager.remove_systemd_service()

    def networks_mode(self):
        """Show saved networks with gateway IPs"""
        networks = self.data_manager.get_networks()
        if not networks:
            print("No saved networks.")
            return

        if RICH_AVAILABLE:
            from rich.table import Table
            from rich.console import Console
            from rich.box import ROUNDED

            console = Console()
            table = Table(title="Saved Networks", box=ROUNDED, expand=True)
            table.add_column("SSID", style="bold cyan")
            table.add_column("Gateway IP", style="yellow")
            table.add_column("Total Usage", justify="right")
            table.add_column("Last Seen", style="dim")

            for net in sorted(networks, key=lambda x: x.get("last_seen") or "", reverse=True):
                total = net["total_rx"] + net["total_tx"]
                gw = net.get("gateway_ip") or "N/A"
                last = net.get("last_seen", "Unknown")
                if isinstance(last, str) and len(last) > 16:
                    last = last[:16]
                table.add_row(net["ssid"], gw, self.display_manager.format_bytes(total), last)

            console.print(table)
        else:
            for net in networks:
                total = net["total_rx"] + net["total_tx"]
                gw = net.get("gateway_ip") or "N/A"
                print(f"{net['ssid']}\t{gw}\t{total} bytes")

    def alert_mode(self, args: list) -> None:
        """Configure or show high-usage alert settings."""
        if len(args) == 1 and args[0] == "show":
            settings = self.data_manager.get_alert_settings()
            threshold = settings["threshold_bytes"]
            window = settings["window_hours"]
            print(f"Alert threshold: {self.display_manager.format_bytes(threshold)}")
            print(f"Time window: {AlertManager.format_window(window)}")
            return

        if len(args) != 2:
            print("Usage: wifi-tracker alert <threshold> <window>")
            print("  Examples:")
            print("    wifi-tracker alert 5G 1h")
            print("    wifi-tracker alert 500M 30m")
            print("    wifi-tracker alert 2G 2d")
            print("    wifi-tracker alert show")
            return

        threshold_bytes = AlertManager.parse_threshold(args[0])
        if threshold_bytes is None:
            print(f"Invalid threshold: {args[0]}")
            return

        window_hours = AlertManager.parse_window(args[1])
        if window_hours is None or window_hours < 1 / 60:
            print(f"Invalid time window: {args[1]}")
            return

        self.data_manager.set_alert_settings(
            threshold_bytes=threshold_bytes,
            window_hours=window_hours,
        )
        print(f"Alert set: {self.display_manager.format_bytes(threshold_bytes)} in {AlertManager.format_window(window_hours)}")

    def _cleanup(self):
        """Cleanup resources"""
        self.running = False
        self.data_manager.save_data()
        self.process_manager.remove_pid_file()

    def _log_info(self, message: str) -> None:
        """Log info message to log file."""
        self.process_manager._log_info(message)
        notifier.send_notification("WiFi Tracker", "WiFi Tracker stopped", Urgency.LOW)


def main():
    """Main entry point"""
    # Check for --complete early (before any parsing)
    if "--complete" in sys.argv:
        idx = sys.argv.index("--complete")
        if idx + 2 < len(sys.argv):
            _handle_completion(sys.argv[idx + 1], sys.argv[idx + 2])
        sys.exit(0)

    parser = argparse.ArgumentParser(
        prog="wifi-tracker",
        description="WiFi Usage Tracker — monitor, limit, and secure your network.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
  MONITORING
    daemon, d           Start background monitoring
    watch, w            Live interactive dashboard
    status, s           Show usage statistics
    today, t            Quick one-line status
    graph, g            ASCII usage graph (24h)
    top-apps            Show apps using the network
    networks            Show saved networks

  LIMITS & ALERTS
    limit               Set data limit (daily/weekly/monthly)
    remove-limit        Remove a data limit
    usage-from          Set custom usage start date
    alert               Configure high-usage alerts

  SECURITY
    trust-gateway       Trust a gateway (MITM protection)
    trusted-gateways    List trusted gateways
    mark-safe           Mark app as safe (won't alert/kill)
    safe-apps           List trusted apps
    kill-app            Kill app or auto-kill on limit
    kill-list           List auto-kill apps

  MANAGEMENT
    stop                Stop the daemon
    cleanup             Clean old data
    install-service     Install systemd service
    remove-service      Remove systemd service

  RANGE (for graph, status, today)
    --range 1h          Last hour (per minute)
    --range 24h         Last 24 hours (per hour) [default]
    --range 7d          Last 7 days
    --range 30d         Last 30 days
    --range 12m         Last 12 months

  EXAMPLES
    wifi-tracker daemon                         Start monitoring
    wifi-tracker limit HomeWiFi 5GB monthly     Set 5GB monthly cap
    wifi-tracker alert 2GB 1h                   Alert on 2GB/hour
    wifi-tracker graph --range 1h               Last hour per minute
    wifi-tracker graph --range 7d               Last 7 days
    wifi-tracker status --range 30d             Last 30 days stats
    wifi-tracker trust-gateway HomeWiFi 10.0.0.1 Trust your router
    wifi-tracker mark-safe HomeWiFi firefox --always  Always allow firefox
    wifi-tracker today                          Quick status check
""",
    )

    # Global options
    parser.add_argument("--interface", "-i", help="Network interface to monitor")
    parser.add_argument(
        "--interval", type=float, default=0.5, help="Update interval in seconds"
    )

    subparsers = parser.add_subparsers(dest="command", help="See categories below")

    # ── Monitoring ──────────────────────────────────────────────
    subparsers.add_parser("daemon", aliases=["d"], help="Start background monitoring")
    subparsers.add_parser("watch", aliases=["w"], help="Live interactive dashboard")

    status_p = subparsers.add_parser("status", aliases=["s"], help="Show usage statistics")
    status_p.add_argument("--all", action="store_true", help="Show all networks")
    status_p.add_argument("--from-date", help="Start date (YYYY-MM-DD)")
    status_p.add_argument("--to-date", help="End date (YYYY-MM-DD)")
    status_p.add_argument("--range", dest="range_str", default="24h",
                          choices=["1h", "24h", "7d", "30d", "12m"],
                          help="Time range (default: 24h)")

    today_p = subparsers.add_parser("today", aliases=["t"], help="Quick one-line status")
    today_p.add_argument("--range", dest="range_str", default="24h",
                         choices=["1h", "24h", "7d", "30d", "12m"],
                         help="Time range (default: 24h)")

    graph_p = subparsers.add_parser("graph", aliases=["g"], help="ASCII usage graph")
    graph_p.add_argument("ssid", nargs="?", help="Network SSID (omit for current)")
    graph_p.add_argument("--range", dest="range_str", default="24h",
                         choices=["1h", "24h", "7d", "30d", "12m"],
                         help="Time range (default: 24h)")

    top_apps_p = subparsers.add_parser("top-apps", help="Show apps using the network")
    top_apps_p.add_argument("--range", dest="range_str", default="24h",
                            choices=["1h", "24h", "7d", "30d", "12m"],
                            help="Time range (default: 24h)")
    subparsers.add_parser("networks", help="Show saved networks")

    # ── Limits & Alerts ─────────────────────────────────────────
    limit_p = subparsers.add_parser("limit", help="Set data limit")
    limit_p.add_argument("ssid", help="Network SSID")
    limit_p.add_argument("size", help="Limit size (e.g. 1GB, 500MB)")
    limit_p.add_argument("interval", choices=["daily", "weekly", "monthly"], help="Limit interval")

    rm_limit_p = subparsers.add_parser("remove-limit", help="Remove a data limit")
    rm_limit_p.add_argument("ssid", help="Network SSID")

    usage_p = subparsers.add_parser("usage-from", help="Set custom usage start date")
    usage_p.add_argument("ssid", help="Network SSID")
    usage_p.add_argument("date", help="Start date (YYYY-MM-DD or relative like 2weeks)")

    alert_p = subparsers.add_parser("alert", help="Configure high-usage alerts")
    alert_p.add_argument("args", nargs="*", help="show | <threshold> <window> (e.g. 2GB 1h)")

    # ── Security ────────────────────────────────────────────────
    trust_gw_p = subparsers.add_parser("trust-gateway", help="Trust a gateway (MITM protection)")
    trust_gw_p.add_argument("ssid", help="Network SSID")
    trust_gw_p.add_argument("gateway_ip", help="Gateway IP address")
    trust_gw_p.add_argument("--mac", help="Gateway MAC address (optional)")

    trusted_gw_p = subparsers.add_parser("trusted-gateways", help="List trusted gateways")
    trusted_gw_p.add_argument("ssid", nargs="?", help="Network SSID (omit for all)")

    mark_safe_p = subparsers.add_parser("mark-safe", help="Mark app as safe (won't alert/kill)")
    mark_safe_p.add_argument("ssid", help="Network SSID")
    mark_safe_p.add_argument("app_name", help="Process/command name")
    mark_safe_p.add_argument("--always", action="store_true", help="Always safe (not just once)")

    safe_apps_p = subparsers.add_parser("safe-apps", help="List trusted apps")
    safe_apps_p.add_argument("ssid", nargs="?", help="Network SSID (omit for all)")

    kill_app_p = subparsers.add_parser("kill-app", help="Kill app or auto-kill on limit")
    kill_app_p.add_argument("ssid", help="Network SSID")
    kill_app_p.add_argument("app_name", help="Process/command name")
    kill_app_p.add_argument("--always", action="store_true", help="Always kill when exceeding limit")

    kill_list_p = subparsers.add_parser("kill-list", help="List auto-kill apps")
    kill_list_p.add_argument("ssid", nargs="?", help="Network SSID (omit for all)")

    # ── Management ──────────────────────────────────────────────
    subparsers.add_parser("stop", help="Stop the daemon")

    cleanup_p = subparsers.add_parser("cleanup", help="Clean old data")
    cleanup_p.add_argument("days", nargs="?", type=int, default=90, help="Days to keep (default: 90)")

    subparsers.add_parser("install-service", help="Install systemd service")
    subparsers.add_parser("remove-service", help="Remove systemd service")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Resolve aliases
    command = args.command
    if command in ("d",):
        command = "daemon"
    elif command in ("w",):
        command = "watch"
    elif command in ("s",):
        command = "status"

    # Create tracker instance
    tracker = WiFiTracker(args.interface, args.interval)

    try:
        if command == "daemon":
            tracker.daemon_mode()
        elif command == "watch":
            tracker.watch_mode()
        elif command == "status":
            custom_start_date = None
            custom_end_date = None
            if args.from_date:
                custom_start_date = datetime.strptime(args.from_date, "%Y-%m-%d")
            if args.to_date:
                custom_end_date = datetime.strptime(args.to_date, "%Y-%m-%d")
            if args.from_date and not args.to_date:
                custom_end_date = datetime.now()
            if not custom_start_date and not custom_end_date:
                range_str = getattr(args, 'range_str', '24h')
                range_days = {"1h": 0, "24h": 1, "7d": 7, "30d": 30, "12m": 365}
                days = range_days.get(range_str, 1)
                if days > 0:
                    custom_start_date = datetime.now() - timedelta(days=days)
                    custom_end_date = datetime.now()
            if args.all:
                tracker.status_all_mode()
            else:
                tracker.status_mode(custom_start_date, custom_end_date)
        elif command == "top-apps":
            tracker.top_apps_mode()
        elif command == "stop":
            tracker.stop_daemon()
        elif command == "networks":
            tracker.networks_mode()
        elif command == "limit":
            tracker.set_limit(args.ssid, args.size, args.interval)
        elif command == "remove-limit":
            tracker.remove_limit(args.ssid)
        elif command == "usage-from":
            tracker.set_usage_from(args.ssid, args.date)
        elif command == "cleanup":
            tracker.cleanup_data(args.days)
        elif command == "alert":
            tracker.alert_mode(args.args)
        elif command == "install-service":
            tracker.install_service()
        elif command == "remove-service":
            tracker.remove_service()
        elif command == "mark-safe":
            tracker.data_manager.mark_app_safe(args.ssid, args.app_name, args.always)
            mode = "always" if args.always else "once"
            print(f"✓ Marked '{args.app_name}' as safe ({mode}) on {args.ssid}")
        elif command == "kill-app":
            # Kill immediately and optionally mark for future auto-kill
            killed = tracker.data_manager.kill_app(args.app_name)
            if killed:
                print(f"✓ Killed {killed} process(es) named '{args.app_name}'")
            else:
                print(f"No running processes found for '{args.app_name}'")
            if args.always:
                tracker.data_manager.mark_app_kill(args.ssid, args.app_name, always=True)
                print(f"✓ Will auto-kill '{args.app_name}' when exceeding limit on {args.ssid}")
            else:
                tracker.data_manager.mark_app_kill(args.ssid, args.app_name, always=False)
                print(f"✓ Will kill '{args.app_name}' once when exceeding limit on {args.ssid}")
        elif command == "trust-gateway":
            tracker.data_manager.add_known_gateway(
                args.ssid, args.gateway_ip, args.mac or ""
            )
            print(f"✓ Trusted gateway {args.gateway_ip} on {args.ssid}")
        elif command == "safe-apps":
            ssid_filter = args.ssid
            found = False
            for ssid, data in tracker.data_manager.usage_data.items():
                if ssid_filter and ssid != ssid_filter:
                    continue
                all_safe = list(data.get("safe_apps", []))
                onetime = data.get("safe_apps_onetime", [])
                if all_safe or onetime:
                    found = True
                    print(f"\n{ssid}:")
                    for app in all_safe:
                        print(f"  {app} (always)")
                    for app in onetime:
                        print(f"  {app} (once)")
            if not found:
                print("No safe apps configured.")
        elif command == "kill-list":
            ssid_filter = args.ssid
            found = False
            for ssid, data in tracker.data_manager.usage_data.items():
                if ssid_filter and ssid != ssid_filter:
                    continue
                all_kill = list(data.get("kill_apps", []))
                onetime = data.get("kill_apps_onetime", [])
                if all_kill or onetime:
                    found = True
                    print(f"\n{ssid}:")
                    for app in all_kill:
                        print(f"  {app} (always)")
                    for app in onetime:
                        print(f"  {app} (once)")
            if not found:
                print("No apps marked for auto-kill.")
        elif command == "trusted-gateways":
            ssid_filter = args.ssid
            found = False
            for ssid, data in tracker.data_manager.usage_data.items():
                if ssid_filter and ssid != ssid_filter:
                    continue
                gateways = data.get("known_gateways", [])
                if gateways:
                    found = True
                    print(f"\n{ssid}:")
                    for gw in gateways:
                        vendor = gw.get("vendor") or ""
                        mac = gw.get("mac") or ""
                        ip = gw.get("ip", "")
                        if vendor:
                            print(f"  {ip} ({mac}) [{vendor}]" if mac else f"  {ip} [{vendor}]")
                        else:
                            print(f"  {ip} ({mac})" if mac else f"  {ip}")
            if not found:
                print("No trusted gateways configured.")
        elif command in ("today", "t"):
            measurement = tracker.monitor.get_measurement()
            current_ssid = measurement.get("ssid") if measurement else None
            if not current_ssid:
                print("Not connected to any network.")
            else:
                range_str = getattr(args, 'range_str', '24h')
                range_usage = sum(v for _, v in tracker.data_manager.get_usage_for_graph(current_ssid, range_str))
                ssid_data = tracker.data_manager.usage_data.get(current_ssid, {})
                total = ssid_data.get("total_rx", 0) + ssid_data.get("total_tx", 0)
                rate_up = measurement.get("tx_rate", 0)
                rate_down = measurement.get("rx_rate", 0)
                limit_info = tracker.data_manager.limits_data.get(current_ssid, {})
                limit = limit_info.get("limit", 0)
                top_app = ""
                try:
                    apps = tracker.process_manager.get_top_network_apps(limit=1)
                    if apps:
                        top_app = apps[0].get("name", "")
                except Exception:
                    pass
                tracker.display_manager.print_quick_status(
                    current_ssid, range_usage, total, rate_up, rate_down, limit, top_app
                )
        elif command in ("graph", "g"):
            target_ssid = getattr(args, 'ssid', None)
            if not target_ssid:
                measurement = tracker.monitor.get_measurement()
                target_ssid = measurement.get("ssid") if measurement else None
            if not target_ssid:
                print("Not connected to any network. Usage: wifi-tracker graph SSID")
            else:
                tracker.data_manager.load_data()
                range_str = getattr(args, 'range_str', '24h')
                hourly = tracker.data_manager.get_usage_for_graph(target_ssid, range_str)
                tracker.display_manager.print_ascii_graph(hourly, target_ssid, range_label=range_str)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        tracker._cleanup()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _handle_completion(shell: str, comp_word: str) -> None:
    """Output shell completion suggestions based on context."""
    import os
    all_words = os.environ.get("COMP_WORDS", comp_word).split()
    # Filter out everything except the actual command words
    words = []
    skip_next = False
    for w in all_words:
        if skip_next:
            skip_next = False
            continue
        if w == "--complete":
            skip_next = True
            continue
        if w in ("wifi-tracker", shell):
            continue
        if w:  # skip empty strings from trailing spaces
            words.append(w)

    cur = comp_word.lower()

    # Load saved networks
    networks = []
    try:
        from .data_manager import DataManager
        dm = DataManager()
        networks = [ssid for ssid in dm.usage_data if not ssid.startswith("_")]
    except Exception:
        pass

    # If cur is in words, it's being completed (not a new word)
    if words and words[-1].lower() == cur:
        words = words[:-1]

    prev = words[-1].lower() if words else ""
    cmd = words[0].lower() if words else ""
    argc = len(words)  # number of complete args (excluding current word)

    suggestions = []

    if argc == 0:
        # No subcommand: show commands only
        all_cmds = [
            "daemon", "watch", "status", "today", "graph", "top-apps", "networks",
            "limit", "remove-limit", "usage-from", "alert",
            "trust-gateway", "trusted-gateways", "mark-safe", "safe-apps",
            "kill-app", "kill-list",
            "stop", "cleanup", "install-service", "remove-service",
        ]
        for c in all_cmds:
            if c.startswith(cur):
                suggestions.append(c)
    elif argc == 1 and cmd in ("limit", "remove-limit", "usage-from", "mark-safe", "kill-app", "trust-gateway"):
        # SSID arg
        for net in networks:
            if net.lower().startswith(cur):
                suggestions.append(net)
    elif argc == 1 and cmd in ("safe-apps", "kill-list", "trusted-gateways", "graph"):
        # Optional SSID
        for net in networks:
            if net.lower().startswith(cur):
                suggestions.append(net)
    elif argc == 2 and cmd in ("mark-safe", "kill-app"):
        # App name arg
        try:
            from .process_manager import ProcessManager
            pm = ProcessManager("wifi-tracker")
            apps = pm.get_top_network_apps(limit=30)
            for app in apps:
                name = app.get("name", "")
                if name.startswith(cur):
                    suggestions.append(name)
        except Exception:
            pass
    elif argc == 2 and cmd == "limit":
        # Size arg
        for hint in ["1GB", "2GB", "5GB", "10GB", "500MB"]:
            if hint.lower().startswith(cur):
                suggestions.append(hint)
    elif argc == 3 and cmd == "limit":
        # Interval arg
        for interval in ["daily", "weekly", "monthly"]:
            if interval.startswith(cur):
                suggestions.append(interval)
    elif argc == 1 and cmd == "alert":
        for hint in ["show", "1GB", "2GB", "5GB"]:
            if hint.lower().startswith(cur):
                suggestions.append(hint)
    elif argc == 1 and cmd in ("today", "top-apps"):
        for hint in ["--range"]:
            if hint.startswith(cur):
                suggestions.append(hint)
    elif argc == 1 and cmd in ("stop", "install-service", "remove-service", "networks"):
        pass
    elif argc == 1 and cmd == "status":
        for hint in ["--all", "--from-date", "--to-date", "--range"]:
            if hint.startswith(cur):
                suggestions.append(hint)
    elif argc == 1 and cmd == "graph":
        for hint in ["--range"]:
            if hint.startswith(cur):
                suggestions.append(hint)
    elif argc == 1 and cmd == "cleanup":
        for hint in ["30", "60", "90", "365"]:
            if hint.startswith(cur):
                suggestions.append(hint)
    elif prev == "--range":
        for hint in ["1h", "24h", "7d", "30d", "12m"]:
            if hint.startswith(cur):
                suggestions.append(hint)
    elif prev in ("--interface", "-i"):
        import glob
        for iface in glob.glob("/sys/class/net/*"):
            name = iface.split("/")[-1]
            if name.startswith(cur):
                suggestions.append(name)
    else:
        # Fallback: show commands
        all_cmds = [
            "daemon", "watch", "status", "today", "graph", "top-apps", "networks",
            "limit", "remove-limit", "usage-from", "alert",
            "trust-gateway", "trusted-gateways", "mark-safe", "safe-apps",
            "kill-app", "kill-list",
            "stop", "cleanup", "install-service", "remove-service",
        ]
        for c in all_cmds:
            if c.startswith(cur):
                suggestions.append(c)

    # Output suggestions
    result = sorted(set(suggestions))
    if not result:
        return

    if shell == "fish":
        # Fish needs one suggestion per line
        print("\n".join(result))
    else:
        # Columnar output for bash/zsh
        try:
            import shutil
            term_width = shutil.get_terminal_size().columns
        except Exception:
            term_width = 80

        max_len = max(len(s) for s in result)
        col_width = max_len + 2
        cols = max(1, term_width // col_width)

        lines = []
        for i in range(0, len(result), cols):
            row = result[i:i + cols]
            lines.append("".join(s.ljust(col_width) for s in row))

        print("\n".join(lines))


if __name__ == "__main__":
    main()
