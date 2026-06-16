"""
Configuration Module for WiFi Tracker
Handles path configuration and XDG Base Directory specification compliance.
"""

import os
from pathlib import Path


class Config:
    """Central configuration for file paths and settings"""

    APP_NAME = "wifi-tracker"

    @staticmethod
    def get_data_dir() -> Path:
        """
        Get the data directory respecting XDG_DATA_HOME.
        Default: ~/.local/share/wifi-tracker
        """
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data)
        else:
            base = Path.home() / ".local" / "share"

        path = base / Config.APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_cache_dir() -> Path:
        """
        Get the cache directory respecting XDG_CACHE_HOME.
        Default: ~/.cache/wifi-tracker
        """
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            base = Path(xdg_cache)
        else:
            base = Path.home() / ".cache"

        path = base / Config.APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_config_dir() -> Path:
        """
        Get the config directory respecting XDG_CONFIG_HOME.
        Default: ~/.config/wifi-tracker
        """
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            base = Path(xdg_config)
        else:
            base = Path.home() / ".config"

        path = base / Config.APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Specialized paths

    @classmethod
    def get_data_file(cls) -> Path:
        """Path to the main usage data JSON file"""
        return cls.get_data_dir() / "wifi_usage.json"

    @classmethod
    def get_limits_file(cls) -> Path:
        """Path to the limits data JSON file"""
        return cls.get_data_dir() / "wifi_limits.json"

    @classmethod
    def get_pid_file(cls) -> Path:
        """Path to the daemon PID file"""
        # PID files often go in runtime dir, but cache is acceptable for user session
        # XDG_RUNTIME_DIR is preferred if available
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
        if xdg_runtime:
            return Path(xdg_runtime) / cls.APP_NAME / "daemon.pid"
        return cls.get_cache_dir() / "daemon.pid"

    @classmethod
    def get_log_file(cls) -> Path:
        """Path to the daemon log file"""
        return cls.get_cache_dir() / "daemon.log"

    @classmethod
    def get_error_log_file(cls) -> Path:
        """Path to the daemon error log file"""
        return cls.get_cache_dir() / "error.log"
