"""
Dynamic Configuration Manager

This module provides dynamic configuration management with:
- Hot reload without service restart
- Configuration validation
- Change notification system
- Configuration versioning
- Rollback support

Key Features:
- YAML configuration loading and reloading
- Configuration change detection
- Subscriber notification on changes
- Safe configuration updates with validation
- Configuration history for rollback

Service Design Principles:
- Minimize service disruption during config changes
- Provide clear feedback on configuration state
- Enable runtime customization
- Support operational flexibility
"""

import logging
import os
import hashlib
import yaml
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy
import time

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ConfigurationChange:
    """Represents a configuration change"""

    path: str
    old_value: Any
    new_value: Any
    changed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "path": self.path,
            "old_value": str(self.old_value)[:100],  # Truncate for display
            "new_value": str(self.new_value)[:100],
            "changed_at": self.changed_at.isoformat(),
        }


@dataclass
class ConfigurationVersion:
    """A versioned configuration snapshot"""

    version: int
    config: Dict[str, Any]
    checksum: str
    created_at: datetime
    source: str  # "file", "api", "default"
    changes: List[ConfigurationChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version": self.version,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "change_count": len(self.changes),
        }


class ConfigurationValidator:
    """Validates configuration data"""

    def __init__(self):
        self._rules: Dict[str, Callable[[Any], bool]] = {}
        self._required_keys: Set[str] = set()
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default validation rules"""
        # Capacity rules
        self.add_rule(
            "capacity.people_per_hour", lambda v: isinstance(v, int) and 1 <= v <= 100
        )
        self.add_rule(
            "capacity.avg_service_minutes",
            lambda v: isinstance(v, int) and 1 <= v <= 120,
        )

        # Alert rules
        self.add_rule(
            "alerts.queue.warning_threshold", lambda v: isinstance(v, int) and v >= 1
        )
        self.add_rule(
            "alerts.queue.critical_threshold", lambda v: isinstance(v, int) and v >= 1
        )

        # UI rules
        self.add_rule(
            "ui.public_display.refresh_interval_seconds",
            lambda v: isinstance(v, int) and 1 <= v <= 60,
        )

    def add_rule(self, path: str, validator: Callable[[Any], bool]) -> None:
        """Add a validation rule for a config path"""
        self._rules[path] = validator

    def add_required(self, path: str) -> None:
        """Mark a config path as required"""
        self._required_keys.add(path)

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required keys
        for path in self._required_keys:
            if self._get_path(config, path) is None:
                errors.append(f"Missing required configuration: {path}")

        # Run validation rules
        for path, validator in self._rules.items():
            value = self._get_path(config, path)
            if value is not None:
                try:
                    if not validator(value):
                        errors.append(f"Invalid value for {path}: {value}")
                except Exception as e:
                    errors.append(f"Validation error for {path}: {str(e)}")

        return errors

    def _get_path(self, config: Dict, path: str) -> Any:
        """Get a value from config using dot notation"""
        parts = path.split(".")
        current = config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


class ConfigurationSubscriber:
    """Base class for configuration change subscribers"""

    def on_config_changed(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        changes: List[ConfigurationChange],
    ) -> None:
        """
        Called when configuration changes.

        Args:
            old_config: Previous configuration
            new_config: New configuration
            changes: List of specific changes
        """
        pass

    def on_config_reloaded(self, config: Dict[str, Any]) -> None:
        """
        Called when configuration is reloaded from file.

        Args:
            config: Reloaded configuration
        """
        pass


class DynamicConfigurationManager:
    """
    Manages dynamic configuration with hot reload support.

    This manager:
    - Loads configuration from YAML files
    - Detects and applies configuration changes
    - Notifies subscribers of changes
    - Maintains configuration history
    - Supports rollback to previous versions
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        auto_reload: bool = False,
        reload_interval_seconds: int = 30,
        max_history: int = 10,
    ):
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to configuration file
            auto_reload: Enable automatic file watching
            reload_interval_seconds: Interval for file change detection
            max_history: Maximum configuration versions to keep
        """
        self._config_path = config_path
        self._auto_reload = auto_reload
        self._reload_interval = reload_interval_seconds
        self._max_history = max_history

        self._config: Dict[str, Any] = {}
        self._history: List[ConfigurationVersion] = []
        self._version_counter = 0
        self._subscribers: List[ConfigurationSubscriber] = []
        self._validator = ConfigurationValidator()
        self._lock = threading.RLock()

        # File watching
        self._last_checksum: Optional[str] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._running = False

        # Load initial configuration
        if config_path:
            self.load_from_file(config_path)

        # Start auto-reload if enabled
        if auto_reload and config_path:
            self.start_auto_reload()

    def load_from_file(self, path: str) -> bool:
        """
        Load configuration from a YAML file.

        Args:
            path: Path to configuration file

        Returns:
            True if loaded successfully
        """
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                logger.warning(f"Configuration file not found: {path}")
                return False

            with open(path_obj, "r") as f:
                content = f.read()
                new_config = yaml.safe_load(content) or {}

            # Calculate checksum
            checksum = hashlib.md5(content.encode()).hexdigest()

            # Skip if unchanged
            if checksum == self._last_checksum:
                return True

            # Validate
            errors = self._validator.validate(new_config)
            if errors:
                logger.error(f"Configuration validation failed: {errors}")
                return False

            # Apply configuration
            with self._lock:
                old_config = deepcopy(self._config)
                changes = self._detect_changes(old_config, new_config)

                self._config = new_config
                self._config_path = str(path_obj)
                self._last_checksum = checksum

                # Save to history
                self._save_version(new_config, checksum, "file", changes)

                # Notify subscribers
                self._notify_reload(new_config)
                if changes:
                    self._notify_changes(old_config, new_config, changes)

            logger.info(
                f"Configuration loaded from {path} (version {self._version_counter})"
            )
            return True

        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration from {path}: {e}")
            return False

    def load_from_dict(self, config: Dict[str, Any], source: str = "api") -> bool:
        """
        Load configuration from a dictionary.

        Args:
            config: Configuration dictionary
            source: Source identifier

        Returns:
            True if loaded successfully
        """
        # Validate
        errors = self._validator.validate(config)
        if errors:
            logger.error(f"Configuration validation failed: {errors}")
            return False

        with self._lock:
            old_config = deepcopy(self._config)
            changes = self._detect_changes(old_config, config)

            # Calculate checksum
            checksum = hashlib.md5(yaml.dump(config).encode()).hexdigest()

            self._config = deepcopy(config)

            # Save to history
            self._save_version(config, checksum, source, changes)

            # Notify subscribers
            if changes:
                self._notify_changes(old_config, config, changes)

        logger.info(
            f"Configuration loaded from {source} (version {self._version_counter})"
        )
        return True

    def update(self, path: str, value: Any, source: str = "api") -> bool:
        """
        Update a specific configuration value.

        Args:
            path: Dot-notation path to update
            value: New value
            source: Source of update

        Returns:
            True if updated successfully
        """
        with self._lock:
            # Create a copy with the update
            new_config = deepcopy(self._config)
            self._set_path(new_config, path, value)

            # Validate
            errors = self._validator.validate(new_config)
            if errors:
                logger.error(f"Update validation failed: {errors}")
                return False

            old_value = self.get(path)
            old_config = deepcopy(self._config)

            self._config = new_config

            # Create change record
            change = ConfigurationChange(
                path=path, old_value=old_value, new_value=value, changed_at=utc_now()
            )

            # Calculate checksum
            checksum = hashlib.md5(yaml.dump(new_config).encode()).hexdigest()

            # Save to history
            self._save_version(new_config, checksum, source, [change])

            # Notify subscribers
            self._notify_changes(old_config, new_config, [change])

        logger.info(f"Configuration updated: {path} = {value}")
        return True

    def get(self, path: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            path: Dot-notation path (None for entire config)
            default: Default value if not found

        Returns:
            Configuration value
        """
        with self._lock:
            if path is None:
                return deepcopy(self._config)

            return self._get_path(self._config, path, default)

    def reload(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            True if reloaded successfully
        """
        if self._config_path:
            return self.load_from_file(self._config_path)
        return False

    def rollback(self, version: Optional[int] = None) -> bool:
        """
        Rollback to a previous configuration version.

        Args:
            version: Version to rollback to (None = previous)

        Returns:
            True if rollback successful
        """
        with self._lock:
            if not self._history:
                logger.warning("No configuration history for rollback")
                return False

            if version is None:
                # Rollback to previous version
                if len(self._history) < 2:
                    logger.warning("No previous version available")
                    return False
                target = self._history[-2]
            else:
                # Find specific version
                target = next((v for v in self._history if v.version == version), None)
                if not target:
                    logger.warning(f"Version {version} not found")
                    return False

            old_config = deepcopy(self._config)
            changes = self._detect_changes(old_config, target.config)

            self._config = deepcopy(target.config)

            # Save rollback as new version
            self._save_version(
                target.config,
                target.checksum,
                f"rollback_from_v{self._version_counter}",
                changes,
            )

            # Notify
            self._notify_changes(old_config, target.config, changes)

        logger.info(f"Configuration rolled back to version {target.version}")
        return True

    def subscribe(self, subscriber: ConfigurationSubscriber) -> None:
        """Subscribe to configuration changes"""
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: ConfigurationSubscriber) -> bool:
        """Unsubscribe from configuration changes"""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
            return True
        return False

    def get_history(self) -> List[Dict[str, Any]]:
        """Get configuration history"""
        return [v.to_dict() for v in self._history]

    def get_current_version(self) -> int:
        """Get current configuration version number"""
        return self._version_counter

    def export_to_yaml(self, path: Optional[str] = None) -> str:
        """
        Export current configuration to YAML.

        Args:
            path: Optional file path to write to

        Returns:
            YAML string
        """
        yaml_str = yaml.dump(
            self._config, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

        if path:
            with open(path, "w") as f:
                f.write(yaml_str)
            logger.info(f"Configuration exported to {path}")

        return yaml_str

    def start_auto_reload(self) -> None:
        """Start automatic configuration file watching"""
        if self._running:
            return

        self._running = True
        self._watch_thread = threading.Thread(
            target=self._watch_file, daemon=True, name="config-watcher"
        )
        self._watch_thread.start()
        logger.info("Configuration auto-reload started")

    def stop_auto_reload(self) -> None:
        """Stop automatic configuration file watching"""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
        logger.info("Configuration auto-reload stopped")

    def add_validation_rule(self, path: str, validator: Callable[[Any], bool]) -> None:
        """Add a custom validation rule"""
        self._validator.add_rule(path, validator)

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _watch_file(self) -> None:
        """File watching thread"""
        last_mtime = None

        while self._running:
            try:
                if self._config_path and os.path.exists(self._config_path):
                    # First check modification time - much faster than reading file
                    current_mtime = os.path.getmtime(self._config_path)

                    if last_mtime is None:
                        last_mtime = current_mtime
                    elif current_mtime != last_mtime:
                        # File was modified, now read and check content
                        with open(self._config_path, "r") as f:
                            content = f.read()

                        checksum = hashlib.md5(content.encode()).hexdigest()
                        if checksum != self._last_checksum:
                            logger.info("Configuration file changed, reloading...")
                            self.load_from_file(self._config_path)

                        last_mtime = current_mtime

            except Exception as e:
                logger.error(f"Error watching configuration file: {e}")

            time.sleep(self._reload_interval)

    def _save_version(
        self,
        config: Dict[str, Any],
        checksum: str,
        source: str,
        changes: List[ConfigurationChange],
    ) -> None:
        """Save a configuration version to history"""
        self._version_counter += 1
        version = ConfigurationVersion(
            version=self._version_counter,
            config=deepcopy(config),
            checksum=checksum,
            created_at=utc_now(),
            source=source,
            changes=changes,
        )

        self._history.append(version)

        # Trim history if needed
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def _detect_changes(
        self, old: Dict[str, Any], new: Dict[str, Any], prefix: str = ""
    ) -> List[ConfigurationChange]:
        """Detect changes between two configurations"""
        changes = []
        now = utc_now()

        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            path = f"{prefix}.{key}" if prefix else key
            old_val = old.get(key)
            new_val = new.get(key)

            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # Recurse into nested dicts
                    changes.extend(self._detect_changes(old_val, new_val, path))
                else:
                    changes.append(
                        ConfigurationChange(
                            path=path,
                            old_value=old_val,
                            new_value=new_val,
                            changed_at=now,
                        )
                    )

        return changes

    def _get_path(self, config: Dict, path: str, default: Any = None) -> Any:
        """Get value at dot-notation path"""
        parts = path.split(".")
        current = config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def _set_path(self, config: Dict, path: str, value: Any) -> None:
        """Set value at dot-notation path"""
        parts = path.split(".")
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def _notify_changes(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        changes: List[ConfigurationChange],
    ) -> None:
        """Notify subscribers of changes"""
        for subscriber in self._subscribers:
            try:
                subscriber.on_config_changed(old_config, new_config, changes)
            except Exception as e:
                logger.error(f"Subscriber notification error: {e}")

    def _notify_reload(self, config: Dict[str, Any]) -> None:
        """Notify subscribers of reload"""
        for subscriber in self._subscribers:
            try:
                subscriber.on_config_reloaded(config)
            except Exception as e:
                logger.error(f"Subscriber reload notification error: {e}")


# =============================================================================
# Global Instance
# =============================================================================

_config_manager: Optional[DynamicConfigurationManager] = None


def get_config_manager(
    config_path: Optional[str] = None,
) -> DynamicConfigurationManager:
    """Get or create the global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = DynamicConfigurationManager(config_path)
    return _config_manager


def get_config(path: Optional[str] = None, default: Any = None) -> Any:
    """Convenience function to get configuration value"""
    return get_config_manager().get(path, default)


def update_config(path: str, value: Any) -> bool:
    """Convenience function to update configuration"""
    return get_config_manager().update(path, value)
