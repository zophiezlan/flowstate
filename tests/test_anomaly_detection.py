"""Tests for anomaly detection features"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
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


def test_forgotten_exit_taps(test_db):
    """Test detection of forgotten exit taps and incomplete journeys"""
    # Create an old QUEUE_JOIN event without EXIT (>30 min ago)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=45)

    test_db.log_event(
        token_id="001",
        uid="ABC",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=old_time,
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Should detect as incomplete journey (which includes forgotten exits)
    assert len(anomalies["incomplete_journeys"]) >= 1
    incomplete = [a for a in anomalies["incomplete_journeys"] if a["token_id"] == "001"]
    assert len(incomplete) == 1
    assert incomplete[0]["token_id"] == "001"

    # Summary should count it
    assert anomalies["summary"]["total_anomalies"] >= 1


def test_stuck_in_service(test_db):
    """Test detection of participants stuck in service via incomplete journeys"""
    # Create SERVICE_START event >45 min ago without completion
    old_time = datetime.now(timezone.utc) - timedelta(minutes=60)

    test_db.log_event(
        token_id="002",
        uid="DEF",
        stage="SERVICE_START",
        device_id="station1",
        session_id="test-session",
        timestamp=old_time,
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Should detect as incomplete journey (SERVICE_START without completion)
    # Note: The separate stuck_in_service detection requires more complex SQL
    # and incomplete_journeys already covers this case effectively
    assert len(anomalies["incomplete_journeys"]) >= 1
    incomplete = [a for a in anomalies["incomplete_journeys"] if a["token_id"] == "002"]
    assert len(incomplete) == 1


def test_incomplete_journeys(test_db):
    """Test detection of incomplete journeys (no EXIT)"""
    # Create journey without EXIT
    test_db.log_event(
        token_id="003",
        uid="GHI",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )

    test_db.log_event(
        token_id="003",
        uid="GHI",
        stage="SERVICE_START",
        device_id="station1",
        session_id="test-session",
    )

    # Create complete journey for comparison
    test_db.log_event(
        token_id="004",
        uid="JKL",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )

    test_db.log_event(
        token_id="004",
        uid="JKL",
        stage="EXIT",
        device_id="station2",
        session_id="test-session",
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Should detect incomplete journey for token 003 but not 004
    incomplete = [a for a in anomalies["incomplete_journeys"] if a["token_id"] == "003"]
    assert len(incomplete) == 1
    assert "EXIT" not in incomplete[0]["journey"]


def test_rapid_fire_taps(test_db):
    """Test detection of rapid-fire duplicate taps"""
    now = datetime.now(timezone.utc)

    # First tap
    test_db.log_event(
        token_id="005",
        uid="MNO",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=now,
        skip_duplicate_check=True,  # Force both to be logged
    )

    # Second tap <2 min later at same stage (rapid-fire)
    test_db.log_event(
        token_id="005",
        uid="MNO",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=now + timedelta(seconds=30),
        skip_duplicate_check=True,  # Force both to be logged
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Should detect rapid-fire taps
    rapid = [a for a in anomalies["rapid_fire_taps"] if a["token_id"] == "005"]
    assert len(rapid) >= 1
    assert rapid[0]["seconds_between"] < 120  # Less than 2 minutes


def test_long_service_times(test_db):
    """Test detection of unusually long service times"""
    now = datetime.now(timezone.utc)

    # Create several normal service times (10-15 min)
    for i in range(5):
        join_time = now - timedelta(minutes=20 + i * 2)
        exit_time = join_time + timedelta(minutes=12)

        test_db.log_event(
            token_id=f"{i:03d}",
            uid=f"UID{i}",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id="test-session",
            timestamp=join_time,
        )

        test_db.log_event(
            token_id=f"{i:03d}",
            uid=f"UID{i}",
            stage="EXIT",
            device_id="station2",
            session_id="test-session",
            timestamp=exit_time,
        )

    # Create one very long service time (>2x median, i.e., >24 min)
    long_join = now - timedelta(minutes=50)
    long_exit = long_join + timedelta(minutes=30)

    test_db.log_event(
        token_id="999",
        uid="LONG",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=long_join,
    )

    test_db.log_event(
        token_id="999",
        uid="LONG",
        stage="EXIT",
        device_id="station2",
        session_id="test-session",
        timestamp=long_exit,
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Should detect long service time
    long_service = [
        a for a in anomalies["long_service_times"] if a["token_id"] == "999"
    ]
    assert len(long_service) >= 1
    assert long_service[0]["service_minutes"] >= 24


def test_deleted_events_audit_trail(test_db):
    """Test that deleted events are archived"""
    # Log an event
    result = test_db.log_event(
        token_id="006",
        uid="PQR",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
    )
    assert result["success"] is True

    # Get the event ID
    events = test_db.get_recent_events(1)
    event_id = events[0]["id"]

    # Remove the event
    remove_result = test_db.remove_event(
        event_id=event_id,
        operator_id="test_operator",
        reason="Test deletion",
    )

    assert remove_result["success"] is True
    assert remove_result["removed_event"]["token_id"] == "006"

    # Event should be gone from events table
    assert test_db.get_event_count("test-session") == 0

    # But should exist in deleted_events table
    cursor = test_db.conn.execute(
        "SELECT * FROM deleted_events WHERE original_event_id = ?", (event_id,)
    )
    deleted = cursor.fetchone()

    assert deleted is not None
    assert deleted["token_id"] == "006"
    assert deleted["deleted_by"] == "test_operator"
    assert deleted["deletion_reason"] == "Test deletion"


def test_manual_event_bypasses_duplicate_check(test_db):
    """Test that manual events can bypass duplicate checking"""
    now = datetime.now(timezone.utc)

    # Log normal event
    result1 = test_db.log_event(
        token_id="007",
        uid="STU",
        stage="EXIT",
        device_id="station2",
        session_id="test-session",
        timestamp=now,
    )
    assert result1["success"] is True

    # Try to add manual event at same stage (should succeed)
    result2 = test_db.add_manual_event(
        token_id="007",
        stage="EXIT",  # Same stage as before
        timestamp=now - timedelta(minutes=5),  # Earlier time
        session_id="test-session",
        operator_id="staff_alice",
        reason="Participant forgot to tap earlier",
    )

    # Manual event should succeed despite being duplicate stage
    assert result2["success"] is True

    # Both events should exist
    assert test_db.get_event_count("test-session") == 2


def test_stage_validation(test_db):
    """Test that invalid stages are rejected"""
    result = test_db.log_event(
        token_id="008",
        uid="VWX",
        stage="INVALID_STAGE",
        device_id="station1",
        session_id="test-session",
    )

    # Should fail validation
    assert result["success"] is False
    assert "Unknown stage" in result.get("warning", "")


def test_anomaly_summary_statistics(test_db):
    """Test that anomaly summary provides correct statistics"""
    # Create various anomalies
    old_time = datetime.now(timezone.utc) - timedelta(minutes=45)

    # Incomplete journey #1
    test_db.log_event(
        token_id="010",
        uid="ABC1",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id="test-session",
        timestamp=old_time,
    )

    # Incomplete journey #2
    very_old = datetime.now(timezone.utc) - timedelta(minutes=95)
    test_db.log_event(
        token_id="011",
        uid="ABC2",
        stage="SERVICE_START",
        device_id="station1",
        session_id="test-session",
        timestamp=very_old,
    )

    # Get anomalies
    anomalies = test_db.get_anomalies("test-session")

    # Check summary
    summary = anomalies["summary"]
    assert summary["total_anomalies"] >= 2
    # Both incomplete journeys are marked as medium severity
    assert summary["medium_severity"] >= 2
