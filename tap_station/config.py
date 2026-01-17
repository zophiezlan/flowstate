"""Configuration loader for tap station"""

import os
import yaml
from typing import Any


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

    @property
    def device_id(self) -> str:
        """Get station device ID"""
        return self.get("station.device_id", "unknown")

    @property
    def stage(self) -> str:
        """Get station stage name"""
        stage = self.get("station.stage", "UNKNOWN")
        if not isinstance(stage, str):
            return "UNKNOWN"

        normalized = stage.strip()
        if not normalized:
            return "UNKNOWN"

        lowered = normalized.lower()
        if lowered in {"join", "queue_join", "queue-join", "queue join"}:
            return "QUEUE_JOIN"
        if lowered in {"exit", "queue_exit", "queue-exit", "queue exit"}:
            return "EXIT"

        return normalized.upper()

    @property
    def session_id(self) -> str:
        """Get current session ID"""
        return self.get("station.session_id", "default-session")

    @property
    def database_path(self) -> str:
        """Get database file path"""
        return self.get("database.path", "data/events.db")

    @property
    def wal_mode(self) -> bool:
        """Get WAL mode setting"""
        return self.get("database.wal_mode", True)

    @property
    def i2c_bus(self) -> int:
        """Get I2C bus number"""
        return self.get("nfc.i2c_bus", 1)

    @property
    def i2c_address(self) -> int:
        """Get I2C address for PN532"""
        return self.get("nfc.address", 0x24)

    @property
    def nfc_timeout(self) -> int:
        """Get NFC read timeout"""
        return self.get("nfc.timeout", 2)

    @property
    def nfc_retries(self) -> int:
        """Get NFC retry count"""
        return self.get("nfc.retries", 3)

    @property
    def debounce_seconds(self) -> float:
        """Get debounce time in seconds"""
        return self.get("nfc.debounce_seconds", 1.0)

    @property
    def buzzer_enabled(self) -> bool:
        """Check if buzzer is enabled"""
        return self.get("feedback.buzzer_enabled", False)

    @property
    def led_enabled(self) -> bool:
        """Check if LEDs are enabled"""
        return self.get("feedback.led_enabled", False)

    @property
    def gpio_buzzer(self) -> int:
        """Get GPIO pin for buzzer"""
        return self.get("feedback.gpio.buzzer", 17)

    @property
    def gpio_led_green(self) -> int:
        """Get GPIO pin for green LED"""
        return self.get("feedback.gpio.led_green", 27)

    @property
    def gpio_led_red(self) -> int:
        """Get GPIO pin for red LED"""
        return self.get("feedback.gpio.led_red", 22)

    @property
    def beep_success(self) -> list:
        """Get success beep pattern"""
        return self.get("feedback.beep_success", [0.1])

    @property
    def beep_duplicate(self) -> list:
        """Get duplicate beep pattern"""
        return self.get("feedback.beep_duplicate", [0.1, 0.05, 0.1])

    @property
    def beep_error(self) -> list:
        """Get error beep pattern"""
        return self.get("feedback.beep_error", [0.3])

    @property
    def shutdown_button_enabled(self) -> bool:
        """Check if shutdown button is enabled"""
        return self.get("shutdown_button.enabled", False)

    @property
    def shutdown_button_gpio(self) -> int:
        """Get GPIO pin for shutdown button"""
        return self.get("shutdown_button.gpio_pin", 26)

    @property
    def shutdown_button_hold_time(self) -> float:
        """Get shutdown button hold time in seconds"""
        return self.get("shutdown_button.hold_time", 3.0)

    @property
    def shutdown_button_delay_minutes(self) -> int:
        """Get shutdown delay in minutes"""
        return self.get("shutdown_button.delay_minutes", 1)

    @property
    def log_path(self) -> str:
        """Get log file path"""
        return self.get("logging.path", "logs/tap-station.log")

    @property
    def log_level(self) -> str:
        """Get log level"""
        return self.get("logging.level", "INFO")

    @property
    def log_max_size_mb(self) -> int:
        """Get max log file size in MB"""
        return int(self.get("logging.max_size_mb", 10))

    @property
    def log_backup_count(self) -> int:
        """Get number of backup log files"""
        return int(self.get("logging.backup_count", 3))

    @property
    def web_server_enabled(self) -> bool:
        """Check if web server is enabled"""
        return bool(self.get("web_server.enabled", False))

    @property
    def web_server_host(self) -> str:
        """Get web server host"""
        return self.get("web_server.host", "0.0.0.0")

    @property
    def web_server_port(self) -> int:
        """Get web server port"""
        return int(self.get("web_server.port", 8080))

    def __repr__(self) -> str:
        return (
            f"Config(device={self.device_id}, "
            f"stage={self.stage}, session={self.session_id})"
        )
