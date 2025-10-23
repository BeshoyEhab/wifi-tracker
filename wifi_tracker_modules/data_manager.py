#!/usr/bin/env python3
"""
Data Manager Module for WiFi Tracker
Handles data persistence, validation, and management
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class DataManager:
    """Manages WiFi usage data persistence and validation"""
    
    def __init__(self, data_file: str = None):
        self.data_file = Path(data_file) if data_file else Path.home() / ".cache" / "wifi_usage.json"
        self.limits_file = Path.home() / ".cache" / "wifi_limits.json"
        
        # Ensure cache directory exists
        self.data_file.parent.mkdir(exist_ok=True)
        
        # Initialize data structures
        self.usage_data = {}
        self.limits_data = {}
        self._metadata = {}  # Track cleanup and other metadata
        
        # Load existing data
        self.load_data()
        self.load_limits()
    
    def load_data(self) -> Dict[str, Any]:
        """Load usage data from file with validation and migration"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                # Extract metadata if present
                if '_metadata' in data:
                    self._metadata = data['_metadata']
                    del data['_metadata']  # Remove from main data
                else:
                    self._metadata = {}
                
                # Validate and migrate data structure
                self.usage_data = self._validate_and_migrate_data(data)
            else:
                self.usage_data = {}
                self._metadata = {}
                
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Warning: Could not load data file: {e}")
            self.usage_data = {}
            self._metadata = {}
        
        return self.usage_data
    
    def load_limits(self) -> Dict[str, Any]:
        """Load limits data from file"""
        try:
            if self.limits_file.exists():
                with open(self.limits_file, 'r') as f:
                    self.limits_data = json.load(f)
            else:
                self.limits_data = {}
                
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Warning: Could not load limits file: {e}")
            self.limits_data = {}
        
        return self.limits_data
    
    def save_data(self) -> bool:
        """Save usage data to file"""
        try:
            # Create backup of existing file
            if self.data_file.exists():
                backup_file = self.data_file.with_suffix('.json.bak')
                self.data_file.rename(backup_file)
            
            # Prepare data with metadata
            data_to_save = self.usage_data.copy()
            data_to_save['_metadata'] = self._metadata
            
            # Write new data
            with open(self.data_file, 'w') as f:
                json.dump(data_to_save, f, indent=2, default=str)
            
            return True
            
        except (PermissionError, OSError) as e:
            print(f"Error saving data: {e}")
            return False
    
    def save_limits(self) -> bool:
        """Save limits data to file"""
        try:
            with open(self.limits_file, 'w') as f:
                json.dump(self.limits_data, f, indent=2)
            return True
            
        except (PermissionError, OSError) as e:
            print(f"Error saving limits: {e}")
            return False
    
    def _validate_and_migrate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and migrate data structure for backward compatibility"""
        validated_data = {}
        
        for ssid, ssid_data in data.items():
            if not isinstance(ssid_data, dict):
                continue
            
            # Initialize validated SSID data
            validated_ssid = {
                'total_rx': ssid_data.get('total_rx', 0),
                'total_tx': ssid_data.get('total_tx', 0),
                'first_seen': ssid_data.get('first_seen', datetime.now().isoformat()),
                'last_seen': ssid_data.get('last_seen', datetime.now().isoformat()),
                'connection_count': ssid_data.get('connection_count', 1),
                'daily': ssid_data.get('daily', {}),
                'sessions': ssid_data.get('sessions', []),
                'peak_rx_rate': ssid_data.get('peak_rx_rate', 0),
                'peak_tx_rate': ssid_data.get('peak_tx_rate', 0),
                'last_interface_rx': ssid_data.get('last_interface_rx', 0),
                'last_interface_tx': ssid_data.get('last_interface_tx', 0),
                'session_start_rx': ssid_data.get('session_start_rx', 0),
                'session_start_tx': ssid_data.get('session_start_tx', 0),
                'accuracy_stats': ssid_data.get('accuracy_stats', {
                    'total_measurements': 0,
                    'successful_measurements': 0,
                    'last_accuracy_check': datetime.now().isoformat(),
                    'accuracy_score': 1.0
                })
            }
            
            # Validate daily data structure
            validated_daily = {}
            for date, daily_data in validated_ssid['daily'].items():
                if isinstance(daily_data, dict):
                    validated_daily[date] = {
                        'rx': daily_data.get('rx', 0),
                        'tx': daily_data.get('tx', 0),
                        'sessions': daily_data.get('sessions', 0),
                        'first_connection': daily_data.get('first_connection'),
                        'last_connection': daily_data.get('last_connection')
                    }
            
            validated_ssid['daily'] = validated_daily
            validated_data[ssid] = validated_ssid
        
        return validated_data
    
    def update_usage(self, ssid: str, rx_bytes: int, tx_bytes: int, 
                    timestamp: datetime = None, rx_rate: float = 0, tx_rate: float = 0) -> None:
        """Update usage data for a specific SSID using delta-based tracking"""
        if timestamp is None:
            timestamp = datetime.now()
        
        today = timestamp.strftime('%Y-%m-%d')
        
        # Auto-cleanup old data (90 days) once per day
        self._auto_cleanup_if_needed()
        
        # Initialize SSID data if not exists
        if ssid not in self.usage_data:
            self.usage_data[ssid] = {
                'total_rx': 0,
                'total_tx': 0,
                'first_seen': timestamp.isoformat(),
                'last_seen': timestamp.isoformat(),
                'connection_count': 1,
                'daily': {},
                'sessions': [],
                'peak_rx_rate': 0,
                'peak_tx_rate': 0,
                'last_interface_rx': rx_bytes,  # Track last interface reading
                'last_interface_tx': tx_bytes,  # Track last interface reading
                'session_start_rx': rx_bytes,   # Track session start
                'session_start_tx': tx_bytes,   # Track session start
                'accuracy_stats': {
                    'total_measurements': 0,
                    'successful_measurements': 0,
                    'last_accuracy_check': timestamp.isoformat(),
                    'accuracy_score': 1.0
                }
            }
        else:
            # Ensure peak rate fields exist (for backward compatibility)
            if 'peak_rx_rate' not in self.usage_data[ssid]:
                self.usage_data[ssid]['peak_rx_rate'] = 0
            if 'peak_tx_rate' not in self.usage_data[ssid]:
                self.usage_data[ssid]['peak_tx_rate'] = 0
        
        ssid_data = self.usage_data[ssid]
        
        # Calculate deltas from last measurement
        last_rx = ssid_data.get('last_interface_rx', rx_bytes)
        last_tx = ssid_data.get('last_interface_tx', tx_bytes)
        
        # Handle interface counter resets (when current < last)
        if rx_bytes < last_rx or tx_bytes < last_tx:
            # Interface counters reset, start new session tracking
            ssid_data['session_start_rx'] = rx_bytes
            ssid_data['session_start_tx'] = tx_bytes
            rx_delta = 0
            tx_delta = 0
        else:
            # Normal case: calculate deltas
            rx_delta = rx_bytes - last_rx
            tx_delta = tx_bytes - last_tx
        
        # Update totals with deltas
        ssid_data['total_rx'] += rx_delta
        ssid_data['total_tx'] += tx_delta
        ssid_data['last_seen'] = timestamp.isoformat()
        
        # Update interface tracking
        ssid_data['last_interface_rx'] = rx_bytes
        ssid_data['last_interface_tx'] = tx_bytes
        
        # Initialize daily data if not exists for today
        if today not in ssid_data['daily']:
            ssid_data['daily'][today] = {
                'rx': 0,
                'tx': 0,
                'sessions': 0,
                'first_connection': timestamp.isoformat(),
                'last_connection': timestamp.isoformat(),
                'date': today,
                'peak_rx_rate': 0,
                'peak_tx_rate': 0,
                'connection_duration': 0,
                'data_points': 0
            }
        
        # Get daily data and update it
        daily_data = ssid_data['daily'][today]
        daily_data['rx'] = daily_data.get('rx', 0) + rx_delta
        daily_data['tx'] = daily_data.get('tx', 0) + tx_delta
        daily_data['last_connection'] = timestamp.isoformat()
        
        # Safely update peak rates
        current_peak_rx = daily_data.get('peak_rx_rate', 0) or 0
        current_peak_tx = daily_data.get('peak_tx_rate', 0) or 0
        daily_data['peak_rx_rate'] = max(current_peak_rx, rx_rate)
        daily_data['peak_tx_rate'] = max(current_peak_tx, tx_rate)
        
        # Update data points counter
        daily_data['data_points'] = daily_data.get('data_points', 0) + 1
        
        # Update accuracy stats
        accuracy_stats = ssid_data['accuracy_stats']
        accuracy_stats['total_measurements'] += 1
        accuracy_stats['successful_measurements'] += 1
        accuracy_stats['last_accuracy_check'] = timestamp.isoformat()
        
        # Calculate accuracy score (simple heuristic)
        if accuracy_stats['total_measurements'] > 0:
            accuracy_stats['accuracy_score'] = min(1.0, 
                accuracy_stats['successful_measurements'] / accuracy_stats['total_measurements'])
    
    def get_session_usage(self, ssid: str, current_rx: int, current_tx: int) -> tuple:
        """Get current session usage for an SSID"""
        if ssid not in self.usage_data:
            return 0, 0
        
        ssid_data = self.usage_data[ssid]
        session_start_rx = ssid_data.get('session_start_rx', current_rx)
        session_start_tx = ssid_data.get('session_start_tx', current_tx)
        
        # Calculate session usage (current interface stats - session start)
        session_rx = max(0, current_rx - session_start_rx)
        session_tx = max(0, current_tx - session_start_tx)
        
        return session_rx, session_tx
    
    def get_usage_summary(self, ssid: str = None) -> Dict[str, Any]:
        """Get usage summary for specific SSID or all SSIDs"""
        if ssid:
            return self.usage_data.get(ssid, {})
        
        # Return summary for all SSIDs
        summary = {}
        total_rx = total_tx = 0
        
        for ssid_name, ssid_data in self.usage_data.items():
            summary[ssid_name] = {
                'total_usage': ssid_data['total_rx'] + ssid_data['total_tx'],
                'total_rx': ssid_data['total_rx'],
                'total_tx': ssid_data['total_tx'],
                'connection_count': ssid_data['connection_count'],
                'first_seen': ssid_data['first_seen'],
                'last_seen': ssid_data['last_seen']
            }
            total_rx += ssid_data['total_rx']
            total_tx += ssid_data['total_tx']
        
        summary['_totals'] = {
            'total_rx': total_rx,
            'total_tx': total_tx,
            'total_usage': total_rx + total_tx,
            'ssid_count': len(self.usage_data)
        }
        
        return summary
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old daily data beyond specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        removed_count = 0
        
        for ssid, ssid_data in self.usage_data.items():
            if 'daily' in ssid_data:
                dates_to_remove = []
                for date in ssid_data['daily'].keys():
                    if date < cutoff_str:
                        dates_to_remove.append(date)
                
                for date in dates_to_remove:
                    del ssid_data['daily'][date]
                    removed_count += 1
        
        # Update last cleanup timestamp
        if not hasattr(self, '_metadata'):
            self._metadata = {}
        self._metadata['last_cleanup'] = datetime.now().isoformat()
        
        return removed_count
    
    def _auto_cleanup_if_needed(self) -> None:
        """Automatically cleanup old data if it's been more than a day since last cleanup"""
        if not hasattr(self, '_metadata'):
            self._metadata = {}
        
        last_cleanup_str = self._metadata.get('last_cleanup')
        
        # Check if we need to run cleanup (once per day)
        should_cleanup = False
        if not last_cleanup_str:
            should_cleanup = True
        else:
            try:
                last_cleanup = datetime.fromisoformat(last_cleanup_str)
                # Run cleanup if it's been more than 24 hours
                if datetime.now() - last_cleanup > timedelta(hours=24):
                    should_cleanup = True
            except ValueError:
                should_cleanup = True
        
        if should_cleanup:
            removed_count = self.cleanup_old_data(90)  # Keep 90 days of data
            if removed_count > 0:
                print(f"🧹 Auto-cleanup: Removed {removed_count} old daily records (>90 days)")
                self.save_data()  # Save after cleanup
    
    def set_limit(self, ssid: str, limit_bytes: int, interval: str = 'monthly') -> None:
        """Set data limit for specific SSID"""
        self.limits_data[ssid] = {
            'limit': limit_bytes,
            'interval': interval,
            'created': datetime.now().isoformat()
        }
        self.save_limits()
    
    def get_limit(self, ssid: str) -> Optional[Dict[str, Any]]:
        """Get data limit for specific SSID"""
        return self.limits_data.get(ssid)
    
    def remove_limit(self, ssid: str) -> bool:
        """Remove data limit for specific SSID"""
        if ssid in self.limits_data:
            del self.limits_data[ssid]
            self.save_limits()
            return True
        return False
