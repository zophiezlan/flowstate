"""Tests for v1 database operations."""

import os
import tempfile

import pytest

from tap_station.database import Database


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path, wal_mode=True)
    yield db
    db.close()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_database_creation_includes_correction_audit(test_db):
    tables = {
        row["name"]
        for row in test_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "events" in tables
    assert "correction_audit" in tables


def test_valid_v1_stage_progression(test_db):
    session_id = "s1"
    token_id = "001"
    uid = "uid-001"
    stages = [
        "ENTERED",
        "FIRST_CONTACT",
        "SAMPLE_LOGGED",
        "TESTING",
        "RESULT_READY",
        "COMPLETED",
    ]

    for idx, stage in enumerate(stages):
        result = test_db.log_event(
            token_id=token_id,
            uid=uid,
            stage=stage,
            device_id=f"station-{idx}",
            session_id=session_id,
        )
        assert result["success"] is True
        assert result["out_of_order"] is False

    assert test_db.get_event_count(session_id) == 6


def test_invalid_first_stage_is_flagged(test_db):
    result = test_db.log_event(
        token_id="002",
        uid="uid-002",
        stage="TESTING",
        device_id="station-x",
        session_id="s1",
    )
    assert result["success"] is True
    assert result["out_of_order"] is True


def test_set_episode_stage_records_audit(test_db):
    test_db.log_event(
        token_id="003",
        uid="uid-003",
        stage="ENTERED",
        device_id="station-entry",
        session_id="s1",
    )

    result = test_db.set_episode_stage(
        token_id="003",
        target_stage="RESULT_READY",
        session_id="s1",
        corrected_by="operator-1",
    )
    assert result["success"] is True
    assert result["from_stage"] == "ENTERED"
    assert result["to_stage"] == "RESULT_READY"

    audit = test_db.conn.execute(
        "SELECT corrected_by, from_stage, to_stage FROM correction_audit WHERE token_id = ?",
        ("003",),
    ).fetchone()
    assert audit is not None
    assert audit["corrected_by"] == "operator-1"
    assert audit["from_stage"] == "ENTERED"
    assert audit["to_stage"] == "RESULT_READY"
