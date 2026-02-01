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
from datetime import datetime
from pathlib import Path
import psutil
from typing import Optional

try:
    from .data_manager import DataManager
    from .display_manager import DisplayManager, RICH_AVAILABLE
    from .network_monitor import NetworkMonitor
    from .process_manager import ProcessManager
    from .notification_manager import notifier, Urgency
    from .config import Config
except ImportError as e:
    # Fallback for direct execution/testing if not installed as package
    try:
        from wifi_tracker_modules.data_manager import DataManager
        from wifi_tracker_modules.display_manager import DisplayManager, RICH_AVAILABLE
        from wifi_tracker_modules.network_monitor import NetworkMonitor
        from wifi_tracker_modules.process_manager import ProcessManager
        from wifi_tracker_modules.notification_manager import notifier, Urgency
        from wifi_tracker_modules.config import Config
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

        # Update interface from monitor if auto-detected
        if not self.interface:
            self.interface = self.monitor.interface
            
        # Check dependencies
        if not RICH_AVAILABLE:
            print("⚠️ 'rich' library not found. Installing it is recommended for a better experience.")
            if shutil.which("uv"):
                print("Tip: Run 'uv pip install rich' to install it.")
            else:
                print("Tip: Run 'pip install rich' to install it.")
            time.sleep(1)

    def _check_connection_change(self, current_ssid: str) -> None:
        """
        Check and notify if connection changed (helper for both modes).

        Args:
            current_ssid (str): The currently connected SSID.
        """
        if current_ssid != self.last_ssid:
            if current_ssid:
                notifier.send_notification(
                    "WiFi Connected", 
                    f"Connected to {current_ssid}",
                    Urgency.NORMAL
                )
            elif self.last_ssid:
                notifier.send_notification(
                    "WiFi Disconnected", 
                    f"Disconnected from {self.last_ssid}", 
                    Urgency.NORMAL
                )
            self.last_ssid = current_ssid

    def _check_limits(self, ssid: str, current_usage: int) -> None:
        """
        Check data limits and notify if needed.

        Args:
            ssid (str): The SSID to check limits for.
            current_usage (int): Current usage in bytes for the limit period.
        """
        if ssid in self.data_manager.limits_data:
            limit_info = self.data_manager.limits_data[ssid]
            limit = limit_info.get('limit', 0)
            if limit > 0:
                percent = (current_usage / limit) * 100
                
                # Check 100%
                if percent >= 100 and not limit_info.get('notified_100', False):
                    notifier.send_notification(
                        "Data Limit Reached",
                        f"You have reached your data limit for {ssid}!",
                        Urgency.CRITICAL
                    )
                    self.data_manager.update_limit_status(ssid, 'notified_100', True)
                
                # Check 80%
                elif percent >= 80 and percent < 100 and not limit_info.get('notified_80', False):
                    notifier.send_notification(
                        "Data Limit Warning",
                        f"You have used {percent:.1f}% of your data limit for {ssid}.",
                        Urgency.NORMAL
                    )
                    self.data_manager.update_limit_status(ssid, 'notified_80', True)
                    
                # Reset if below 80 (e.g. limit increased or new period)
                elif percent < 80:
                    if limit_info.get('notified_80', False):
                         self.data_manager.update_limit_status(ssid, 'notified_80', False)
                    if limit_info.get('notified_100', False):
                         self.data_manager.update_limit_status(ssid, 'notified_100', False)


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
        notifier.send_notification("WiFi Tracker", "Daemon started in background", Urgency.LOW)

        # Daemonize
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

        while self.running:
            try:
                # Get network measurement
                measurement = self.monitor.get_measurement()
                current_ssid = measurement.get("ssid") if measurement else None
                
                # Notify on connection change
                self._check_connection_change(current_ssid)

                if measurement and current_ssid:
                    # Update usage data
                    self.data_manager.update_usage(
                        current_ssid,
                        measurement["rx_bytes"],
                        measurement["tx_bytes"],
                        measurement["timestamp"],
                        measurement["rx_rate"],
                        measurement["tx_rate"],
                    )
                    
                    # Check limits
                    current_usage = self._get_current_period_usage(current_ssid)
                    self._check_limits(current_ssid, current_usage)

                # Save data periodically
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
        
    def _get_current_period_usage(self, ssid: str) -> int:
        """Helper to get current usage based on limit interval"""
        if ssid not in self.data_manager.limits_data:
            return 0
            
        interval = self.data_manager.limits_data[ssid].get('interval', 'monthly')
        ssid_data = self.data_manager.usage_data.get(ssid, {})
        return self.display_manager._calculate_period_usage(ssid_data, interval)

    def watch_mode(self) -> None:
        """Run in watch mode (interactive display)"""
        if RICH_AVAILABLE:
            from rich.live import Live
        
        print("🔄 Starting watch mode...")
        print("Press Ctrl+C to exit")
        time.sleep(1)

        self.running = True
        last_save_time = time.time()
        save_interval = 0.5
        update_count = 0
        
        # Context manager for Rich Live or dummy for basic print
        context = Live(auto_refresh=False) if RICH_AVAILABLE else open(os.devnull, 'w')
        
        # If not using Rich, we just print periodically
        # If using Rich, we update the Live display

        try:
            # We enter the context (Live or dummy)
            # If dummy (file), __enter__ returns the file object, which we ignore
            with context as live:
                while self.running:
                    current_time = datetime.now()
                    uptime = current_time - self.start_time
                    update_count += 1

                    # Get current measurement
                    measurement = self.monitor.get_measurement()
                    current_ssid = measurement.get("ssid") if measurement else None
                    
                    self._check_connection_change(current_ssid)

                    # Update data if connected
                    if measurement and current_ssid:
                        self.data_manager.update_usage(
                            current_ssid,
                            measurement["rx_bytes"],
                            measurement["tx_bytes"],
                            measurement["timestamp"],
                            measurement["rx_rate"],
                            measurement["tx_rate"],
                        )
                        
                        # Check limits
                        current_usage = self._get_current_period_usage(current_ssid)
                        self._check_limits(current_ssid, current_usage)

                    # Get SSID data for display
                    ssid_data = (
                        self.data_manager.usage_data.get(current_ssid, {})
                        if current_ssid
                        else {}
                    )
                    rx_rate = measurement.get("rx_rate", 0) if measurement else 0
                    tx_rate = measurement.get("tx_rate", 0) if measurement else 0

                    # Get session usage
                    session_rx, session_tx = 0, 0
                    if measurement and current_ssid:
                        session_rx, session_tx = self.data_manager.get_session_usage(
                            current_ssid, measurement["rx_bytes"], measurement["tx_bytes"]
                        )

                    # Display
                    if RICH_AVAILABLE:
                         layout = self.display_manager.create_layout(
                            self.interface,
                            self.process_manager.get_process_info()["current_pid"],
                            current_time,
                            uptime,
                            update_count,
                            current_ssid,
                            ssid_data,
                            rx_rate,
                            tx_rate,
                            self.data_manager.limits_data,
                            session_rx,
                            session_tx
                         )
                         live.update(layout, refresh=True)
                    else:
                        # Legacy display
                        display_content = self.display_manager.build_watch_display(
                            self.interface,
                            self.process_manager.get_process_info()["current_pid"],
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

                    # Handle saving
                    current_timestamp = time.time()
                    if current_timestamp - last_save_time >= save_interval:
                        self.data_manager.save_data()
                        last_save_time = current_timestamp

                    # Sleep
                    time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n👋 Exiting watch mode...")
            self.running = False
        finally:
             if not RICH_AVAILABLE:
                 try: context.close()
                 except: pass

    # Reuse existing methods for stats, cleaning, etc.
    # Note: status_mode and status_all_mode use display_manager.print_detailed_stats which we updated
    
    def status_mode(self) -> None:
        """Show current status and statistics"""
        # Logic remains mostly same, just delegating to improved display manager
        try:
            self.data_manager.load_data()
            current_measurement = self.monitor.get_measurement()
            current_ssid = current_measurement.get("ssid") if current_measurement else None
            
            if current_measurement and current_ssid:
                 self.data_manager.update_usage(
                    current_ssid,
                    current_measurement.get("rx_bytes", 0),
                    current_measurement.get("tx_bytes", 0),
                    current_measurement.get("timestamp", datetime.now()),
                    current_measurement.get("rx_rate", 0),
                    current_measurement.get("tx_rate", 0),
                 )

            self.display_manager.print_detailed_stats(
                self.data_manager.usage_data,
                self.data_manager.limits_data,
                current_ssid,
                current_measurement,
            )
            
            # Print process info (could be moved to display manager too, but fine here)
            process_info = self.process_manager.get_process_info()
            
            # Check for systemd
            systemd_status = "Installed" if self.process_manager.is_systemd_installed() else "Not Installed"
            
            print(f"\n🔧 Process Information:")
            print(f"Current PID: {process_info['current_pid']}")
            print(f"Daemon running: {'Yes' if process_info['daemon_running'] else 'No'}")
            print(f"Systemd Service: {systemd_status}")
            print(f"Total instances: {process_info['total_instances']}")

        except Exception as e:
            print(f"❌ Error displaying status: {e}")

    def status_all_mode(self) -> None:
         """Show detailed statistics for all SSIDs"""
         # Delegated to display manager
         self.status_mode() # For now status mode prints everything with Rich table anyway

    def top_apps_mode(self) -> None:
        """Show top 10 applications"""
        try:
            top_apps = self.process_manager.get_top_network_apps(limit=10)
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
        try:
            # Parse limit (e.g., "1GB", "500MB")
            limit_upper = limit.upper()
            if limit_upper.endswith("GB"):
                limit_bytes = int(float(limit_upper[:-2]) * 1024 * 1024 * 1024)
            elif limit_upper.endswith("MB"):
                limit_bytes = int(float(limit_upper[:-2]) * 1024 * 1024)
            elif limit_upper.endswith("KB"):
                limit_bytes = int(float(limit_upper[:-2]) * 1024)
            else:
                limit_bytes = int(limit)

            self.data_manager.set_limit(ssid, limit_bytes, interval)
            print(
                f"✅ Set {interval} limit for '{ssid}': {self.display_manager.format_bytes(limit_bytes)}"
            )

        except ValueError:
            print(f"❌ Invalid limit format: {limit}")
            print("Use format like: 1GB, 500MB, 1024KB, or raw bytes")

    def remove_limit(self, ssid: str):
        """Remove data limit for SSID"""
        if self.data_manager.remove_limit(ssid):
            print(f"✅ Removed limit for '{ssid}'")
        else:
            print(f"❌ No limit found for '{ssid}'")

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

    def _cleanup(self):
        """Cleanup resources"""
        self.running = False
        self.data_manager.save_data()
        self.process_manager.remove_pid_file()
        notifier.send_notification("WiFi Tracker", "WiFi Tracker stopped", Urgency.LOW)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Enhanced WiFi Usage Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wifi-tracker --daemon                    # Start daemon mode
  wifi-tracker --install-service           # Install as systemd service (auto-start)
  wifi-tracker --watch                     # Start watch mode
  wifi-tracker --status                    # Show current status
  wifi-tracker --stop                      # Stop daemon
  wifi-tracker --limit MyWiFi 1GB monthly # Set monthly limit
        """,
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument("--daemon", "-d", action="store_true", help="Run in daemon mode")
    mode_group.add_argument("--watch", "-w", action="store_true", help="Run in watch mode")
    mode_group.add_argument("--status", "-s", action="store_true", help="Show status and statistics")
    mode_group.add_argument("--status-all", action="store_true", help="Show detailed statistics for all networks")
    mode_group.add_argument("--top-apps", action="store_true", help="Show top 10 applications")
    mode_group.add_argument("--stop", action="store_true", help="Stop daemon mode")
    mode_group.add_argument("--install-service", action="store_true", help="Install systemd user service")
    mode_group.add_argument("--remove-service", action="store_true", help="Remove systemd user service")
    
    mode_group.add_argument(
        "--limit",
        nargs=3,
        metavar=("SSID", "LIMIT", "INTERVAL"),
        help="Set data limit (e.g., --limit MyWiFi 1GB monthly)",
    )
    mode_group.add_argument("--remove-limit", metavar="SSID", help="Remove data limit for SSID")
    mode_group.add_argument(
        "--cleanup",
        nargs="?",
        const=90,
        type=int,
        metavar="DAYS",
        help="Clean up data older than specified days (default: 90)",
    )

    # Configuration options
    parser.add_argument("--interface", "-i", help="Network interface to monitor")
    parser.add_argument("--interval", type=float, default=0.5, help="Update interval in seconds")

    args = parser.parse_args()

    # If no mode specified, show help
    if not any([args.daemon, args.watch, args.status, args.status_all, args.top_apps, args.stop, 
                args.limit, args.remove_limit, args.cleanup is not None, 
                args.install_service, args.remove_service]):
        parser.print_help()
        sys.exit(0)

    # Create tracker instance
    tracker = WiFiTracker(args.interface, args.interval)

    try:
        # Execute requested mode
        if args.daemon:
            tracker.daemon_mode()
        elif args.watch:
            tracker.watch_mode()
        elif args.status:
            tracker.status_mode()
        elif args.status_all:
            tracker.status_all_mode()
        elif args.top_apps:
            tracker.top_apps_mode()
        elif args.stop:
            tracker.stop_daemon()
        elif args.limit:
            ssid, limit, interval = args.limit
            tracker.set_limit(ssid, limit, interval)
        elif args.remove_limit:
            tracker.remove_limit(args.remove_limit)
        elif args.cleanup is not None:
            tracker.cleanup_data(args.cleanup)
        elif args.install_service:
            tracker.install_service()
        elif args.remove_service:
            tracker.remove_service()

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        tracker._cleanup()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
