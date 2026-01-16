"""Tests for database operations"""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from tap_station.database import Database


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db = Database(path, wal_mode=True)
    yield db

    db.close()
    os.unlink(path)

    # Clean up WAL files
    for ext in ["-wal", "-shm"]:
        wal_path = path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


def test_database_creation(test_db):
    """Test database table creation"""
    # Check that events table exists
    cursor = test_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result["name"] == "events"


def test_log_event(test_db):
    """Test logging an event"""
    success = test_db.log_event(
        token_id="001",
        uid="1234567890ABCDEF",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )

    assert success is True

    # Verify event was logged
    count = test_db.get_event_count("test-session")
    assert count == 1


def test_duplicate_prevention(test_db):
    """Test that duplicate events are prevented"""
    # Log first event
    success1 = test_db.log_event(
        token_id="001",
        uid="1234567890ABCDEF",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )
    assert success1 is True

    # Try to log duplicate (same token, same stage, same session)
    success2 = test_db.log_event(
        token_id="001",
        uid="1234567890ABCDEF",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )
    assert success2 is False

    # Only one event should exist
    count = test_db.get_event_count("test-session")
    assert count == 1


def test_different_stages_allowed(test_db):
    """Test that same token can log at different stages"""
    # Queue join
    success1 = test_db.log_event(
        token_id="001",
        uid="1234567890ABCDEF",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )
    assert success1 is True

    # Exit (different stage)
    success2 = test_db.log_event(
        token_id="001",
        uid="1234567890ABCDEF",
        stage="EXIT",
        device_id="station2",
        session_id="test-session",
    )
    assert success2 is True

    # Both events should exist
    count = test_db.get_event_count("test-session")
    assert count == 2


def test_session_isolation(test_db):
    """Test that sessions are isolated"""
    # Log in session 1
    test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="session1",
    )

    # Log same token/stage in session 2 (should succeed)
    success = test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="session2",
    )
    assert success is True

    # Each session should have 1 event
    assert test_db.get_event_count("session1") == 1
    assert test_db.get_event_count("session2") == 1


def test_get_recent_events(test_db):
    """Test retrieving recent events"""
    # Log multiple events
    for i in range(5):
        test_db.log_event(
            token_id=f"{i:03d}",
            uid=f"UID{i}",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test-session",
        )

    # Get recent events
    recent = test_db.get_recent_events(limit=3)

    assert len(recent) == 3
    # Should be in reverse chronological order
    assert recent[0]["token_id"] == "004"
    assert recent[1]["token_id"] == "003"
    assert recent[2]["token_id"] == "002"


def test_export_to_csv(test_db):
    """Test CSV export"""
    # Log some events
    test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )
    test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="EXIT",
        device_id="station2",
        session_id="test-session",
    )

    # Export to CSV
    fd, csv_path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)

    try:
        row_count = test_db.export_to_csv(csv_path, session_id="test-session")
        assert row_count == 2

        # Verify CSV content
        with open(csv_path, "r") as f:
            lines = f.readlines()

        # Should have header + 2 data rows
        assert len(lines) == 3
        assert "token_id" in lines[0]
        assert "001" in lines[1]
        assert "001" in lines[2]

    finally:
        os.unlink(csv_path)


def test_custom_timestamp(test_db):
    """Test logging with custom timestamp"""
    custom_time = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

    test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=custom_time,
    )

    # Verify timestamp
    recent = test_db.get_recent_events(1)
    assert len(recent) == 1
    assert custom_time.isoformat() in recent[0]["timestamp"]
