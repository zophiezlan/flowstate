"""Configuration loader for tap station"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from .constants import WorkflowStages
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Required configuration fields that must be explicitly set
_REQUIRED_FIELDS = ["station.device_id", "station.stage", "station.session_id"]

# Valid GPIO pin numbers for Raspberry Pi (BCM numbering)
_VALID_GPIO_PINS = set(range(0, 28))

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
    "admin_password": (
        "web_server.admin.password",
        "CHANGE-ME-BEFORE-DEPLOYMENT",
        str,
    ),
    "admin_session_timeout_minutes": (
        "web_server.admin.session_timeout_minutes",
        60,
        int,
    ),
    # API limits and validation
    "api_max_events_per_request": (
        "web_server.api.max_events_per_request",
        1000,
        int,
    ),
    "api_max_token_id_length": (
        "web_server.api.max_token_id_length",
        100,
        int,
    ),
    "api_max_uid_length": ("web_server.api.max_uid_length", 100, int),
    "api_max_stage_length": ("web_server.api.max_stage_length", 50, int),
    # Analytics and dashboard settings
    "analytics_wait_sample_size": (
        "web_server.analytics.wait_sample_size",
        20,
        int,
    ),
    "analytics_recent_completions_limit": (
        "web_server.analytics.recent_completions_limit",
        10,
        int,
    ),
    "analytics_recent_events_limit": (
        "web_server.analytics.recent_events_limit",
        15,
        int,
    ),
    "analytics_activity_hours": (
        "web_server.analytics.activity_hours",
        12,
        int,
    ),
    "analytics_max_estimate_minutes": (
        "web_server.analytics.max_estimate_minutes",
        120,
        int,
    ),
    "analytics_recent_service_window": (
        "web_server.analytics.recent_service_window_minutes",
        30,
        int,
    ),
    "analytics_confidence_sample_size": (
        "web_server.analytics.confidence_sample_size",
        5,
        int,
    ),
    # Hardware monitoring thresholds
    "hardware_temp_warning": ("hardware.temp_warning_celsius", 70, int),
    "hardware_temp_critical": ("hardware.temp_critical_celsius", 80, int),
    "hardware_disk_warning": ("hardware.disk_warning_percent", 80, int),
    "hardware_disk_critical": ("hardware.disk_critical_percent", 90, int),
    # On-Site Setup Features
    "onsite_enabled": ("onsite.enabled", True, bool),
    # WiFi Management
    "onsite_wifi_enabled": ("onsite.wifi.enabled", True, bool),
    "onsite_wifi_setup_button_gpio": (
        "onsite.wifi.setup_button_gpio",
        23,
        int,
    ),
    "onsite_wifi_networks_file": (
        "onsite.wifi.networks_file",
        "config/wifi_networks.conf",
        str,
    ),
    # mDNS Discovery
    "onsite_mdns_enabled": ("onsite.mdns.enabled", True, bool),
    # Failover Settings
    "onsite_failover_enabled": ("onsite.failover.enabled", True, bool),
    "onsite_failover_peer_hostname": (
        "onsite.failover.peer_hostname",
        None,
        str,
    ),
    "onsite_failover_check_interval": (
        "onsite.failover.check_interval",
        30,
        int,
    ),
    "onsite_failover_failure_threshold": (
        "onsite.failover.failure_threshold",
        2,
        int,
    ),
    # Status LEDs
    "onsite_status_leds_enabled": ("onsite.status_leds.enabled", True, bool),
    "onsite_status_leds_gpio_blue": (
        "onsite.status_leds.gpio_blue",
        None,
        int,
    ),
}


class Config:
    """Load and manage configuration from YAML file"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Load configuration from YAML file

        Args:
            config_path: Path to config.yaml file

        Raises:
            ConfigurationError: If config file is missing or invalid
        """
        if not os.path.exists(config_path):
            # Provide helpful error message with suggestion
            error_msg = (
                f"Configuration file not found: {config_path}\n"
                f"Please create a config.yaml file from the example:\n"
                f"  cp config.yaml.example config.yaml\n"
                f"Then edit config.yaml to set your station's device_id, stage, and session_id."
            )
            raise ConfigurationError(error_msg, config_key=config_path)

        try:
            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML syntax in configuration file: {e}"
            raise ConfigurationError(error_msg, config_key=config_path)
        except Exception as e:
            error_msg = f"Failed to read configuration file: {e}"
            raise ConfigurationError(error_msg, config_key=config_path)

        # Cache for computed values
        self._cache: Dict[str, Any] = {}

        # Validate configuration on load
        self._validate_config()

    def _validate_config(self) -> None:
        """
        Validate configuration values on load.
        Logs warnings for missing required fields or invalid values.
        """
        config_warnings: List[str] = []

        # Get default device_id from schema for comparison
        default_device_id = _CONFIG_SCHEMA["device_id"][1]

        # Check required fields
        for field in _REQUIRED_FIELDS:
            value = self.get(field)
            if value is None or value == "":
                config_warnings.append(
                    f"Required field '{field}' is missing or empty"
                )
            elif field == "station.device_id" and value == default_device_id:
                config_warnings.append(
                    f"Field '{field}' uses default value '{default_device_id}' - "
                    "please set a unique device ID"
                )

        # Validate GPIO pins if feedback is enabled
        if self.get("feedback.buzzer_enabled", False):
            buzzer_pin = self.get("feedback.gpio.buzzer", 17)
            if buzzer_pin not in _VALID_GPIO_PINS:
                config_warnings.append(
                    f"Invalid buzzer GPIO pin {buzzer_pin} - "
                    f"must be 0-27 (BCM numbering)"
                )

        if self.get("feedback.led_enabled", False):
            for led_name, default in [("led_green", 27), ("led_red", 22)]:
                led_pin = self.get(f"feedback.gpio.{led_name}", default)
                if led_pin not in _VALID_GPIO_PINS:
                    config_warnings.append(
                        f"Invalid {led_name} GPIO pin {led_pin} - "
                        f"must be 0-27 (BCM numbering)"
                    )

        # Validate numeric ranges
        nfc_timeout = self.get("nfc.timeout", 2)
        if not (1 <= nfc_timeout <= 30):
            config_warnings.append(
                f"NFC timeout {nfc_timeout}s outside recommended range (1-30s)"
            )

        debounce = self.get("nfc.debounce_seconds", 1.0)
        if not (0.1 <= debounce <= 10.0):
            config_warnings.append(
                f"Debounce {debounce}s outside recommended range (0.1-10s)"
            )

        web_port = self.get("web_server.port", 8080)
        if not (1024 <= web_port <= 65535):
            config_warnings.append(
                f"Web server port {web_port} outside valid range (1024-65535)"
            )

        # Validate log level
        log_level = self.get("logging.level", "INFO")
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level.upper() not in valid_levels:
            config_warnings.append(
                f"Invalid log level '{log_level}' - "
                f"must be one of: {', '.join(valid_levels)}"
            )

        # Cross-validate station stage against service config workflow
        stage_warnings = self._validate_stage_against_service_config()
        config_warnings.extend(stage_warnings)

        # Log all warnings
        for warning in config_warnings:
            logger.warning(f"Configuration: {warning}")

    def _validate_stage_against_service_config(self) -> List[str]:
        """
        Validate that this station's stage exists in the service config workflow.

        Returns:
            List of warning messages if validation fails
        """
        warnings = []
        stage = self.get("station.stage")

        # Skip validation for UNKNOWN or missing stage (already caught above)
        if not stage or stage == "UNKNOWN":
            return warnings

        try:
            # Try to import and load service config
            from .service_config_loader import ServiceConfigLoader

            service_config = ServiceConfigLoader.get_config()
            if service_config and service_config.workflow_stages:
                valid_stages = [s.id for s in service_config.workflow_stages]

                # Normalize the stage for comparison (handle case differences)
                from .constants import WorkflowStages
                normalized_stage = WorkflowStages.normalize(stage)

                if normalized_stage not in valid_stages:
                    warnings.append(
                        f"Station stage '{stage}' (normalized: '{normalized_stage}') "
                        f"not found in service config workflow. "
                        f"Valid stages: {', '.join(valid_stages)}"
                    )
        except ImportError:
            # Service config loader not available, skip validation
            pass
        except Exception as e:
            # Don't fail startup for service config issues
            logger.debug(f"Could not validate stage against service config: {e}")

        return warnings

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

    def get_required(self, key_path: str) -> Any:
        """
        Get a required configuration value with better error message.

        Args:
            key_path: Dot-separated path (e.g., "station.device_id")

        Returns:
            Configuration value

        Raises:
            ConfigurationError: If the required value is missing
        """
        value = self.get(key_path)

        if value is None or value == "":
            error_msg = (
                f"Required configuration field '{key_path}' is missing or empty.\n"
                f"Please add it to your config.yaml file. Example:\n"
                f"  {self._format_example(key_path)}"
            )
            raise ConfigurationError(error_msg, config_key=key_path)

        return value

    def _format_example(self, key_path: str) -> str:
        """
        Format an example configuration snippet for a given key path.

        Args:
            key_path: Dot-separated path

        Returns:
            Formatted YAML example
        """
        keys = key_path.split(".")
        indent = "  "

        # Build nested YAML structure
        lines = []
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                lines.append(f"{indent * i}{key}: <your-value-here>")
            else:
                lines.append(f"{indent * i}{key}:")

        return "\n  ".join(lines)

    def __getattr__(self, name: str) -> Any:
        """
        Dynamic attribute access for configuration values.

        This allows accessing config values as attributes while
        keeping the code DRY by using the schema definition.
        """
        # Avoid recursion for private attributes
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'"
            )

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
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Configuration: Failed to convert '{name}' value '{value}' "
                        f"to {type_converter.__name__}, using default: {default}"
                    )
                    value = default

            # Cache the result
            self._cache[name] = value
            return value

        raise AttributeError(
            f"'{type(self).__name__}' has no attribute '{name}'"
        )

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
                raise FileNotFoundError(
                    f"Config file not found: {config_path}"
                )
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
