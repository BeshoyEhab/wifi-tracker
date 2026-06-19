import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    test_dir = tempfile.mkdtemp()
    yield Path(test_dir)
    shutil.rmtree(test_dir)


@pytest.fixture
def data_files(temp_dir):
    """Create empty data and limits files."""
    data_file = temp_dir / "wifi_usage.json"
    limits_file = temp_dir / "wifi_limits.json"

    with open(data_file, "w") as f:
        json.dump({}, f)
    with open(limits_file, "w") as f:
        json.dump({}, f)

    return data_file, limits_file


@pytest.fixture
def data_manager(data_files):
    """Create a DataManager instance with temp files."""
    from wifi_tracker_modules.data_manager import DataManager

    data_file, limits_file = data_files
    return DataManager(str(data_file), str(limits_file))


@pytest.fixture
def mock_interface():
    """Return a mock network interface name."""
    return "wlan0"


@pytest.fixture
def sample_ssid():
    """Return a sample SSID for testing."""
    return "TestWiFi"


@pytest.fixture
def sample_usage_data() -> dict[str, Any]:
    """Return sample usage data for testing."""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "TestWiFi": {
            "total_rx": 1024 * 1024 * 100,  # 100MB
            "total_tx": 1024 * 1024 * 50,  # 50MB
            "first_seen": (datetime.now() - timedelta(days=7)).isoformat(),
            "last_seen": datetime.now().isoformat(),
            "connection_count": 15,
            "daily": {
                today: {
                    "rx": 1024 * 1024 * 10,  # 10MB
                    "tx": 1024 * 1024 * 5,  # 5MB
                    "sessions": 3,
                    "first_connection": datetime.now().isoformat(),
                    "last_connection": datetime.now().isoformat(),
                    "date": today,
                    "peak_rx_rate": 1024 * 1024,  # 1MB/s
                    "peak_tx_rate": 512 * 1024,  # 512KB/s
                    "connection_duration": 3600,
                    "data_points": 100,
                    "hourly": {},
                    "minutely": {},
                }
            },
            "sessions": [],
            "peak_rx_rate": 1024 * 1024,
            "peak_tx_rate": 512 * 1024,
            "last_interface_rx": 1024 * 1024 * 150,
            "last_interface_tx": 1024 * 1024 * 75,
            "session_start_rx": 1024 * 1024 * 140,
            "session_start_tx": 1024 * 1024 * 70,
            "gateway_ip": "192.168.1.1",
            "app_usage": {},
            "accuracy_stats": {
                "total_measurements": 100,
                "successful_measurements": 98,
                "last_accuracy_check": datetime.now().isoformat(),
                "accuracy_score": 0.98,
            },
        }
    }


@pytest.fixture
def sample_limits_data() -> dict[str, Any]:
    """Return sample limits data for testing."""
    return {
        "TestWiFi": {
            "limit": 1024 * 1024 * 1024 * 5,  # 5GB
            "interval": "monthly",
            "created": datetime.now().isoformat(),
            "notified_80": False,
            "notified_100": False,
        }
    }


@pytest.fixture
def populated_data_manager(data_manager, sample_usage_data, sample_limits_data):
    """Create a DataManager pre-populated with sample data."""
    data_manager.usage_data = sample_usage_data
    data_manager.limits_data = sample_limits_data
    return data_manager
