"""
WiFi Tracker Modules Package
Enhanced modular WiFi usage tracking system
"""

__version__ = "2.0.0"
__author__ = "WiFi Tracker Enhanced"

# Import main classes for easy access
from .network_monitor import NetworkMonitor
from .process_manager import ProcessManager
from .data_manager import DataManager
from .display_manager import DisplayManager

__all__ = [
    'NetworkMonitor',
    'ProcessManager', 
    'DataManager',
    'DisplayManager'
]
