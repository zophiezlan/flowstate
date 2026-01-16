import json
import tempfile
from pathlib import Path

from scripts.ingest_mobile_batch import _load_events, ingest_events
from tap_station.database import Database


import os


def _temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # Close the file descriptor so we can delete the file
    Path(path).unlink()  # Database class will recreate
    return Path(path)


def test_load_events_jsonl(tmp_path):
    data = [
        {
            "token_id": "001",
            "uid": "A1",
            "stage": "QUEUE_JOIN",
            "session_id": "s1",
            "timestamp_ms": 1712000,
        }
    ]
    jsonl = tmp_path / "events.jsonl"
    jsonl.write_text("\n".join(json.dumps(item) for item in data))

    loaded = _load_events(jsonl)
    assert loaded == data


def test_ingest_inserts_and_skips_duplicates(tmp_path):
    db_path = _temp_db_path()
    events = [
        {
            "token_id": "010",
            "uid": "UID010",
            "stage": "queue_join",
            "session_id": "session-x",
            "device_id": "phone-1",
            "timestamp_ms": 1712000,
        },
        {
            "token_id": "010",
            "uid": "UID010",
            "stage": "queue_join",
            "session_id": "session-x",
            "device_id": "phone-1",
            "timestamp_ms": 1712001,
        },
        {
            "token_id": "011",
            "uid": "UID011",
            "stage": "EXIT",
            "session_id": "session-x",
            "device_id": "phone-2",
            "timestamp_ms": 1712002,
        },
    ]

    summary = ingest_events(events, db_path)
    assert summary["inserted"] == 2
    assert summary["duplicates"] == 1

    with Database(str(db_path), wal_mode=True) as db:
        assert db.get_event_count("session-x") == 2
        rows = db.get_recent_events(limit=2)
        assert any(row["stage"] == "QUEUE_JOIN" for row in rows)
        assert any(row["stage"] == "EXIT" for row in rows)


def test_load_events_csv(tmp_path):
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(
        "token_id,uid,stage,session_id,device_id,timestamp_ms\n"
        "001,A1,QUEUE_JOIN,fest,phone-1,1712000\n"
    )

    loaded = _load_events(csv_path)
    assert loaded[0]["token_id"] == "001"
    assert loaded[0]["stage"] == "QUEUE_JOIN"


def test_ingest_handles_mixed_timestamp_formats(tmp_path):
    db_path = _temp_db_path()
    events = [
        {
            "token_id": "020",
            "uid": "U20",
            "stage": "EXIT",
            "session_id": "fest",
            "timestamp": "2024-01-01T00:00:01+00:00",
        },
        {
            "token_id": "021",
            "uid": "U21",
            "stage": "EXIT",
            "session_id": "fest",
            "timestamp_ms": "1712000",
        },
    ]

    summary = ingest_events(events, db_path)
    assert summary["inserted"] == 2
    with Database(str(db_path), wal_mode=True) as db:
        assert db.get_event_count("fest") == 2
