"""Tests for substance return confirmation functionality"""

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


def test_substance_return_workflow(test_db):
    """Test full workflow with substance return stage"""
    token_id = "042"
    uid = "ABCD1234"
    session_id = "festival-2026"
    
    # Simulate full workflow: QUEUE_JOIN -> SERVICE_START -> SUBSTANCE_RETURNED -> EXIT
    now = datetime.now(timezone.utc)
    
    # Stage 1: Join queue
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id=session_id,
        timestamp=now,
    )
    assert success is True
    
    # Stage 2: Service starts (10 minutes later)
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SERVICE_START",
        device_id="station2",
        session_id=session_id,
        timestamp=now + timedelta(minutes=10),
    )
    assert success is True
    
    # Stage 3: Substance returned (8 minutes after service start)
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id=session_id,
        timestamp=now + timedelta(minutes=18),
    )
    assert success is True
    
    # Stage 4: Exit (1 minute after substance returned)
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="EXIT",
        device_id="station4",
        session_id=session_id,
        timestamp=now + timedelta(minutes=19),
    )
    assert success is True
    
    # Verify all events logged
    events = test_db.get_recent_events(limit=10)
    assert len(events) == 4
    
    # Verify stages in correct order
    stages = [event['stage'] for event in reversed(events)]
    assert stages == ["QUEUE_JOIN", "SERVICE_START", "SUBSTANCE_RETURNED", "EXIT"]


def test_substance_return_duplicate_prevention(test_db):
    """Test that duplicate substance return confirmations are prevented"""
    token_id = "067"
    uid = "EFGH5678"
    session_id = "festival-2026"
    
    # Log initial substance return
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id=session_id,
    )
    assert success is True
    
    # Attempt to log duplicate
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id=session_id,
    )
    assert success is False  # Should be rejected as duplicate


def test_multiple_participants_substance_return(test_db):
    """Test tracking substance return for multiple participants"""
    session_id = "festival-2026"
    now = datetime.now(timezone.utc)
    
    # Track 3 participants through substance return workflow
    participants = [
        {"token": "001", "uid": "UID001"},
        {"token": "002", "uid": "UID002"},
        {"token": "003", "uid": "UID003"},
    ]
    
    for p in participants:
        # Each participant: QUEUE_JOIN -> SERVICE_START -> SUBSTANCE_RETURNED -> EXIT
        test_db.log_event(
            token_id=p["token"],
            uid=p["uid"],
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id=session_id,
            timestamp=now,
        )
        
        test_db.log_event(
            token_id=p["token"],
            uid=p["uid"],
            stage="SERVICE_START",
            device_id="station2",
            session_id=session_id,
            timestamp=now + timedelta(minutes=5),
        )
        
        test_db.log_event(
            token_id=p["token"],
            uid=p["uid"],
            stage="SUBSTANCE_RETURNED",
            device_id="station3",
            session_id=session_id,
            timestamp=now + timedelta(minutes=12),
        )
        
        test_db.log_event(
            token_id=p["token"],
            uid=p["uid"],
            stage="EXIT",
            device_id="station4",
            session_id=session_id,
            timestamp=now + timedelta(minutes=13),
        )
    
    # Verify all events logged (4 stages × 3 participants = 12 events)
    events = test_db.get_recent_events(limit=20)
    assert len(events) == 12
    
    # Count SUBSTANCE_RETURNED events
    returned_count = len([e for e in events if e['stage'] == 'SUBSTANCE_RETURNED'])
    assert returned_count == 3


def test_unreturned_substance_detection(test_db):
    """Test detection of participants awaiting substance return"""
    session_id = "festival-2026"
    now = datetime.now(timezone.utc)
    
    # Participant 1: Complete workflow (substance returned)
    test_db.log_event(
        token_id="001",
        uid="UID001",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id=session_id,
        timestamp=now - timedelta(minutes=20),
    )
    test_db.log_event(
        token_id="001",
        uid="UID001",
        stage="SERVICE_START",
        device_id="station2",
        session_id=session_id,
        timestamp=now - timedelta(minutes=15),
    )
    test_db.log_event(
        token_id="001",
        uid="UID001",
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id=session_id,
        timestamp=now - timedelta(minutes=10),
    )
    test_db.log_event(
        token_id="001",
        uid="UID001",
        stage="EXIT",
        device_id="station4",
        session_id=session_id,
        timestamp=now - timedelta(minutes=9),
    )
    
    # Participant 2: Service completed but substance NOT returned yet
    test_db.log_event(
        token_id="002",
        uid="UID002",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id=session_id,
        timestamp=now - timedelta(minutes=18),
    )
    test_db.log_event(
        token_id="002",
        uid="UID002",
        stage="SERVICE_START",
        device_id="station2",
        session_id=session_id,
        timestamp=now - timedelta(minutes=8),
    )
    # No SUBSTANCE_RETURNED event for participant 2
    
    # Query to find participants awaiting substance return
    # (has SERVICE_START but no SUBSTANCE_RETURNED)
    cursor = test_db.conn.execute(
        """
        SELECT DISTINCT token_id
        FROM events
        WHERE session_id = ?
          AND stage = 'SERVICE_START'
          AND token_id NOT IN (
              SELECT token_id 
              FROM events 
              WHERE session_id = ? AND stage = 'SUBSTANCE_RETURNED'
          )
        """,
        (session_id, session_id),
    )
    
    unreturned = [row['token_id'] for row in cursor.fetchall()]
    assert len(unreturned) == 1
    assert "002" in unreturned
    assert "001" not in unreturned  # Participant 1 had substance returned


def test_substance_return_timing_metrics(test_db):
    """Test calculation of substance return timing metrics"""
    session_id = "festival-2026"
    now = datetime.now(timezone.utc)
    token_id = "042"
    
    # Log workflow with specific timing
    service_start_time = now + timedelta(minutes=10)
    return_time = now + timedelta(minutes=18)  # 8 minutes after service start
    
    test_db.log_event(
        token_id=token_id,
        uid="TEST_UID",
        stage="QUEUE_JOIN",
        device_id="station1",
        session_id=session_id,
        timestamp=now,
    )
    
    test_db.log_event(
        token_id=token_id,
        uid="TEST_UID",
        stage="SERVICE_START",
        device_id="station2",
        session_id=session_id,
        timestamp=service_start_time,
    )
    
    test_db.log_event(
        token_id=token_id,
        uid="TEST_UID",
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id=session_id,
        timestamp=return_time,
    )
    
    test_db.log_event(
        token_id=token_id,
        uid="TEST_UID",
        stage="EXIT",
        device_id="station4",
        session_id=session_id,
        timestamp=now + timedelta(minutes=19),
    )
    
    # Query to calculate time from service start to substance return
    cursor = test_db.conn.execute(
        """
        SELECT 
            s.token_id,
            s.timestamp as service_start,
            r.timestamp as substance_returned,
            (julianday(r.timestamp) - julianday(s.timestamp)) * 24 * 60 as minutes_to_return
        FROM events s
        JOIN events r ON s.token_id = r.token_id AND s.session_id = r.session_id
        WHERE s.session_id = ?
          AND s.stage = 'SERVICE_START'
          AND r.stage = 'SUBSTANCE_RETURNED'
          AND s.token_id = ?
        """,
        (session_id, token_id),
    )
    
    result = cursor.fetchone()
    assert result is not None
    assert result['token_id'] == token_id
    
    # Should be approximately 8 minutes
    minutes = result['minutes_to_return']
    assert 7.9 <= minutes <= 8.1  # Allow small floating point variance


def test_session_isolation_substance_return(test_db):
    """Test that substance return tracking is isolated per session"""
    token_id = "001"
    uid = "TEST_UID"
    
    # Session 1: Complete workflow with substance return
    test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SERVICE_START",
        device_id="station2",
        session_id="session-1",
    )
    test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id="session-1",
    )
    
    # Session 2: Same token can have another substance return
    success = test_db.log_event(
        token_id=token_id,
        uid=uid,
        stage="SUBSTANCE_RETURNED",
        device_id="station3",
        session_id="session-2",
    )
    assert success is True  # Should succeed because different session
    
    # Verify both events exist
    events = test_db.get_recent_events(limit=10)
    returned_events = [e for e in events if e['stage'] == 'SUBSTANCE_RETURNED']
    assert len(returned_events) == 2
    
    # Verify they're in different sessions
    sessions = {e['session_id'] for e in returned_events}
    assert sessions == {"session-1", "session-2"}
