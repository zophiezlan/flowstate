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
    config.admin_password = "test-password-123"
    config.admin_session_timeout_minutes = 60
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


# ===== Authentication Tests =====


def test_control_panel_requires_auth(client):
    """Test that control panel redirects to login when not authenticated"""
    response = client.get("/control")
    assert response.status_code == 302  # Redirect
    assert "/login" in response.location


def test_login_page_loads(client):
    """Test that login page loads successfully"""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Admin Login" in response.data


def test_login_with_valid_password(client, mock_config):
    """Test successful login with correct password"""
    # Set the admin password
    mock_config.admin_password = "testpass123"
    mock_config.admin_session_timeout_minutes = 60

    # Recreate server with updated config
    from tap_station.web_server import StatusWebServer
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    server = StatusWebServer(mock_config, mock_db)
    server.app.config["TESTING"] = True

    with server.app.test_client() as test_client:
        # Try to login
        response = test_client.post(
            "/login", data={"password": "testpass123"}, follow_redirects=False
        )

        assert response.status_code == 302  # Redirect after successful login
        assert "/control" in response.location


def test_login_with_invalid_password(client):
    """Test login failure with incorrect password"""
    response = client.post(
        "/login", data={"password": "wrongpassword"}, follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Invalid password" in response.data


def test_logout_clears_session(client, mock_config):
    """Test that logout clears the session"""
    # Setup authenticated session
    mock_config.admin_password = "testpass123"
    mock_config.admin_session_timeout_minutes = 60

    from tap_station.web_server import StatusWebServer
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    server = StatusWebServer(mock_config, mock_db)
    server.app.config["TESTING"] = True

    with server.app.test_client() as test_client:
        # Login first
        test_client.post("/login", data={"password": "testpass123"})

        # Logout
        response = test_client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

        # Try to access control panel - should redirect to login
        response = test_client.get("/control")
        assert response.status_code == 302
        assert "/login" in response.location


def test_control_api_endpoints_require_auth(client):
    """Test that control API endpoints require authentication"""
    # Test various control endpoints
    endpoints = [
        ("/api/control/status", "GET"),
        ("/api/control/execute", "POST"),
        ("/api/control/force-exit", "POST"),
        ("/api/control/stuck-cards", "GET"),
        ("/api/control/backup-database", "GET"),
        ("/api/control/hardware-status", "GET"),
    ]

    for endpoint, method in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        else:
            response = client.post(
                endpoint, data=json.dumps({}), content_type="application/json"
            )

        # Should redirect to login
        assert response.status_code == 302, f"Endpoint {endpoint} should require auth"
        assert "/login" in response.location


def test_authenticated_control_api_access(client, mock_config):
    """Test that authenticated users can access control API"""
    mock_config.admin_password = "testpass123"
    mock_config.admin_session_timeout_minutes = 60

    from tap_station.web_server import StatusWebServer
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    mock_db.get_event_count.return_value = 100

    server = StatusWebServer(mock_config, mock_db)
    server.app.config["TESTING"] = True

    with server.app.test_client() as test_client:
        # Login first
        test_client.post("/login", data={"password": "testpass123"})

        # Now access control status endpoint
        response = test_client.get("/api/control/status")
        assert response.status_code == 200
        data = response.get_json()
        # Should return status data (exact fields may vary based on system availability)
        assert isinstance(data, dict)
        assert "service_running" in data or "error" in data
