import os
import tempfile

import pytest

from tap_station.database import Database
from tap_station.web_server import StatusWebServer


class TestConfig:
    device_id = "test-pi"
    stage = "ENTERED"
    session_id = "test-session"
    admin_password = "test-password-123"


@pytest.fixture
def server_and_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path, wal_mode=True)
    server = StatusWebServer(TestConfig, db)
    server.app.config["TESTING"] = True
    with server.app.test_client() as client:
        yield client, db
    db.close()
    for ext in ["", "-wal", "-shm"]:
        p = path + ext
        if os.path.exists(p):
            os.unlink(p)


def test_health_and_readiness_endpoints(server_and_db):
    client, _ = server_and_db
    assert client.get("/health").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_api_stages(server_and_db):
    client, _ = server_and_db
    response = client.get("/api/stages")
    assert response.status_code == 200
    assert response.get_json()["stages"] == [
        "ENTERED",
        "FIRST_CONTACT",
        "SAMPLE_LOGGED",
        "TESTING",
        "RESULT_READY",
        "COMPLETED",
    ]


def test_api_ingest_and_dashboard_and_export(server_and_db):
    client, _ = server_and_db

    payload = [
        {"token_id": "001", "uid": "u-001", "stage": "ENTERED"},
        {"token_id": "001", "uid": "u-001", "stage": "FIRST_CONTACT"},
    ]
    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["inserted"] == 2

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.get_json()
    assert data["active_count"] == 1
    assert data["counts_per_stage"]["FIRST_CONTACT"] == 1

    export = client.get("/api/export.csv")
    assert export.status_code == 200
    assert "token_id,stage,timestamp,device_id,session_id" in export.get_data(as_text=True)


def test_api_ingest_rejects_non_entry_first_scan(server_and_db):
    client, _ = server_and_db
    response = client.post(
        "/api/ingest",
        json={"token_id": "002", "uid": "u-002", "stage": "TESTING"},
    )
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["inserted"] == 0
    assert summary["errors"] == 1


def test_admin_login_and_correct_stage_records_audit(server_and_db):
    client, db = server_and_db

    client.post(
        "/api/ingest",
        json={"token_id": "001", "uid": "u-001", "stage": "ENTERED"},
    )

    # Requires auth
    unauth = client.post(
        "/api/admin/correct-stage",
        json={"token_id": "001", "target_stage": "TESTING", "corrected_by": "op1"},
    )
    assert unauth.status_code == 401

    login = client.post("/api/admin/login", json={"password": "test-password-123"})
    assert login.status_code == 200

    correction = client.post(
        "/api/admin/correct-stage",
        json={"token_id": "001", "target_stage": "TESTING", "corrected_by": "op1"},
    )
    assert correction.status_code == 200
    payload = correction.get_json()
    assert payload["from_stage"] == "ENTERED"
    assert payload["to_stage"] == "TESTING"

    row = db.conn.execute(
        "SELECT corrected_by, from_stage, to_stage FROM correction_audit WHERE token_id = ?",
        ("001",),
    ).fetchone()
    assert row is not None
    assert row["corrected_by"] == "op1"
    assert row["from_stage"] == "ENTERED"
    assert row["to_stage"] == "TESTING"
