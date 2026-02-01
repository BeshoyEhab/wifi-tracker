"""
Process Manager Module for WiFi Tracker
Handles process management, daemon operations, and instance control
"""

import os
import sys
import time
import signal
import psutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any

from wifi_tracker_modules.config import Config


class ProcessManager:
    """
    Manages WiFi tracker processes and daemon operations.

    Attributes:
        script_name (str): Name of the script to manage.
        pid_file (Path): Path to the daemon PID file.
        log_file (Path): Path to the daemon log file.
        error_log (Path): Path to the daemon error log file.
    """
    
    def __init__(self, script_name: str = "wifi-tracker"):
        """
        Initialize the ProcessManager.

        Args:
            script_name (str, optional): Name of the script. Defaults to "wifi-tracker".
        """
        self.script_name = script_name
        # Use centralized config for paths
        self.pid_file = Config.get_pid_file() 
        self.log_file = Config.get_log_file()
        self.error_log = Config.get_error_log_file()
        
        # Ensure directories exist
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def find_all_instances(self) -> List[psutil.Process]:
        """
        Find ALL instances of wifi-tracker regardless of command line options.

        Returns:
            List[psutil.Process]: List of process objects.
        """
        instances = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if process name or command line contains our script
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue
                    
                    # Convert cmdline to string for easier matching
                    cmdline_str = ' '.join(cmdline)
                    
                    # Match various ways the script might be invoked
                    if any([
                        self.script_name in cmdline_str,
                        'wifi-tracker' in cmdline_str,
                        'wifi_tracker' in cmdline_str,
                        any('wifi-tracker' in arg for arg in cmdline),
                        any('wifi_tracker' in arg for arg in cmdline)
                    ]):
                        # Skip the current process
                        if proc.pid != os.getpid():
                            instances.append(proc)
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            self._log_error(f"Error finding instances: {e}")
        
        return instances
    
    def kill_all_instances(self, exclude_current: bool = True) -> int:
        """
        Kill ALL instances of wifi-tracker with any options.

        Args:
            exclude_current (bool, optional): Whether to exclude current process. Defaults to True.

        Returns:
            int: Number of killed instances.
        """
        killed_count = 0
        current_pid = os.getpid()
        
        # Find all instances
        instances = self.find_all_instances()
        
        if not instances:
            return 0
        
        # First pass: Send SIGTERM (graceful shutdown)
        for proc in instances:
            try:
                if exclude_current and proc.pid == current_pid:
                    continue
                    
                self._log_info(f"Sending SIGTERM to PID {proc.pid}: {' '.join(proc.cmdline())}")
                proc.terminate()
                killed_count += 1
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Wait for graceful shutdown
        if killed_count > 0:
            time.sleep(2)
        
        # Second pass: Force kill remaining processes
        remaining_instances = self.find_all_instances()
        for proc in remaining_instances:
            try:
                if exclude_current and proc.pid == current_pid:
                    continue
                    
                if proc.is_running():
                    self._log_info(f"Force killing PID {proc.pid}: {' '.join(proc.cmdline())}")
                    proc.kill()
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Final verification with delay
        time.sleep(1)
        final_instances = self.find_all_instances()
        final_count = len([p for p in final_instances if not exclude_current or p.pid != current_pid])
        
        if final_count > 0:
            self._log_error(f"Warning: {final_count} instances may still be running")
        
        return killed_count
    
    def is_daemon_running(self) -> bool:
        """
        Check if daemon is currently running.

        Returns:
            bool: True if daemon is running.
        """
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process with this PID exists and is our script
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                cmdline_str = ' '.join(proc.cmdline())
                if self.script_name in cmdline_str or 'wifi-tracker' in cmdline_str:
                    return True
            
            # PID file exists but process doesn't, clean up
            self.pid_file.unlink()
            return False
            
        except (ValueError, FileNotFoundError, psutil.NoSuchProcess):
            # Clean up invalid PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False
    
    def create_pid_file(self) -> None:
        """Create PID file for daemon process."""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self._log_error(f"Failed to create PID file: {e}")
    
    def remove_pid_file(self) -> None:
        """Remove the PID file."""
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except OSError as e:
                self._log_error(f"Failed to remove PID file: {e}")

    # ==========================
    # Systemd Integration
    # ==========================

    def get_systemd_service_path(self) -> Path:
        """
        Get the path for the user systemd service file.

        Returns:
            Path: Path to service file.
        """
        return Path.home() / ".config" / "systemd" / "user" / "wifi-tracker.service"

    def is_systemd_installed(self) -> bool:
        """
        Check if the systemd service is installed.

        Returns:
            bool: True if installed.
        """
        return self.get_systemd_service_path().exists()

    def install_systemd_service(self, executable_path: str, args: str = "--daemon") -> bool:
        """
        Generate and install systemd user service.
        
        Args:
            executable_path: Full path to the wifi-tracker executable
            args: Arguments to pass to the executable
            
        Returns:
            bool: True if successful
        """
        service_path = self.get_systemd_service_path()
        service_dir = service_path.parent
        
        # Ensure directory exists
        service_dir.mkdir(parents=True, exist_ok=True)
        
        # Service file content
        content = f"""[Unit]
Description=WiFi Usage Tracker Daemon
After=network.target

[Service]
Type=simple
ExecStart={executable_path} {args}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        
        try:
            # Write service file
            with open(service_path, 'w') as f:
                f.write(content)
            
            # Reload systemd
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            
            # Enable and start
            subprocess.run(['systemctl', '--user', 'enable', 'wifi-tracker'], check=True)
            subprocess.run(['systemctl', '--user', 'start', 'wifi-tracker'], check=True)
            
            print(f"✅ Systemd service installed at: {service_path}")
            print("To view logs: journalctl --user -u wifi-tracker -f")
            return True
            
        except Exception as e:
            print(f"❌ Failed to install systemd service: {e}")
            return False

    def remove_systemd_service(self) -> bool:
        """
        Stop and remove the systemd service.

        Returns:
            bool: True if successful.
        """
        service_path = self.get_systemd_service_path()
        
        try:
            # Stop and disable
            subprocess.run(['systemctl', '--user', 'stop', 'wifi-tracker'], stderr=subprocess.DEVNULL)
            subprocess.run(['systemctl', '--user', 'disable', 'wifi-tracker'], stderr=subprocess.DEVNULL)
            
            # Remove file
            if service_path.exists():
                service_path.unlink()
                
            # Reload
            subprocess.run(['systemctl', '--user', 'daemon-reload'], stderr=subprocess.DEVNULL)
            
            print("✅ Systemd service removed")
            return True
            
        except Exception as e:
            print(f"❌ Failed to remove systemd service: {e}")
            return False
    
    def daemonize(self) -> None:
        """Daemonize the current process."""
        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Parent exits
        except OSError as e:
            self._log_error(f"First fork failed: {e}")
            sys.exit(1)
        
        # Decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)
        
        try:
            # Second fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Second parent exits
        except OSError as e:
            self._log_error(f"Second fork failed: {e}")
            sys.exit(1)
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Redirect to /dev/null
        with open('/dev/null', 'r') as dev_null_r:
            os.dup2(dev_null_r.fileno(), sys.stdin.fileno())
        
        with open('/dev/null', 'w') as dev_null_w:
            os.dup2(dev_null_w.fileno(), sys.stdout.fileno())
            os.dup2(dev_null_w.fileno(), sys.stderr.fileno())
    
    def setup_signal_handlers(self, cleanup_callback=None) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Args:
            cleanup_callback (callable, optional): function to call on exit.
        """
        def signal_handler(signum, frame):
            self._log_info(f"Received signal {signum}, shutting down gracefully...")
            if cleanup_callback:
                cleanup_callback()
            self.remove_pid_file()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGUSR1, signal_handler)
    
    def _log_info(self, message: str) -> None:
        """Log info message to log file."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] INFO: {message}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_message)
        except Exception:
            pass  # Fail silently in daemon mode
    
    def _log_error(self, message: str) -> None:
        """Log error message to error log."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] ERROR: {message}\n"
        
        try:
            with open(self.error_log, 'a') as f:
                f.write(log_message)
        except Exception:
            pass  # Fail silently in daemon mode
    
    def get_process_info(self) -> Dict[str, Any]:
        """
        Get information about current process and instances.

        Returns:
            Dict[str, Any]: Process info dictionary.
        """
        instances = self.find_all_instances()
        daemon_running = self.is_daemon_running()
        
        return {
            'current_pid': os.getpid(),
            'daemon_running': daemon_running,
            'total_instances': len(instances),
            'instance_pids': [p.pid for p in instances],
            'pid_file_exists': self.pid_file.exists(),
            'log_file': str(self.log_file),
            'error_log': str(self.error_log)
        }
        
    def get_top_network_apps(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top applications using the network.
        
        Args:
            limit: Maximum number of apps to return (default: 10)
            
        Returns:
            List of dicts with app info including PID, name, and network usage
        """
        try:
            # Get per-process network I/O counters
            net_io = psutil.net_io_counters(pernic=False)
            if not net_io:
                return []
                
            # Get all processes with network connections
            processes = {}
            
            # First, get processes with active connections
            for conn in psutil.net_connections(kind='inet'):
                try:
                    if not conn.pid:
                        continue
                        
                    proc = psutil.Process(conn.pid)
                    with proc.oneshot():
                        name = proc.name()
                        username = proc.username()
                        
                    if conn.pid not in processes:
                        processes[conn.pid] = {
                            'pid': conn.pid,
                            'name': name,
                            'user': username,
                            'bytes_sent': 0,
                            'bytes_recv': 0,
                            'connections': 0,
                            'last_activity': 0
                        }
                    
                    # Update connection count
                    processes[conn.pid]['connections'] += 1
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, psutil.ZombieProcess):
                    continue
            
            # Now get I/O counters for processes with network activity
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    pid = proc.info['pid']
                    if pid not in processes:
                        continue
                        
                    # Get process I/O counters
                    io = proc.io_counters()
                    if io:
                        processes[pid].update({
                            'bytes_sent': io.write_bytes,
                            'bytes_recv': io.read_bytes,
                            'total_bytes': io.write_bytes + io.read_bytes
                        })
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, psutil.ZombieProcess):
                    if proc.info['pid'] in processes:
                        del processes[proc.info['pid']]
            
            # Convert to list and sort by total bytes
            sorted_apps = sorted(
                processes.values(),
                key=lambda x: x.get('total_bytes', 0),
                reverse=True
            )
            
            # Filter out processes with no network activity
            active_apps = [
                app for app in sorted_apps 
                if app.get('total_bytes', 0) > 0 or app.get('connections', 0) > 0
            ]
            
            return active_apps[:min(limit, len(active_apps))]
            
        except Exception as e:
            self._log_error(f"Error getting top network apps: {e}")
            return []
