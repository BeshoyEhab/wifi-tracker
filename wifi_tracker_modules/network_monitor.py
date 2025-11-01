"""
Network Monitor Module for WiFi Tracker
Handles network interface monitoring and data collection
"""

import subprocess
import re
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, Any


class NetworkMonitor:
    """Monitors network interfaces and collects usage statistics"""
    def __init__(self, interface: str = None, interval: float = 0.5):
        self.interface = interface or self.detect_wireless_interface()
        self.interval = interval
        self.last_measurement = None
        self.start_time = time.time()
        
    def detect_wireless_interface(self) -> str:
        """Auto-detect the active wireless interface"""
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'IEEE 802.11' in line and 'no wireless extensions' not in line:
                    interface = line.split()[0]
                    if interface and not interface.startswith('lo'):
                        return interface
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Fallback: try common wireless interface names
        for interface in ['wlan0', 'wlp1s0', 'wlp2s0', 'wlo1']:
            if self._interface_exists(interface):
                return interface
        
        return 'wlan0'  # Default fallback
    
    def _interface_exists(self, interface: str) -> bool:
        """Check if network interface exists"""
        try:
            with open(f'/sys/class/net/{interface}/operstate', 'r') as f:
                return True
        except FileNotFoundError:
            return False
    
    def get_interface_stats(self) -> Optional[Dict[str, int]]:
        """Get current interface statistics"""
        try:
            with open(f'/proc/net/dev', 'r') as f:
                for line in f:
                    if self.interface in line:
                        parts = line.split()
                        return {
                            'rx_bytes': int(parts[1]),
                            'tx_bytes': int(parts[9]),
                            'rx_packets': int(parts[2]),
                            'tx_packets': int(parts[10])
                        }
        except (FileNotFoundError, ValueError, IndexError):
            pass
        return None
    
    def get_current_ssid(self) -> Optional[str]:
        """Get currently connected WiFi SSID"""
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Alternative method using iwconfig
        try:
            result = subprocess.run(['iwconfig', self.interface], capture_output=True, text=True, timeout=3)
            match = re.search(r'ESSID:"([^"]*)"', result.stdout)
            if match:
                ssid = match.group(1)
                return ssid if ssid != "off/any" else None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Alternative method using nmcli
        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('yes:'):
                        return line.split(':')[1]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return None

    def get_signal_quality(self) -> Dict[str, Any]:
        """Get WiFi signal quality information"""
        quality_info = {
            'signal_level': 0,
            'signal_quality': 0,
            'link_quality': 0,
            'noise_level': 0
        }
        
        try:
            result = subprocess.run(['iwconfig', self.interface], capture_output=True, text=True, timeout=3)
            output = result.stdout
            
            # Parse signal level
            signal_match = re.search(r'Signal level=(-?\d+)', output)
            if signal_match:
                quality_info['signal_level'] = int(signal_match.group(1))
            
            # Parse link quality
            quality_match = re.search(r'Link Quality=(\d+)/(\d+)', output)
            if quality_match:
                quality_info['link_quality'] = int(quality_match.group(1))
                quality_info['signal_quality'] = int(quality_match.group(2))
            
            # Parse noise level
            noise_match = re.search(r'Noise level=(-?\d+)', output)
            if noise_match:
                quality_info['noise_level'] = int(noise_match.group(1))
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return quality_info
    
    def calculate_rates(self, current_stats: Dict[str, int]) -> Tuple[float, float]:
        """Calculate download and upload rates"""
        if not self.last_measurement:
            self.last_measurement = {
                'stats': current_stats,
                'timestamp': time.time()
            }
            return 0.0, 0.0
        
        time_diff = time.time() - self.last_measurement['timestamp']
        if time_diff <= 0:
            return 0.0, 0.0
        
        rx_diff = current_stats['rx_bytes'] - self.last_measurement['stats']['rx_bytes']
        tx_diff = current_stats['tx_bytes'] - self.last_measurement['stats']['tx_bytes']
        
        rx_rate = max(0, rx_diff / time_diff)
        tx_rate = max(0, tx_diff / time_diff)
        
        self.last_measurement = {
            'stats': current_stats,
            'timestamp': time.time()
        }
        
        return rx_rate, tx_rate
    
    def get_measurement(self) -> Optional[Dict[str, Any]]:
        """Get complete network measurement"""
        current_ssid = self.get_current_ssid()
        current_stats = self.get_interface_stats()
        
        if not current_stats:
            return None
        
        rx_rate, tx_rate = self.calculate_rates(current_stats)
        quality_info = self.get_signal_quality()
        
        return {
            'ssid': current_ssid,
            'timestamp': datetime.now(),
            'rx_bytes': current_stats['rx_bytes'],
            'tx_bytes': current_stats['tx_bytes'],
            'rx_rate': rx_rate,
            'tx_rate': tx_rate,
            'signal_quality': quality_info,
            'interface': self.interface
        }
