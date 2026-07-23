"""
WiFi Tracker Modules Package
Enhanced modular WiFi usage tracking system
"""

__version__ = "0.1.2"
__author__ = "WiFi Tracker Enhanced"

# Import main classes for easy access
from .data_manager import DataManager
from .display_manager import DisplayManager
from .network_monitor import NetworkMonitor
from .process_manager import ProcessManager

__all__ = ["NetworkMonitor", "ProcessManager", "DataManager", "DisplayManager"]
