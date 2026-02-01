"""
Data Manager Module for WiFi Tracker
Handles data persistence, validation, and management
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from types import NoneType
from typing import Dict, Any, Optional

from wifi_tracker_modules.config import Config


class DataManager:
    """
    Manages WiFi usage data persistence and validation.

    Attributes:
        data_file (Path): Path to the main usage data JSON file.
        limits_file (Path): Path to the limits data JSON file.
        usage_data (Dict): In-memory storage of usage data.
        limits_data (Dict): In-memory storage of limits data.
    """
    
    def __init__(self, data_file: Optional[str] = None, limits_file: Optional[str] = None):
        """
        Initialize the Data Manager.

        Args:
            data_file (str, optional): Path to the WiFi usage data file.
            limits_file (str, optional): Path to the data limits file.
        """
        self.data_file = Path(data_file) if data_file else Config.get_data_file()
        self.limits_file = Path(limits_file) if limits_file else Config.get_limits_file()
        
        # Check for legacy data and migrate if needed
        self._check_and_migrate_legacy_data()
        
        # Initialize data structures
        self.usage_data = {}
        self.limits_data = {}
        self._metadata = {}  # Track cleanup and other metadata
        
        # Load existing data
        self.load_data()
        self.load_limits()
    
    def _check_and_migrate_legacy_data(self) -> None:
        """
        Check for legacy data in ~/.cache and migrate to new XDG location if found.
        Only migrates if the new data file doesn't already exist.
        """
        if self.data_file.exists():
            return
            
        legacy_data = Path.home() / ".cache" / "wifi_usage.json"
        legacy_limits = Path.home() / ".cache" / "wifi_limits.json"
        
        if legacy_data.exists():
            print(f"📦 Migrating data from {legacy_data} to {self.data_file}...")
            try:
                self.data_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(legacy_data), str(self.data_file))
                if legacy_limits.exists():
                    shutil.move(str(legacy_limits), str(self.limits_file))
                print("✅ Migration successful")
            except Exception as e:
                print(f"❌ Migration failed: {e}")

    def load_data(self) -> Dict[str, Any]:
        """
        Load usage data from file with validation and migration.

        Returns:
            Dict[str, Any]: The loaded usage data.
        """
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
        """
        Load limits data from file.

        Returns:
            Dict[str, Any]: The loaded limits data.
        """
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
        """
        Save usage data to file.

        Returns:
            bool: True if save was successful, False otherwise.
        """
        try:
            # Create backup of existing file
            if self.data_file.exists():
                backup_file = self.data_file.with_suffix('.json.bak')
                # Use replace (atomic) instead of rename/rename to avoid issues
                try:
                    shutil.copy2(self.data_file, backup_file)
                except OSError:
                    pass # Ignore backup errors if necessary
            
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
        """
        Save limits data to file.

        Returns:
            bool: True if save was successful, False otherwise.
        """
        try:
            with open(self.limits_file, 'w') as f:
                json.dump(self.limits_data, f, indent=2)
            return True
            
        except (PermissionError, OSError) as e:
            print(f"Error saving limits: {e}")
            return False
    
    def _validate_and_migrate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and migrate data structure for backward compatibility.

        Args:
            data (Dict[str, Any]): The raw loaded data.

        Returns:
            Dict[str, Any]: Validated and structured data.
        """
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
                    timestamp: Optional[datetime] = None, rx_rate: float = 0, tx_rate: float = 0) -> None:
        """
        Update usage data for a specific SSID using delta-based tracking.

        Args:
            ssid (str): The SSID name.
            rx_bytes (int): Current total RX bytes from interface.
            tx_bytes (int): Current total TX bytes from interface.
            timestamp (datetime, optional): Measurement timestamp. Defaults to now.
            rx_rate (float, optional): Current download rate. Defaults to 0.
            tx_rate (float, optional): Current upload rate. Defaults to 0.
        """
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
        """
        Get current session usage for an SSID.

        Args:
            ssid (str): The SSID name.
            current_rx (int): Current interface RX bytes.
            current_tx (int): Current interface TX bytes.

        Returns:
            tuple: (session_rx, session_tx) usage in bytes.
        """
        if ssid not in self.usage_data:
            return 0, 0
        
        ssid_data = self.usage_data[ssid]
        session_start_rx = ssid_data.get('session_start_rx', current_rx)
        session_start_tx = ssid_data.get('session_start_tx', current_tx)
        
        # Calculate session usage (current interface stats - session start)
        session_rx = max(0, current_rx - session_start_rx)
        session_tx = max(0, current_tx - session_start_tx)
        
        return session_rx, session_tx
    
    def get_usage_summary(self, ssid: str = "") -> Dict[str, Any]:
        """
        Get usage summary for specific SSID or all SSIDs.

        Args:
            ssid (str, optional): Specific SSID to summarize. Defaults to None (all SSIDs).

        Returns:
            Dict[str, Any]: Summary dictionary.
        """
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
        """
        Clean up old daily data beyond specified days.

        Args:
            days_to_keep (int, optional): Number of days to keep. Defaults to 30.

        Returns:
            int: Number of day records removed.
        """
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
        """
        Automatically cleanup old data if it's been more than a day since last cleanup.
        """
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

    def update_limit_status(self, ssid: str, key: str, value: Any) -> None:
        """
        Update a specific status flag for an SSID limit.

        Args:
            ssid (str): The SSID to update.
            key (str): The status key (e.g., 'notified_80').
            value (Any): The value to set.
        """
        if ssid in self.limits_data:
            self.limits_data[ssid][key] = value
            self.save_limits()
    
    def set_limit(self, ssid: str, limit_bytes: int, interval: str = 'monthly') -> None:
        """
        Set data limit for specific SSID.

        Args:
            ssid (str): SSID to set limit for.
            limit_bytes (int): Limit in bytes.
            interval (str, optional): Interval ('daily', 'weekly', 'monthly'). Defaults to 'monthly'.
        """
        self.limits_data[ssid] = {
            'limit': limit_bytes,
            'interval': interval,
            'created': datetime.now().isoformat()
        }
        self.save_limits()
    
    def get_limit(self, ssid: str) -> Optional[Dict[str, Any]]:
        """
        Get data limit for specific SSID.

        Args:
            ssid (str): SSID to get limit for.

        Returns:
            Optional[Dict[str, Any]]: Limit data or None.
        """
        return self.limits_data.get(ssid)
    
    def remove_limit(self, ssid: str) -> bool:
        """
        Remove data limit for specific SSID.

        Args:
            ssid (str): SSID to remove limit for.

        Returns:
            bool: True if limit was removed, False if not found.
        """
        if ssid in self.limits_data:
            del self.limits_data[ssid]
            self.save_limits()
            return True
        return False
