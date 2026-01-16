"""Tests for configuration loader"""

import pytest
import tempfile
import os
from tap_station.config import Config


def test_config_loading():
    """Test loading configuration from YAML"""
    # Create temporary config file
    config_content = """
station:
  device_id: "test-station"
  stage: "TEST_STAGE"
  session_id: "test-session"

database:
  path: "test.db"
  wal_mode: true

nfc:
  i2c_bus: 1
  address: 0x24
  timeout: 2
  retries: 3
  debounce_seconds: 1.0

feedback:
  buzzer_enabled: false
  led_enabled: false

logging:
  path: "test.log"
  level: "DEBUG"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config = Config(config_path)

        assert config.device_id == "test-station"
        assert config.stage == "TEST_STAGE"
        assert config.session_id == "test-session"
        assert config.database_path == "test.db"
        assert config.wal_mode is True
        assert config.i2c_bus == 1
        assert config.i2c_address == 0x24
        assert config.nfc_timeout == 2
        assert config.nfc_retries == 3
        assert config.debounce_seconds == 1.0
        assert config.buzzer_enabled is False
        assert config.led_enabled is False
        assert config.log_path == "test.log"
        assert config.log_level == "DEBUG"

    finally:
        os.unlink(config_path)


def test_config_defaults():
    """Test configuration defaults"""
    config_content = """
station:
  device_id: "test"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config = Config(config_path)

        # Check defaults
        assert config.device_id == "test"
        assert config.stage == "UNKNOWN"  # default
        assert config.session_id == "default-session"  # default

    finally:
        os.unlink(config_path)


def test_config_file_not_found():
    """Test error when config file doesn't exist"""
    with pytest.raises(FileNotFoundError):
        Config("nonexistent.yaml")


def test_config_get_method():
    """Test get method with dot notation"""
    config_content = """
station:
  device_id: "test"
  nested:
    value: 42
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config = Config(config_path)

        assert config.get("station.device_id") == "test"
        assert config.get("station.nested.value") == 42
        assert config.get("nonexistent.key", "default") == "default"

    finally:
        os.unlink(config_path)
