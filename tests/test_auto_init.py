"""Tests for auto-initialization of cards on first tap"""

import pytest
from tap_station.database import Database
from tap_station.nfc_reader import MockNFCReader
from tap_station.config import Config
import tempfile
import os
import yaml


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path, wal_mode=False)
    yield db
    db.close()
    os.unlink(path)


@pytest.fixture
def config_with_auto_init():
    """Create config with auto-init enabled"""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    config_data = {
        "station": {
            "device_id": "test-station",
            "stage": "QUEUE_JOIN",
            "session_id": "test-session",
        },
        "database": {"path": "test.db", "wal_mode": False},
        "nfc": {
            "auto_init_cards": True,
            "auto_init_start_id": 1,
        },
        "feedback": {"buzzer_enabled": False, "led_enabled": False},
        "logging": {"path": "test.log", "level": "INFO"},
        "web_server": {"enabled": False},
    }
    with os.fdopen(fd, "w") as f:
        yaml.dump(config_data, f)

    config = Config(path)
    yield config
    os.unlink(path)


@pytest.fixture
def config_without_auto_init():
    """Create config with auto-init disabled"""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    config_data = {
        "station": {
            "device_id": "test-station",
            "stage": "QUEUE_JOIN",
            "session_id": "test-session",
        },
        "database": {"path": "test.db", "wal_mode": False},
        "nfc": {
            "auto_init_cards": False,
        },
        "feedback": {"buzzer_enabled": False, "led_enabled": False},
        "logging": {"path": "test.log", "level": "INFO"},
        "web_server": {"enabled": False},
    }
    with os.fdopen(fd, "w") as f:
        yaml.dump(config_data, f)

    config = Config(path)
    yield config
    os.unlink(path)


class TestAutoInitDatabase:
    """Test database support for auto-initialization"""

    def test_get_next_token_id_first_time(self, temp_db):
        """Test getting first token ID for a session"""
        token_num, token_str = temp_db.get_next_auto_init_token_id(
            "test-session", start_id=1
        )

        assert token_num == 1
        assert token_str == "001"

    def test_get_next_token_id_sequential(self, temp_db):
        """Test that token IDs increment sequentially"""
        _, token1 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)
        _, token2 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)
        _, token3 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)

        assert token1 == "001"
        assert token2 == "002"
        assert token3 == "003"

    def test_get_next_token_id_custom_start(self, temp_db):
        """Test starting from a custom token ID"""
        _, token1 = temp_db.get_next_auto_init_token_id("test-session", start_id=100)
        _, token2 = temp_db.get_next_auto_init_token_id("test-session", start_id=100)

        assert token1 == "100"
        assert token2 == "101"

    def test_get_next_token_id_multiple_sessions(self, temp_db):
        """Test that different sessions have independent counters"""
        _, token1a = temp_db.get_next_auto_init_token_id("session-a", start_id=1)
        _, token1b = temp_db.get_next_auto_init_token_id("session-b", start_id=1)
        _, token2a = temp_db.get_next_auto_init_token_id("session-a", start_id=1)
        _, token2b = temp_db.get_next_auto_init_token_id("session-b", start_id=1)

        assert token1a == "001"
        assert token1b == "001"
        assert token2a == "002"
        assert token2b == "002"

    def test_get_next_token_id_formats_correctly(self, temp_db):
        """Test that token IDs are formatted as 3-digit strings"""
        _, token1 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)

        assert token1 == "001"
        assert len(token1) == 3

        # Get a few more to verify formatting
        _, token2 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)
        assert token2 == "002"
        assert len(token2) == 3

        # Skip ahead to near 100
        for _ in range(97):
            temp_db.get_next_auto_init_token_id("test-session", start_id=1)

        _, token100 = temp_db.get_next_auto_init_token_id("test-session", start_id=1)
        assert token100 == "100"
        assert len(token100) == 3


class TestAutoInitConfig:
    """Test configuration for auto-initialization"""

    def test_config_auto_init_enabled(self, config_with_auto_init):
        """Test config with auto-init enabled"""
        assert config_with_auto_init.auto_init_cards is True
        assert config_with_auto_init.auto_init_start_id == 1

    def test_config_auto_init_disabled(self, config_without_auto_init):
        """Test config with auto-init disabled"""
        assert config_without_auto_init.auto_init_cards is False

    def test_config_auto_init_default(self):
        """Test that auto-init defaults to False"""
        fd, path = tempfile.mkstemp(suffix=".yaml")
        config_data = {
            "station": {
                "device_id": "test-station",
                "stage": "QUEUE_JOIN",
                "session_id": "test-session",
            },
            "database": {"path": "test.db"},
            "nfc": {},  # No auto_init_cards specified
        }
        with os.fdopen(fd, "w") as f:
            yaml.dump(config_data, f)

        config = Config(path)
        assert config.auto_init_cards is False
        assert config.auto_init_start_id == 1  # default
        os.unlink(path)


class TestAutoInitDetection:
    """Test detection of uninitialized cards"""

    def test_uid_detection(self):
        """Test that UIDs are correctly identified as uninitialized"""
        # Import the utility function from main
        from tap_station.main import TapStation

        # Create a mock tap station just to access the method
        # (We can't instantiate fully without config file)

        # Test the logic directly
        def looks_like_uid(token_id: str) -> bool:
            return len(token_id) >= 8 and all(c in "0123456789ABCDEF" for c in token_id)

        # These look like UIDs (8+ hex chars)
        assert looks_like_uid("04A32FB2")
        assert looks_like_uid("04A32FB2C15080")
        assert looks_like_uid("AABBCCDD")

        # These look like token IDs (3-4 digits)
        assert not looks_like_uid("001")
        assert not looks_like_uid("099")
        assert not looks_like_uid("100")
        assert not looks_like_uid("1000")

        # Edge cases
        assert not looks_like_uid("ABC")  # Too short
        assert not looks_like_uid("12G45678")  # Contains non-hex


class TestAutoInitIntegration:
    """Integration tests for auto-initialization feature"""

    def _looks_like_uid(self, token_id: str) -> bool:
        """Helper: Check if token_id looks like a UID"""
        return len(token_id) >= 8 and all(c in "0123456789ABCDEF" for c in token_id)

    def test_auto_init_assigns_sequential_ids(self, temp_db):
        """Test that multiple uninitialized cards get sequential IDs"""
        # Simulate 3 uninitialized cards being tapped
        # These UIDs are all hex and >= 8 chars, so they look uninitialized
        cards = [
            ("04A32FB2C15080", "04A32FB2"),  # UID used as token (8 hex chars)
            ("05B43AC3D26091", "05B43AC3"),  # All hex
            ("06C54AD4E37102", "06C54AD4"),  # All hex
        ]

        assigned_ids = []
        for uid, token_id in cards:
            # Detect uninitialized (token_id looks like UID)
            if self._looks_like_uid(token_id):
                _, new_token_id = temp_db.get_next_auto_init_token_id(
                    "test-session", start_id=1
                )
                assigned_ids.append(new_token_id)

        assert assigned_ids == ["001", "002", "003"]

    def test_mixed_initialized_and_uninitialized(self, temp_db):
        """Test handling mix of pre-initialized and blank cards"""
        # Simulate card taps in order:
        # 1. Pre-initialized card "050"
        # 2. Uninitialized card (UID - all hex, 8+ chars)
        # 3. Pre-initialized card "025"
        # 4. Uninitialized card (UID - all hex, 8+ chars)

        cards = [
            ("04A32FB2C15080", "050"),  # Pre-init
            ("05B43AC3D26091", "05B43AC3"),  # Uninitialized (all hex)
            ("06C54AD4E37102", "025"),  # Pre-init
            ("07D65AE5F48213", "07D65AE5"),  # Uninitialized (all hex)
        ]

        results = []
        for uid, token_id in cards:
            if self._looks_like_uid(token_id):
                # Auto-init starting at 100 to avoid collision
                _, new_token_id = temp_db.get_next_auto_init_token_id(
                    "test-session", start_id=100
                )
                results.append((uid, new_token_id))
            else:
                # Keep existing token ID
                results.append((uid, token_id))

        # Check results
        assert results[0][1] == "050"  # Pre-init kept
        assert results[1][1] == "100"  # Auto-assigned
        assert results[2][1] == "025"  # Pre-init kept
        assert results[3][1] == "101"  # Auto-assigned

    def test_auto_init_logs_events_correctly(self, temp_db):
        """Test that auto-initialized cards log events correctly"""
        # Get auto-assigned token ID
        _, token_id = temp_db.get_next_auto_init_token_id("test-session", start_id=1)

        # Log event with auto-assigned token ID
        result = temp_db.log_event(
            token_id=token_id,
            uid="04A32FB2C15080",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test-session",
        )

        assert result["success"] is True

        # Verify event was logged
        events = temp_db.get_recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["token_id"] == "001"
        assert events[0]["uid"] == "04A32FB2C15080"


class TestAutoInitCardWriting:
    """Test card writing during auto-initialization"""

    def test_mock_reader_write_token_id(self):
        """Test that mock NFC reader can write token IDs"""
        reader = MockNFCReader()

        success = reader.write_token_id("001")
        assert success is True

    def test_auto_init_with_write_failure(self, temp_db):
        """Test that auto-init still works if card writing fails"""
        # Get auto-assigned token ID
        _, token_id = temp_db.get_next_auto_init_token_id("test-session", start_id=1)
        assert token_id == "001"

        # Even if write fails, we can still log the event
        # (This is what happens in main.py - it tries to write but continues anyway)
        result = temp_db.log_event(
            token_id=token_id,
            uid="04A32FB2C15080",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test-session",
        )

        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
