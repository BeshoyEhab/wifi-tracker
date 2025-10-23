"""
Display Manager Module for WiFi Tracker
Handles all display formatting and output operations
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class DisplayManager:
    """Manages display formatting and output for WiFi tracker"""
    
    def __init__(self):
        self.last_display_time = 0
        self.display_cache = {}
    
    def clear_screen(self) -> None:
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string"""
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_value)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def format_rate(self, rate: float) -> str:
        """Format transfer rate into human-readable string"""
        return f"{self.format_bytes(int(rate))}/s"
    
    def format_duration(self, duration: timedelta) -> str:
        """Format duration into human-readable string"""
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a text-based progress bar"""
        filled = int(round(width * percentage / 100))
        return f"[{'█' * filled}{'░' * (width - filled)}]"
        
    def format_bytes(self, bytes_num: int) -> str:
        """Format bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_num < 1024.0:
                if unit in ['B']:
                    return f"{int(bytes_num)} {unit}"
                return f"{bytes_num:.1f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.1f} PB"
        
    def print_top_network_apps(self, apps: list) -> None:
        """Print top network apps in a formatted table"""
        if not apps:
            print("\nNo network activity detected.")
            return
            
        print("\n🌐 Top Network Applications")
        print("=" * 50)
        print(f"{'PID':<8} {'User':<12} {'App Name':<20} {'Sent':<12} {'Received':<12} {'Total':<12} Connections")
        print("-" * 80)
        
        for app in apps:
            pid = app.get('pid', 'N/A')
            user = app.get('user', 'unknown')[:10]  # Limit username length
            name = app.get('name', 'unknown')[:18]  # Limit app name length
            sent = self.format_bytes(app.get('bytes_sent', 0))
            recv = self.format_bytes(app.get('bytes_recv', 0))
            total = self.format_bytes(app.get('total_bytes', 0))
            conns = app.get('connections', 0)
            
            print(f"{pid:<8} {user:<12} {name:<20} {sent:<12} {recv:<12} {total:<12} {conns}")
        
        print("=" * 80)
    
    def build_header(self, interface: str, pid: int) -> List[str]:
        """Build display header"""
        lines = []
        lines.append("=" * 80)
        lines.append("📊 Enhanced WiFi Usage Statistics")
        lines.append("=" * 80)
        lines.append(f"🔧 Interface: {interface} | PID: {pid}")
        lines.append("=" * 80)
        lines.append("")
        return lines
    
    def build_status_info(self, current_time: datetime, uptime: timedelta, 
                         update_count: int, current_ssid: str, last_save_time: float) -> List[str]:
        """Build status information section"""
        lines = []
        
        current_time_str = current_time.strftime("%H:%M:%S.%f")[:-3]
        lines.append(f"⏰ Time: {current_time_str} | Uptime: {self.format_duration(uptime)} | Updates: {update_count}")
        
        status_emoji = "🟢" if current_ssid else "🔴"
        lines.append(f"🌐 Connected: {current_ssid or 'None'} {status_emoji}")
        lines.append(f"💾 Last save: {time.ctime(last_save_time) if last_save_time else 'Never'}")
        lines.append("")
        
        return lines
    
    def build_network_details(self, ssid: str, ssid_data: Dict[str, Any], 
                            rx_rate: float, tx_rate: float, session_rx: int = 0, session_tx: int = 0) -> List[str]:
        """Build network details section"""
        lines = []
        
        # Calculate totals and daily usage
        total_rx = ssid_data.get('total_rx', 0)
        total_tx = ssid_data.get('total_tx', 0)
        total_usage = total_rx + total_tx
        
        today = datetime.now().strftime('%Y-%m-%d')
        daily_data = ssid_data.get('daily', {}).get(today, {})
        daily_rx = daily_data.get('rx', 0)
        daily_tx = daily_data.get('tx', 0)
        daily_total = daily_rx + daily_tx
        
        # Usage statistics
        lines.append(f"📊 Total: {self.format_bytes(total_usage)} (↓{self.format_bytes(total_rx)} ↑{self.format_bytes(total_tx)})")
        lines.append(f"📅 Today: {self.format_bytes(daily_total)} (↓{self.format_bytes(daily_rx)} ↑{self.format_bytes(daily_tx)})")
        lines.append(f"⚡ Rates: ↓{self.format_rate(rx_rate)} ↑{self.format_rate(tx_rate)}")
        
        # Session usage
        session_total = session_rx + session_tx
        if session_total > 0:
            lines.append(f"⏱️ Session: {self.format_bytes(session_total)} (↓{self.format_bytes(session_rx)} ↑{self.format_bytes(session_tx)})")
        else:
            lines.append("⏱️ Session: Just connected")
        
        # Connection info
        connection_count = ssid_data.get('connection_count', 0)
        first_seen = ssid_data.get('first_seen', 'Unknown')
        if first_seen != 'Unknown':
            try:
                first_seen_dt = datetime.fromisoformat(first_seen)
                first_seen = first_seen_dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        
        lines.append(f"🔗 Connections: {connection_count} | First seen: {first_seen}")
        
        return lines
    
    def build_limits_section(self, ssid: str, ssid_data: Dict[str, Any], 
                           limits_data: Dict[str, Any]) -> List[str]:
        """Build data limits section"""
        lines = []
        
        if ssid not in limits_data:
            return lines
        
        limit_info = limits_data[ssid]
        limit_bytes = limit_info.get('limit', 0)
        interval = limit_info.get('interval', 'monthly')
        
        if limit_bytes <= 0:
            return lines
        
        # Calculate period usage
        period_usage = self._calculate_period_usage(ssid_data, interval)
        usage_percent = min(100, (period_usage / limit_bytes) * 100) if limit_bytes > 0 else 0
        
        lines.append("")
        lines.append(f"📊 {interval.capitalize()} Limit ({usage_percent:.1f}%): {self.format_bytes(period_usage)}/{self.format_bytes(limit_bytes)}")
        
        # Progress bar
        progress_bar = self.create_progress_bar(usage_percent)
        lines.append(progress_bar)
        
        # Warning if approaching limit
        if usage_percent > 80:
            lines.append(f"⚠️ WARNING: {100 - usage_percent:.1f}% remaining")
        
        return lines
    
    def _calculate_period_usage(self, ssid_data: Dict[str, Any], interval: str) -> int:
        """Calculate usage for the specified interval"""
        period_usage = 0
        
        if interval == 'daily':
            today = datetime.now().strftime('%Y-%m-%d')
            daily_data = ssid_data.get('daily', {}).get(today, {})
            period_usage = daily_data.get('rx', 0) + daily_data.get('tx', 0)
        
        elif interval == 'weekly':
            # Calculate usage for current week
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
            
            for i in range(7):
                date = (week_start + timedelta(days=i)).strftime('%Y-%m-%d')
                daily_data = ssid_data.get('daily', {}).get(date, {})
                period_usage += daily_data.get('rx', 0) + daily_data.get('tx', 0)
        
        elif interval == 'monthly':
            # Calculate usage for current month
            today = datetime.now()
            month_start = today.replace(day=1)
            
            current_date = month_start
            while current_date.month == today.month:
                date_str = current_date.strftime('%Y-%m-%d')
                daily_data = ssid_data.get('daily', {}).get(date_str, {})
                period_usage += daily_data.get('rx', 0) + daily_data.get('tx', 0)
                current_date += timedelta(days=1)
                if current_date > today:
                    break
        
        return period_usage
    
    def build_watch_display(self, interface: str, pid: int, current_time: datetime,
                          uptime: timedelta, update_count: int, current_ssid: str,
                          last_save_time: float, ssid_data: Dict[str, Any],
                          rx_rate: float, tx_rate: float, limits_data: Dict[str, Any],
                          interval: float, session_rx: int = 0, session_tx: int = 0) -> str:
        """Build complete watch mode display"""
        display_lines = []
        
        # Header
        display_lines.extend(self.build_header(interface, pid))
        
        # Status info
        display_lines.extend(self.build_status_info(current_time, uptime, update_count, current_ssid, last_save_time))
        
        # Network details (if connected)
        if current_ssid and ssid_data:
            display_lines.extend(self.build_network_details(current_ssid, ssid_data, rx_rate, tx_rate, session_rx, session_tx))
            
            # Data limits (if set)
            limits_section = self.build_limits_section(current_ssid, ssid_data, limits_data)
            display_lines.extend(limits_section)
        
        # Final status line
        display_lines.append("")
        display_lines.append(f"🔄 Refreshing every {interval}s | Press Ctrl+C to exit")
        
        return "\n".join(display_lines)
    
    def print_detailed_stats(self, usage_data: Dict[str, Any], limits_data: Dict[str, Any],
                           current_ssid: str = None, current_measurement: Dict[str, Any] = None) -> None:
        """Print detailed statistics"""
        print("📊 Enhanced WiFi Usage Statistics")
        print("=" * 50)
        
        if not usage_data:
            print("No usage data available.")
            return
        
        # Sort SSIDs by total usage
        sorted_ssids = sorted(usage_data.items(), key=lambda x: x[1].get('total_rx', 0) + x[1].get('total_tx', 0), reverse=True)
        
        for ssid, data in sorted_ssids:
            total_rx = data.get('total_rx', 0)
            total_tx = data.get('total_tx', 0)
            total = total_rx + total_tx
            
            # Current connection indicator
            current_indicator = " 🟢 CURRENT" if ssid == current_ssid else ""
            print(f"\n🌐 SSID: {ssid}{current_indicator}")
            print(f"📊 Total Usage: {self.format_bytes(total)} (↓{self.format_bytes(total_rx)} ↑{self.format_bytes(total_tx)})")
            
            # Today's usage
            today = datetime.now().strftime('%Y-%m-%d')
            daily_data = data.get('daily', {}).get(today, {})
            daily_rx = daily_data.get('rx', 0)
            daily_tx = daily_data.get('tx', 0)
            daily_total = daily_rx + daily_tx
            print(f"📅 Today's Usage: {self.format_bytes(daily_total)} (↓{self.format_bytes(daily_rx)} ↑{self.format_bytes(daily_tx)})")
            
            # Live rates if current connection
            if ssid == current_ssid and current_measurement:
                rx_rate = current_measurement.get('rx_rate', 0)
                tx_rate = current_measurement.get('tx_rate', 0)
                print(f"⚡ Live Rates: ↓{self.format_rate(rx_rate)} ↑{self.format_rate(tx_rate)}")
            
            # Connection info
            connection_count = data.get('connection_count', 0)
            first_seen = data.get('first_seen', 'Unknown')
            last_seen = data.get('last_seen', 'Unknown')
            
            print(f"🔗 Connections: {connection_count}")
            print(f"📅 First seen: {first_seen}")
            print(f"📅 Last seen: {last_seen}")
            
            # Peak rates (with safe defaults and type checking)
            peak_rx = 0
            peak_tx = 0
            if isinstance(data, dict):
                peak_rx = data.get('peak_rx_rate', 0) or 0
                peak_tx = data.get('peak_tx_rate', 0) or 0
                
                # Ensure values are numeric
                try:
                    peak_rx = float(peak_rx) if peak_rx is not None else 0
                    peak_tx = float(peak_tx) if peak_tx is not None else 0
                except (TypeError, ValueError):
                    peak_rx = 0
                    peak_tx = 0
            
            # Only show if we have valid peak rates
            if peak_rx > 0 or peak_tx > 0:
                print(f"🚀 Peak rates: ↓{self.format_rate(peak_rx)} ↑{self.format_rate(peak_tx)}")
            
            # Data limits
            if ssid in limits_data:
                limit_info = limits_data[ssid]
                limit_bytes = limit_info.get('limit', 0)
                interval = limit_info.get('interval', 'monthly')
                
                if limit_bytes > 0:
                    period_usage = self._calculate_period_usage(data, interval)
                    usage_percent = min(100, (period_usage / limit_bytes) * 100)
                    
                    print(f"📊 {interval.capitalize()} Limit: {self.format_bytes(period_usage)}/{self.format_bytes(limit_bytes)} ({usage_percent:.1f}%)")
                    
                    progress_bar = self.create_progress_bar(usage_percent)
                    print(f"    {progress_bar}")
                    
                    if usage_percent > 80:
                        print(f"    ⚠️ WARNING: {100 - usage_percent:.1f}% remaining")
            
            print("-" * 40)
    
    def print_all_stats(self, usage_data: Dict[str, Any], limits_data: Dict[str, Any],
                      current_ssid: str = None, current_measurement: Dict[str, Any] = None) -> None:
        """Print detailed statistics for all SSIDs from the last 90 days"""
        print("📊 WiFi Usage Statistics - Last 90 Days")
        print("=" * 50)
        print("🌐 Detailed statistics for all tracked networks\n")
        
        if not usage_data:
            print("No usage data available.")
            return
        
        # Calculate date 90 days ago
        ninety_days_ago = datetime.now() - timedelta(days=90)
        
        # Sort SSIDs by total usage
        sorted_ssids = sorted(usage_data.items(), 
                             key=lambda x: x[1].get('total_rx', 0) + x[1].get('total_tx', 0), 
                             reverse=True)
        
        for ssid, data in sorted_ssids:
            # Current connection indicator
            current_indicator = " 🟢 CURRENT" if ssid == current_ssid else ""
            print(f"\n🌐 SSID: {ssid}{current_indicator}")
            print("-" * (len(ssid) + 8 + (9 if current_indicator else 0)))
            
            # Total usage
            total_rx = data.get('total_rx', 0)
            total_tx = data.get('total_tx', 0)
            total = total_rx + total_tx
            print(f"📊 Total Usage: {self.format_bytes(total)} (↓{self.format_bytes(total_rx)} ↑{self.format_bytes(total_tx)})")
            
            # Live rates if current connection
            if ssid == current_ssid and current_measurement:
                rx_rate = current_measurement.get('rx_rate', 0)
                tx_rate = current_measurement.get('tx_rate', 0)
                print(f"⚡ Live Rates: ↓{self.format_rate(rx_rate)} ↑{self.format_rate(tx_rate)}")
            
            # Connection info
            connection_count = data.get('connection_count', 0)
            first_seen = data.get('first_seen', 'Unknown')
            last_seen = data.get('last_seen', 'Unknown')
            
            print(f"\n🔗 Connection Info:")
            print(f"   • Connections: {connection_count}")
            print(f"   • First seen: {first_seen}")
            print(f"   • Last seen: {last_seen}")
            
            # Daily usage for last 90 days
            daily_data = data.get('daily', {})
            if daily_data:
                print("\n📅 Daily Usage (Last 90 days):")
                
                # Sort dates in descending order (newest first)
                sorted_dates = sorted(daily_data.items(), key=lambda x: x[0], reverse=True)
                
                # Filter for last 90 days
                recent_days = []
                for date_str, day_data in sorted_dates:
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        if date >= ninety_days_ago:
                            recent_days.append((date_str, day_data))
                    except (ValueError, TypeError):
                        continue
                
                if not recent_days:
                    print("   No recent daily data available.")
                else:
                    for date_str, day_data in recent_days:
                        rx = day_data.get('rx', 0)
                        tx = day_data.get('tx', 0)
                        total = rx + tx
                        
                        if total > 0:  # Only show days with usage
                            print(f"   • {date_str}: {self.format_bytes(total)} "
                                f"(↓{self.format_bytes(rx)} ↑{self.format_bytes(tx)})")
                            
                            # Show peak rates if available (with safe access and type checking)
                            peak_rx = 0
                            peak_tx = 0
                            if isinstance(day_data, dict):
                                peak_rx = day_data.get('peak_rx_rate', 0) or 0
                                peak_tx = day_data.get('peak_tx_rate', 0) or 0
                                
                                # Ensure values are numeric
                                try:
                                    peak_rx = float(peak_rx) if peak_rx is not None else 0
                                    peak_tx = float(peak_tx) if peak_tx is not None else 0
                                except (TypeError, ValueError):
                                    peak_rx = 0
                                    peak_tx = 0
                            
                            # Only show if we have valid peak rates
                            if peak_rx > 0 or peak_tx > 0:
                                print(f"     ⚡ Peak rates: ↓{self.format_rate(peak_rx)} ↑{self.format_rate(peak_tx)}")
            
            # Data limits
            if ssid in limits_data:
                limit_info = limits_data[ssid]
                limit_bytes = limit_info.get('limit', 0)
                interval = limit_info.get('interval', 'monthly')
                
                if limit_bytes > 0:
                    period_usage = self._calculate_period_usage(data, interval)
                    usage_percent = min(100, (period_usage / limit_bytes) * 100)
                    
                    print(f"\n📊 {interval.capitalize()} Data Limit:")
                    print(f"   • Usage: {self.format_bytes(period_usage)} / {self.format_bytes(limit_bytes)} ({usage_percent:.1f}%)")
                    print(f"   • Remaining: {self.format_bytes(max(0, limit_bytes - period_usage))}")
                    
                    progress_bar = self.create_progress_bar(usage_percent, 30)
                    print(f"   • {progress_bar}")
                    
                    if usage_percent > 80:
                        print(f"   ⚠️  WARNING: {100 - usage_percent:.1f}% remaining")
            
            print("\n" + "=" * 50)
