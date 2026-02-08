"""Tests for extension protocol, registry, and the notes extension."""

import json
from unittest.mock import MagicMock

import pytest

from tap_station.config import Config
from tap_station.extension import Extension, TapEvent
from tap_station.registry import ExtensionRegistry
from tap_station.web_server import StatusWebServer


# --- Extension protocol tests ---


class TestExtensionBase:
    """Test the Extension base class has safe no-op defaults."""

    def test_default_name(self):
        ext = Extension()
        assert ext.name == "unnamed"

    def test_default_order(self):
        ext = Extension()
        assert ext.order == 50

    def test_on_startup_noop(self):
        ext = Extension()
        ext.on_startup({"db": None, "config": None})  # should not raise

    def test_on_shutdown_noop(self):
        ext = Extension()
        ext.on_shutdown()

    def test_on_tap_noop(self):
        ext = Extension()
        event = TapEvent(
            uid="AA",
            token_id="001",
            stage="TEST",
            device_id="d1",
            session_id="s1",
        )
        ext.on_tap(event)

    def test_on_dashboard_stats_noop(self):
        ext = Extension()
        stats = {"count": 5}
        ext.on_dashboard_stats(stats)
        assert stats == {"count": 5}  # unmodified

    def test_on_api_routes_noop(self):
        ext = Extension()
        ext.on_api_routes(None, None, None)


class TestTapEvent:
    """Test TapEvent dataclass."""

    def test_create_event(self):
        event = TapEvent(
            uid="AABB",
            token_id="001",
            stage="QUEUE_JOIN",
            device_id="pi1",
            session_id="s1",
        )
        assert event.uid == "AABB"
        assert event.token_id == "001"
        assert event.extra == {}

    def test_event_mutable(self):
        event = TapEvent(
            uid="AABB",
            token_id="001",
            stage="QUEUE_JOIN",
            device_id="pi1",
            session_id="s1",
        )
        event.stage = "EXIT"
        event.extra["modified_by"] = "test"
        assert event.stage == "EXIT"
        assert event.extra["modified_by"] == "test"


# --- Registry tests ---


class TestExtensionRegistry:
    """Test the ExtensionRegistry loading and dispatch."""

    def test_empty_registry(self):
        reg = ExtensionRegistry()
        assert reg._extensions == []

    def test_load_nonexistent_extension(self):
        reg = ExtensionRegistry()
        reg.load(["nonexistent_extension_xyz"])
        assert reg._extensions == []

    def test_startup_empty(self):
        reg = ExtensionRegistry()
        reg.startup({"db": None})  # should not raise

    def test_shutdown_empty(self):
        reg = ExtensionRegistry()
        reg.shutdown()

    def test_run_on_tap_empty(self):
        reg = ExtensionRegistry()
        event = TapEvent(
            uid="AA",
            token_id="001",
            stage="TEST",
            device_id="d1",
            session_id="s1",
        )
        reg.run_on_tap(event)

    def test_run_on_dashboard_stats_empty(self):
        reg = ExtensionRegistry()
        stats = {"count": 5}
        reg.run_on_dashboard_stats(stats)
        assert stats == {"count": 5}

    def test_extensions_sorted_by_order(self):
        reg = ExtensionRegistry()

        ext_high = Extension()
        ext_high.name = "high"
        ext_high.order = 90

        ext_low = Extension()
        ext_low.name = "low"
        ext_low.order = 10

        reg._extensions = [ext_high, ext_low]
        reg._extensions.sort(key=lambda e: e.order)

        assert reg._extensions[0].name == "low"
        assert reg._extensions[1].name == "high"

    def test_dispatch_catches_errors(self):
        """Extensions that throw should not crash the registry."""
        reg = ExtensionRegistry()

        class BadExtension(Extension):
            name = "bad"

            def on_tap(self, event):
                raise RuntimeError("boom")

        reg._extensions = [BadExtension()]

        event = TapEvent(
            uid="AA",
            token_id="001",
            stage="TEST",
            device_id="d1",
            session_id="s1",
        )
        # Should not raise
        reg.run_on_tap(event)


# --- Notes extension integration test ---


class TestNotesExtension:
    """Test that the notes extension registers routes correctly."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.log_event.return_value = {
            "success": True,
            "duplicate": False,
            "out_of_order": False,
        }
        return db

    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=Config)
        config.device_id = "test-pi"
        config.stage = "TEST"
        config.session_id = "test-session"
        config.admin_password = "test-password"
        config.admin_session_timeout_minutes = 60
        config.extensions_enabled = ["notes"]
        return config

    @pytest.fixture
    def client_with_notes(self, mock_db, mock_config):
        """Create a web server with the notes extension loaded."""
        registry = ExtensionRegistry()

        # Manually load the notes extension
        from extensions.notes import extension as notes_ext

        registry._extensions.append(notes_ext)

        server = StatusWebServer(mock_config, mock_db, registry)

        # Simulate startup so extension gets db/config
        registry.startup(
            {
                "db": mock_db,
                "config": mock_config,
                "nfc": None,
                "app": server.app,
            }
        )

        server.app.config["TESTING"] = True
        with server.app.test_client() as client:
            yield client

    def test_notes_route_exists(self, client_with_notes):
        """GET /api/notes should return 200."""
        # Mock the cursor for the GET
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        # The notes extension uses db.conn.execute
        from extensions.notes import extension as notes_ext

        notes_ext.db.conn.execute.return_value = mock_cursor

        response = client_with_notes.get("/api/notes")
        assert response.status_code == 200
        data = response.get_json()
        assert "notes" in data
        assert data["notes"] == []

    def test_notes_post(self, client_with_notes, mock_db):
        """POST /api/notes should add a note."""
        response = client_with_notes.post(
            "/api/notes",
            data=json.dumps({"note": "Test note", "author": "tester"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

    def test_notes_post_empty(self, client_with_notes):
        """POST /api/notes with empty note should return 400."""
        response = client_with_notes.post(
            "/api/notes",
            data=json.dumps({"note": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_notes_not_on_core_server(self):
        """Without the extension, /api/notes should 404."""
        db = MagicMock()
        config = MagicMock(spec=Config)
        config.device_id = "test-pi"
        config.stage = "TEST"
        config.session_id = "test-session"
        config.admin_password = "test-password"
        config.admin_session_timeout_minutes = 60

        # No registry = no extensions = no /api/notes
        server = StatusWebServer(config, db)
        server.app.config["TESTING"] = True

        with server.app.test_client() as client:
            response = client.get("/api/notes")
            assert response.status_code == 404
