"""
Tests for the Dynamic Configuration System

Tests cover:
- Configuration loading
- Hot reload
- Change detection
- Rollback
- Subscriber notifications
"""

import pytest
import tempfile
import os
from datetime import datetime

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.dynamic_config import (
    DynamicConfigurationManager,
    ConfigurationValidator,
    ConfigurationSubscriber,
    ConfigurationChange,
    ConfigurationVersion,
    get_config_manager,
    get_config,
    update_config,
)


@pytest.fixture
def manager():
    """Create a configuration manager"""
    return DynamicConfigurationManager()


@pytest.fixture
def config_file():
    """Create a temporary config file"""
    content = """
service:
  name: Test Service
  type: festival

capacity:
  people_per_hour: 12
  avg_service_minutes: 5

alerts:
  queue:
    warning_threshold: 10
    critical_threshold: 20
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name

    os.unlink(f.name)


class TestConfigurationValidator:
    """Tests for ConfigurationValidator"""

    def test_validate_valid_config(self):
        """Test validation passes for valid config"""
        validator = ConfigurationValidator()
        config = {"capacity": {"people_per_hour": 12, "avg_service_minutes": 5}}
        errors = validator.validate(config)
        assert len(errors) == 0

    def test_validate_invalid_value(self):
        """Test validation fails for invalid value"""
        validator = ConfigurationValidator()
        config = {"capacity": {"people_per_hour": 500}}  # Too high
        errors = validator.validate(config)
        assert len(errors) > 0

    def test_add_custom_rule(self):
        """Test adding custom validation rule"""
        validator = ConfigurationValidator()
        validator.add_rule(
            "custom.setting", lambda v: isinstance(v, str) and len(v) > 0
        )

        config = {"custom": {"setting": ""}}
        errors = validator.validate(config)
        assert len(errors) > 0

    def test_required_keys(self):
        """Test required key validation"""
        validator = ConfigurationValidator()
        validator.add_required("service.name")

        config = {"service": {}}
        errors = validator.validate(config)
        assert any("required" in e.lower() for e in errors)


class TestDynamicConfigurationManager:
    """Tests for DynamicConfigurationManager"""

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert manager._config == {}
        assert manager._version_counter == 0

    def test_load_from_file(self, manager, config_file):
        """Test loading config from file"""
        result = manager.load_from_file(config_file)
        assert result is True
        assert manager.get("service.name") == "Test Service"

    def test_load_from_dict(self, manager):
        """Test loading config from dictionary"""
        config = {
            "service": {"name": "Dict Service"},
            "capacity": {"people_per_hour": 15},
        }
        result = manager.load_from_dict(config)
        assert result is True
        assert manager.get("service.name") == "Dict Service"

    def test_get_entire_config(self, manager):
        """Test getting entire configuration"""
        manager.load_from_dict({"test": "value"})
        config = manager.get()
        assert isinstance(config, dict)
        assert "test" in config

    def test_get_with_path(self, manager):
        """Test getting config value by path"""
        manager.load_from_dict({"level1": {"level2": {"value": 42}}})
        assert manager.get("level1.level2.value") == 42

    def test_get_with_default(self, manager):
        """Test getting non-existent path returns default"""
        manager.load_from_dict({})
        assert manager.get("nonexistent.path", "default") == "default"

    def test_update_config(self, manager):
        """Test updating a config value"""
        manager.load_from_dict({"service": {"name": "Original"}})
        result = manager.update("service.name", "Updated")
        assert result is True
        assert manager.get("service.name") == "Updated"

    def test_update_creates_path(self, manager):
        """Test update creates nested path"""
        manager.load_from_dict({})
        manager.update("new.nested.value", 123)
        assert manager.get("new.nested.value") == 123

    def test_version_history(self, manager):
        """Test configuration versioning"""
        manager.load_from_dict({"v": 1})
        manager.load_from_dict({"v": 2})

        history = manager.get_history()
        assert len(history) >= 2

    def test_rollback(self, manager):
        """Test configuration rollback"""
        manager.load_from_dict({"value": "first"})
        manager.load_from_dict({"value": "second"})

        result = manager.rollback()
        assert result is True
        assert manager.get("value") == "first"

    def test_rollback_to_specific_version(self, manager):
        """Test rollback to specific version"""
        manager.load_from_dict({"v": 1})
        v1 = manager.get_current_version()
        manager.load_from_dict({"v": 2})
        manager.load_from_dict({"v": 3})

        result = manager.rollback(version=v1)
        assert result is True
        assert manager.get("v") == 1

    def test_export_to_yaml(self, manager):
        """Test YAML export"""
        manager.load_from_dict({"service": {"name": "Export Test"}})
        yaml_str = manager.export_to_yaml()
        assert "Export Test" in yaml_str

    def test_export_to_file(self, manager):
        """Test YAML export to file"""
        manager.load_from_dict({"test": "value"})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            path = f.name

        try:
            manager.export_to_yaml(path)
            with open(path, "r") as f:
                content = f.read()
            assert "test" in content
        finally:
            os.unlink(path)


class TestConfigurationSubscriber:
    """Tests for configuration change subscribers"""

    def test_subscriber_notification(self, manager):
        """Test subscribers receive change notifications"""
        changes_received = []

        class TestSubscriber(ConfigurationSubscriber):
            def on_config_changed(self, old, new, changes):
                changes_received.extend(changes)

        subscriber = TestSubscriber()
        manager.subscribe(subscriber)

        manager.load_from_dict({"v": 1})
        manager.update("v", 2)

        assert len(changes_received) > 0

    def test_subscriber_reload_notification(self, manager, config_file):
        """Test subscribers receive reload notifications"""
        reloads_received = []

        class TestSubscriber(ConfigurationSubscriber):
            def on_config_reloaded(self, config):
                reloads_received.append(config)

        subscriber = TestSubscriber()
        manager.subscribe(subscriber)

        manager.load_from_file(config_file)
        assert len(reloads_received) == 1

    def test_unsubscribe(self, manager):
        """Test unsubscribing"""

        class TestSubscriber(ConfigurationSubscriber):
            pass

        subscriber = TestSubscriber()
        manager.subscribe(subscriber)
        result = manager.unsubscribe(subscriber)
        assert result is True


class TestConfigurationChange:
    """Tests for ConfigurationChange dataclass"""

    def test_to_dict(self):
        """Test change serialization"""
        change = ConfigurationChange(
            path="service.name",
            old_value="Old",
            new_value="New",
            changed_at=datetime.utcnow(),
        )
        d = change.to_dict()

        assert d["path"] == "service.name"
        assert "Old" in d["old_value"]
        assert "New" in d["new_value"]


class TestConfigurationVersion:
    """Tests for ConfigurationVersion dataclass"""

    def test_to_dict(self):
        """Test version serialization"""
        version = ConfigurationVersion(
            version=1,
            config={"test": "value"},
            checksum="abc123",
            created_at=datetime.utcnow(),
            source="test",
        )
        d = version.to_dict()

        assert d["version"] == 1
        assert d["checksum"] == "abc123"
        assert d["source"] == "test"


class TestChangeDetection:
    """Tests for configuration change detection"""

    def test_detect_simple_change(self, manager):
        """Test detecting simple value change"""
        manager.load_from_dict({"value": 1})
        manager.load_from_dict({"value": 2})

        history = manager.get_history()
        last_version = history[-1]
        assert last_version["change_count"] == 1

    def test_detect_nested_change(self, manager):
        """Test detecting nested value change"""
        manager.load_from_dict({"a": {"b": {"c": 1}}})
        manager.load_from_dict({"a": {"b": {"c": 2}}})

        history = manager.get_history()
        last_version = history[-1]
        assert last_version["change_count"] >= 1

    def test_detect_addition(self, manager):
        """Test detecting new key addition"""
        manager.load_from_dict({"existing": 1})
        manager.load_from_dict({"existing": 1, "new": 2})

        history = manager.get_history()
        last_version = history[-1]
        assert last_version["change_count"] >= 1


class TestAutoReload:
    """Tests for auto-reload functionality"""

    def test_start_stop_auto_reload(self, config_file):
        """Test starting and stopping auto-reload"""
        manager = DynamicConfigurationManager(
            config_path=config_file, auto_reload=False
        )

        manager.start_auto_reload()
        assert manager._running is True

        manager.stop_auto_reload()
        assert manager._running is False

    def test_reload_method(self, manager, config_file):
        """Test manual reload"""
        manager.load_from_file(config_file)
        result = manager.reload()
        assert result is True


class TestValidationOnLoad:
    """Tests for validation during loading"""

    def test_invalid_config_rejected(self, manager):
        """Test invalid config is rejected"""
        manager.add_validation_rule("must_exist", lambda v: v == "required_value")

        config = {"must_exist": "wrong_value"}
        result = manager.load_from_dict(config)
        assert result is False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_config_manager(self):
        """Test global manager retrieval"""
        module = sys.modules["tap_station.dynamic_config"]
        module._config_manager = None

        manager = get_config_manager()
        assert manager is not None

        manager2 = get_config_manager()
        assert manager is manager2

    def test_get_config_function(self):
        """Test get_config convenience function"""
        module = sys.modules["tap_station.dynamic_config"]
        module._config_manager = None

        manager = get_config_manager()
        manager.load_from_dict({"test": "value"})

        assert get_config("test") == "value"

    def test_update_config_function(self):
        """Test update_config convenience function"""
        module = sys.modules["tap_station.dynamic_config"]
        module._config_manager = None

        manager = get_config_manager()
        manager.load_from_dict({"test": "old"})

        result = update_config("test", "new")
        assert result is True
        assert get_config("test") == "new"
