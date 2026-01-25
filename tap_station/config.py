"""Configuration loader for tap station"""

import os
import yaml
from typing import Any, Dict, Tuple, Callable, Optional

from .constants import WorkflowStages


# Configuration schema: maps attribute names to (config_path, default_value, type_converter)
# type_converter is optional - if None, returns value as-is
_CONFIG_SCHEMA: Dict[str, Tuple[str, Any, Optional[Callable]]] = {
    # Station settings
    "device_id": ("station.device_id", "unknown", str),
    "session_id": ("station.session_id", "default-session", str),

    # Database settings
    "database_path": ("database.path", "data/events.db", str),
    "wal_mode": ("database.wal_mode", True, bool),

    # NFC settings
    "i2c_bus": ("nfc.i2c_bus", 1, int),
    "i2c_address": ("nfc.address", 0x24, int),
    "nfc_timeout": ("nfc.timeout", 2, int),
    "nfc_retries": ("nfc.retries", 3, int),
    "debounce_seconds": ("nfc.debounce_seconds", 1.0, float),
    "auto_init_cards": ("nfc.auto_init_cards", False, bool),
    "auto_init_start_id": ("nfc.auto_init_start_id", 1, int),

    # Feedback settings
    "buzzer_enabled": ("feedback.buzzer_enabled", False, bool),
    "led_enabled": ("feedback.led_enabled", False, bool),
    "gpio_buzzer": ("feedback.gpio.buzzer", 17, int),
    "gpio_led_green": ("feedback.gpio.led_green", 27, int),
    "gpio_led_red": ("feedback.gpio.led_red", 22, int),
    "beep_success": ("feedback.beep_success", [0.1], None),
    "beep_duplicate": ("feedback.beep_duplicate", [0.1, 0.05, 0.1], None),
    "beep_error": ("feedback.beep_error", [0.3], None),

    # Shutdown button settings
    "shutdown_button_enabled": ("shutdown_button.enabled", False, bool),
    "shutdown_button_gpio": ("shutdown_button.gpio_pin", 26, int),
    "shutdown_button_hold_time": ("shutdown_button.hold_time", 3.0, float),
    "shutdown_button_delay_minutes": ("shutdown_button.delay_minutes", 1, int),

    # Logging settings
    "log_path": ("logging.path", "logs/tap-station.log", str),
    "log_level": ("logging.level", "INFO", str),
    "log_max_size_mb": ("logging.max_size_mb", 10, int),
    "log_backup_count": ("logging.backup_count", 3, int),

    # Web server settings
    "web_server_enabled": ("web_server.enabled", False, bool),
    "web_server_host": ("web_server.host", "0.0.0.0", str),
    "web_server_port": ("web_server.port", 8080, int),

    # API limits and validation
    "api_max_events_per_request": ("web_server.api.max_events_per_request", 1000, int),
    "api_max_token_id_length": ("web_server.api.max_token_id_length", 100, int),
    "api_max_uid_length": ("web_server.api.max_uid_length", 100, int),
    "api_max_stage_length": ("web_server.api.max_stage_length", 50, int),

    # Analytics and dashboard settings
    "analytics_wait_sample_size": ("web_server.analytics.wait_sample_size", 20, int),
    "analytics_recent_completions_limit": ("web_server.analytics.recent_completions_limit", 10, int),
    "analytics_recent_events_limit": ("web_server.analytics.recent_events_limit", 15, int),
    "analytics_activity_hours": ("web_server.analytics.activity_hours", 12, int),
    "analytics_max_estimate_minutes": ("web_server.analytics.max_estimate_minutes", 120, int),
    "analytics_recent_service_window": ("web_server.analytics.recent_service_window_minutes", 30, int),
    "analytics_confidence_sample_size": ("web_server.analytics.confidence_sample_size", 5, int),

    # Hardware monitoring thresholds
    "hardware_temp_warning": ("hardware.temp_warning_celsius", 70, int),
    "hardware_temp_critical": ("hardware.temp_critical_celsius", 80, int),
    "hardware_disk_warning": ("hardware.disk_warning_percent", 80, int),
    "hardware_disk_critical": ("hardware.disk_critical_percent", 90, int),
}


class Config:
    """Load and manage configuration from YAML file"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Load configuration from YAML file

        Args:
            config_path: Path to config.yaml file
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            self._config = yaml.safe_load(f)

        # Cache for computed values
        self._cache: Dict[str, Any] = {}

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated path (e.g., "station.device_id")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def __getattr__(self, name: str) -> Any:
        """
        Dynamic attribute access for configuration values.

        This allows accessing config values as attributes while
        keeping the code DRY by using the schema definition.
        """
        # Avoid recursion for private attributes
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

        # Check if it's a known config attribute
        if name in _CONFIG_SCHEMA:
            # Check cache first
            if name in self._cache:
                return self._cache[name]

            config_path, default, type_converter = _CONFIG_SCHEMA[name]
            value = self.get(config_path, default)

            # Apply type conversion if specified
            if type_converter is not None and value is not None:
                try:
                    value = type_converter(value)
                except (ValueError, TypeError):
                    value = default

            # Cache the result
            self._cache[name] = value
            return value

        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    @property
    def stage(self) -> str:
        """Get station stage name (with normalization)"""
        if "stage" in self._cache:
            return self._cache["stage"]

        stage = self.get("station.stage", "UNKNOWN")
        normalized = WorkflowStages.normalize(stage)
        self._cache["stage"] = normalized
        return normalized

    def reload(self, config_path: Optional[str] = None) -> None:
        """
        Reload configuration from file.

        Args:
            config_path: Optional new config path
        """
        if config_path:
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Config file not found: {config_path}")
            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f)

        # Clear cache to force re-read of all values
        self._cache.clear()

    def __repr__(self) -> str:
        return (
            f"Config(device={self.device_id}, "
            f"stage={self.stage}, session={self.session_id})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Export all configuration values as a dictionary.

        Returns:
            Dictionary of all configuration values
        """
        result = {}
        for name in _CONFIG_SCHEMA:
            result[name] = getattr(self, name)
        result["stage"] = self.stage
        return result
