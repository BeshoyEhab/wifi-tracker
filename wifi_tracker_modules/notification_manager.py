"""
Notification Manager Module for WiFi Tracker
Handles system notifications using notify-send
"""

import subprocess
import shutil
from enum import Enum

class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    CRITICAL = "critical"

class NotificationManager:
    """Manages system notifications"""
    
    def __init__(self):
        self._check_dependency()
    
    def _check_dependency(self):
        """Check if notify-send is available"""
        self.available = shutil.which('notify-send') is not None
        
    def send_notification(self, title: str, message: str, urgency: Urgency = Urgency.NORMAL) -> bool:
        """
        Send a desktop notification
        
        Args:
            title: Notification title
            message: Notification body
            urgency: Urgency level (low, normal, critical)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.available:
            return False
            
        try:
            cmd = [
                'notify-send',
                '--app-name=WiFi Tracker',
                f'--urgency={urgency.value}',
                title,
                message
            ]
            
            # Add icon if available (optional enhancement)
            # cmd.extend(['--icon=network-wireless'])
            
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, Exception):
            return False

# Global instance for easy access
notifier = NotificationManager()
