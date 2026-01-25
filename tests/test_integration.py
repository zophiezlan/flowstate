"""Integration tests - full card lifecycle"""

import pytest
import tempfile
import os
import time
from tap_station.config import Config
from tap_station.database import Database
from tap_station.nfc_reader import MockNFCReader
from tap_station.feedback import FeedbackController


@pytest.fixture
def temp_config():
    """Create temporary config file"""
    config_content = """
station:
  device_id: "test-station"
  stage: "QUEUE_JOIN"
  session_id: "test-session"

database:
  path: "test-events.db"
  wal_mode: true

nfc:
  i2c_bus: 1
  address: 0x24
  timeout: 2
  retries: 3
  debounce_seconds: 0.5

feedback:
  buzzer_enabled: false
  led_enabled: false

logging:
  path: "test.log"
  level: "INFO"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        config_path = f.name

    yield config_path

    os.unlink(config_path)


@pytest.fixture
def temp_db():
    """Create temporary database"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    yield path

    # Cleanup
    for ext in ["", "-wal", "-shm"]:
        file_path = path + ext
        if os.path.exists(file_path):
            os.unlink(file_path)


def test_full_card_lifecycle(temp_config, temp_db):
    """Test complete card tap workflow"""
    # Load config
    config = Config(temp_config)

    # Override database path to use temp
    config._config["database"]["path"] = temp_db

    # Initialize components
    db = Database(temp_db, wal_mode=True)
    nfc = MockNFCReader(debounce_seconds=0.5)
    feedback = FeedbackController(buzzer_enabled=False, led_enabled=False)

    # Add mock cards
    nfc.add_mock_card("CARD001", "001")
    nfc.add_mock_card("CARD002", "002")

    try:
        # Simulate first card tap at queue join
        result = nfc.read_card()
        assert result is not None

        uid, token_id = result
        result = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="QUEUE_JOIN",
            device_id=config.device_id,
            session_id=config.session_id,
        )

        assert result["success"] is True

        # Simulate second card tap at queue join
        card_result = nfc.read_card()
        assert card_result is not None

        uid, token_id = card_result
        result = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="QUEUE_JOIN",
            device_id=config.device_id,
            session_id=config.session_id,
        )

        assert result["success"] is True

        # Now simulate same cards at exit
        # Reset mock index to first card
        nfc._mock_index = 0

        # Wait for debounce to expire
        time.sleep(0.6)

        card_result = nfc.read_card()
        uid, token_id = card_result

        result = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="EXIT",
            device_id="station2",
            session_id=config.session_id,
        )

        assert result["success"] is True

        # Verify database state
        total_events = db.get_event_count(config.session_id)
        assert total_events == 3  # 2 queue joins + 1 exit

        # Export to CSV
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)

        try:
            row_count = db.export_to_csv(csv_path, session_id=config.session_id)
            assert row_count == 3

            # Verify CSV content
            with open(csv_path, "r") as f:
                content = f.read()

            assert "QUEUE_JOIN" in content
            assert "EXIT" in content
            assert "001" in content
            assert "002" in content

        finally:
            os.unlink(csv_path)

    finally:
        db.close()
        feedback.cleanup()


def test_duplicate_detection(temp_db):
    """Test that duplicate taps are properly detected"""
    db = Database(temp_db, wal_mode=True)
    nfc = MockNFCReader(debounce_seconds=0.5)

    nfc.add_mock_card("CARD001", "001")

    try:
        # First tap
        result = nfc.read_card()
        uid, token_id = result

        result1 = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test",
        )
        assert result1["success"] is True

        # Wait for debounce
        time.sleep(0.6)

        # Second tap at same stage - detected as out-of-order
        # (QUEUE_JOIN -> QUEUE_JOIN is not a valid transition)
        # Event is still logged for data collection but flagged for review
        card_result = nfc.read_card()
        uid, token_id = card_result

        result2 = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test",
        )
        # Event is logged but flagged as out-of-order
        assert result2["success"] is True
        assert result2["out_of_order"] is True

        # Both events exist (logged for data collection, flagged for review)
        count = db.get_event_count("test")
        assert count == 2

    finally:
        db.close()


def test_multi_station_workflow(temp_db):
    """Test workflow across multiple stations"""
    db = Database(temp_db, wal_mode=True)

    # Simulate 10 cards going through both stations
    for i in range(10):
        token_id = f"{i:03d}"
        uid = f"CARD{i:03d}"

        # Queue join at station 1
        result = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="festival",
        )
        assert result["success"] is True

        # Exit at station 2
        result = db.log_event(
            token_id=token_id,
            uid=uid,
            stage="EXIT",
            device_id="station2",
            session_id="festival",
        )
        assert result["success"] is True

    try:
        # Verify all events logged
        total = db.get_event_count("festival")
        assert total == 20  # 10 cards × 2 stations

        # Export and verify
        fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)

        try:
            row_count = db.export_to_csv(csv_path, session_id="festival")
            assert row_count == 20

        finally:
            os.unlink(csv_path)

    finally:
        db.close()
