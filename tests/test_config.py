"""Tests for v1 configuration loader."""

import os
import tempfile

import pytest

from tap_station.config import Config


def _write_temp_config(content: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        return f.name


def test_config_loading_v1_stage():
    config_path = _write_temp_config(
        """
station:
  device_id: "test-station"
  stage: "entered"
  session_id: "test-session"
"""
    )
    try:
        config = Config(config_path)
        assert config.device_id == "test-station"
        assert config.stage == "ENTERED"
        assert config.session_id == "test-session"
    finally:
        os.unlink(config_path)


def test_config_defaults():
    config_path = _write_temp_config(
        """
station:
  device_id: "test"
"""
    )
    try:
        config = Config(config_path)
        assert config.device_id == "test"
        assert config.stage == "UNKNOWN"
        assert config.session_id == "default-session"
    finally:
        os.unlink(config_path)


def test_config_file_not_found():
    from tap_station.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        Config("nonexistent.yaml")


def test_get_method_with_dot_notation():
    config_path = _write_temp_config(
        """
station:
  device_id: "test"
  nested:
    value: 42
"""
    )
    try:
        config = Config(config_path)
        assert config.get("station.device_id") == "test"
        assert config.get("station.nested.value") == 42
        assert config.get("nonexistent.key", "default") == "default"
    finally:
        os.unlink(config_path)
