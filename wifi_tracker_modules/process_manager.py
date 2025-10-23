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
from typing import List, Optional


class ProcessManager:
    """Manages WiFi tracker processes and daemon operations"""
    
    def __init__(self, script_name: str = "wifi-tracker"):
        self.script_name = script_name
        self.pid_file = Path.home() / ".cache" / f"{script_name}.pid"
        self.log_file = Path.home() / ".cache" / f"{script_name}_daemon.log"
        self.error_log = Path.home() / ".cache" / f"{script_name}_error.log"
        
        # Ensure cache directory exists
        self.pid_file.parent.mkdir(exist_ok=True)
    
    def find_all_instances(self) -> List[psutil.Process]:
        """Find ALL instances of wifi-tracker regardless of command line options"""
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
        """Kill ALL instances of wifi-tracker with any options"""
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
        """Check if daemon is currently running"""
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
        """Create PID file for daemon process"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self._log_error(f"Failed to create PID file: {e}")
    
    def remove_pid_file(self) -> None:
        """Remove PID file"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            self._log_error(f"Failed to remove PID file: {e}")
    
    def daemonize(self) -> None:
        """Daemonize the current process"""
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
        """Setup signal handlers for graceful shutdown"""
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
        """Log info message"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] INFO: {message}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_message)
        except Exception:
            pass  # Fail silently in daemon mode
    
    def _log_error(self, message: str) -> None:
        """Log error message"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] ERROR: {message}\n"
        
        try:
            with open(self.error_log, 'a') as f:
                f.write(log_message)
        except Exception:
            pass  # Fail silently in daemon mode
    
    def get_process_info(self) -> dict:
        """Get information about current process and instances"""
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
        
    def get_top_network_apps(self, limit: int = 10) -> list:
        """Get top applications using the network
        
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
                    
                    # Update connection count and last activity
                    processes[conn.pid]['connections'] += 1
                    if hasattr(conn, 'last_activity') and conn.last_activity:
                        processes[conn.pid]['last_activity'] = max(
                            processes[conn.pid].get('last_activity', 0),
                            conn.last_activity or 0
                        )
                            
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
