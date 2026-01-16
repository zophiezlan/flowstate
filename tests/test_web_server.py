import pytest
import json
from unittest.mock import MagicMock
from tap_station.web_server import StatusWebServer
from tap_station.config import Config


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_event_count.return_value = 100
    db.log_event.return_value = True
    return db


@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.device_id = "test-pi"
    config.stage = "TEST"
    config.session_id = "test-session"
    return config


@pytest.fixture
def client(mock_db, mock_config):
    server = StatusWebServer(mock_config, mock_db)
    server.app.config["TESTING"] = True
    with server.app.test_client() as client:
        yield client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["device_id"] == "test-pi"


def test_api_ingest_success(client, mock_db):
    payload = [{"token_id": "001", "uid": "AABB", "timestamp_ms": 1700000000000}]
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["summary"]["inserted"] == 1

    # Verify mock call
    mock_db.log_event.assert_called_once()
    call_args = mock_db.log_event.call_args[1]
    assert call_args["token_id"] == "001"
    assert call_args["uid"] == "AABB"
    # Verify timestamp conversion (1700000000000 ms -> datetime)
    assert call_args["timestamp"].timestamp() == 1700000000.0


def test_api_ingest_invalid_format(client):
    response = client.post(
        "/api/ingest",
        data=json.dumps({"not": "a list"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_ingest_duplicate_counting(client, mock_db):
    # Mock log_event to return False (duplicate)
    mock_db.log_event.return_value = False

    payload = [{"token_id": "001"}]
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    data = response.get_json()
    assert data["summary"]["inserted"] == 0
    assert data["summary"]["duplicates"] == 1


def test_api_ingest_payload_too_large(client):
    """Test that payloads over 1000 events are rejected"""
    payload = [{"token_id": f"{i:03d}"} for i in range(1001)]
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 413
    data = response.get_json()
    assert "Too many events" in data["error"]


def test_api_ingest_empty_payload(client):
    """Test that empty payloads are rejected"""
    payload = []
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "Empty event list" in data["error"]


def test_api_ingest_invalid_event_type(client, mock_db):
    """Test that non-dict events are counted as errors"""
    payload = ["not a dict", 123, None]
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["errors"] == 3
    assert data["summary"]["inserted"] == 0


def test_api_ingest_field_length_validation(client, mock_db):
    """Test that overly long fields are rejected"""
    payload = [{"token_id": "A" * 101, "uid": "test"}]  # Token ID too long
    response = client.post(
        "/api/ingest", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["errors"] == 1
    assert data["summary"]["inserted"] == 0
