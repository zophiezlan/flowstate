"""
Tests for the Integration Hooks System

Tests cover:
- Webhook registration
- Event emission
- Event routing
- Delivery status tracking
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.integration_hooks import (
    IntegrationHooksManager,
    IntegrationEvent,
    WebhookConfig,
    DeliveryResult,
    DeliveryStatus,
    IntegrationEventType,
    IntegrationStats,
    EventTransformer,
    get_hooks_manager,
    load_webhooks_from_config,
    emit_event,
)


@pytest.fixture
def manager():
    """Create an integration hooks manager with sync delivery"""
    return IntegrationHooksManager(async_delivery=False)


@pytest.fixture
def webhook_config():
    """Create a basic webhook configuration"""
    return WebhookConfig(
        id="test_webhook",
        name="Test Webhook",
        url="https://example.com/webhook",
        events=[IntegrationEventType.ALL],
        enabled=True
    )


class TestIntegrationEvent:
    """Tests for IntegrationEvent dataclass"""

    def test_creation(self):
        """Test event creation"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.QUEUE_JOIN,
            timestamp=datetime.utcnow(),
            payload={"token_id": "token_001"}
        )
        assert event.id == "evt_001"
        assert event.event_type == IntegrationEventType.QUEUE_JOIN

    def test_to_dict(self):
        """Test event serialization"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.EXIT,
            timestamp=datetime.utcnow(),
            payload={"stage": "EXIT"},
            correlation_id="token_001"
        )
        d = event.to_dict()

        assert d["id"] == "evt_001"
        assert d["event_type"] == "exit"
        assert d["correlation_id"] == "token_001"

    def test_to_json(self):
        """Test JSON serialization"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.ALERT_TRIGGERED,
            timestamp=datetime.utcnow(),
            payload={"alert": "test"}
        )
        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == "evt_001"


class TestWebhookConfig:
    """Tests for WebhookConfig dataclass"""

    def test_to_dict(self):
        """Test config serialization"""
        config = WebhookConfig(
            id="webhook_1",
            name="Webhook 1",
            url="https://example.com",
            events=[IntegrationEventType.QUEUE_JOIN, IntegrationEventType.EXIT],
            secret="secret123"
        )
        d = config.to_dict()

        assert d["id"] == "webhook_1"
        assert d["has_secret"] is True
        assert len(d["events"]) == 2


class TestEventTransformer:
    """Tests for EventTransformer"""

    def test_transform_full(self):
        """Test full transformation (no change)"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.QUEUE_JOIN,
            timestamp=datetime.utcnow(),
            payload={"test": "data"}
        )
        result = EventTransformer.transform(event, "full")
        assert result == event.to_dict()

    def test_transform_minimal(self):
        """Test minimal transformation"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.QUEUE_JOIN,
            timestamp=datetime.utcnow(),
            payload={"test": "data"},
            metadata={"extra": "info"}
        )
        result = EventTransformer.transform(event, "minimal")

        assert "event_type" in result
        assert "timestamp" in result
        assert "payload" in result
        assert "metadata" not in result

    def test_transform_flatten(self):
        """Test flatten transformation"""
        event = IntegrationEvent(
            id="evt_001",
            event_type=IntegrationEventType.QUEUE_JOIN,
            timestamp=datetime.utcnow(),
            payload={"nested": {"value": 123}}
        )
        result = EventTransformer.transform(event, "flatten")

        # Should have flattened keys
        assert any("_" in key for key in result.keys())


class TestIntegrationHooksManager:
    """Tests for IntegrationHooksManager"""

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert len(manager._webhooks) == 0

    def test_register_webhook(self, manager, webhook_config):
        """Test webhook registration"""
        manager.register_webhook(webhook_config)
        assert "test_webhook" in manager._webhooks

    def test_register_webhook_from_dict(self, manager):
        """Test webhook registration from dict"""
        config = {
            "id": "dict_webhook",
            "name": "Dict Webhook",
            "url": "https://example.com/hook",
            "events": ["queue_join", "exit"],
            "enabled": True
        }
        webhook = manager.register_webhook_from_dict(config)

        assert webhook.id == "dict_webhook"
        assert IntegrationEventType.QUEUE_JOIN in webhook.events

    def test_unregister_webhook(self, manager, webhook_config):
        """Test webhook unregistration"""
        manager.register_webhook(webhook_config)
        result = manager.unregister_webhook("test_webhook")

        assert result is True
        assert "test_webhook" not in manager._webhooks

    def test_enable_disable_webhook(self, manager, webhook_config):
        """Test enabling/disabling webhook"""
        manager.register_webhook(webhook_config)

        manager.disable_webhook("test_webhook")
        assert manager._webhooks["test_webhook"].enabled is False

        manager.enable_webhook("test_webhook")
        assert manager._webhooks["test_webhook"].enabled is True

    def test_emit_event(self, manager):
        """Test event emission"""
        event = manager.emit(
            event_type=IntegrationEventType.QUEUE_JOIN,
            payload={"token_id": "token_001"}
        )

        assert event is not None
        assert event.event_type == IntegrationEventType.QUEUE_JOIN

    def test_emit_tap_event(self, manager):
        """Test tap event emission"""
        event = manager.emit_tap_event(
            stage="QUEUE_JOIN",
            token_id="token_001",
            session_id="session1"
        )

        assert event is not None
        assert event.payload["stage"] == "QUEUE_JOIN"
        assert event.correlation_id == "token_001"

    def test_emit_alert(self, manager):
        """Test alert emission"""
        event = manager.emit_alert(
            alert_type="queue_warning",
            severity="warning",
            message="Queue is getting long"
        )

        assert event is not None
        assert event.event_type == IntegrationEventType.ALERT_TRIGGERED

    def test_list_webhooks(self, manager, webhook_config):
        """Test listing webhooks"""
        manager.register_webhook(webhook_config)
        webhooks = manager.list_webhooks()

        assert len(webhooks) == 1
        assert webhooks[0]["id"] == "test_webhook"

    def test_get_stats(self, manager, webhook_config):
        """Test getting webhook stats"""
        manager.register_webhook(webhook_config)
        stats = manager.get_stats("test_webhook")

        assert stats is not None
        assert stats.total_events == 0

    def test_get_all_stats(self, manager, webhook_config):
        """Test getting all stats"""
        manager.register_webhook(webhook_config)
        all_stats = manager.get_all_stats()

        assert "test_webhook" in all_stats

    def test_get_recent_deliveries(self, manager):
        """Test getting delivery history"""
        deliveries = manager.get_recent_deliveries()
        assert isinstance(deliveries, list)

    def test_get_health_status(self, manager, webhook_config):
        """Test health status"""
        manager.register_webhook(webhook_config)
        health = manager.get_health_status()

        assert "status" in health
        assert health["total_webhooks"] == 1

    def test_register_handler(self, manager):
        """Test custom handler registration"""
        events_received = []

        def handler(event):
            events_received.append(event)

        manager.register_handler(IntegrationEventType.QUEUE_JOIN, handler)
        manager.emit(IntegrationEventType.QUEUE_JOIN, {"test": "data"})

        assert len(events_received) == 1

    def test_wildcard_handler(self, manager):
        """Test wildcard handler receives all events"""
        events_received = []

        def handler(event):
            events_received.append(event)

        manager.register_handler(IntegrationEventType.ALL, handler)
        manager.emit(IntegrationEventType.QUEUE_JOIN, {})
        manager.emit(IntegrationEventType.EXIT, {})

        assert len(events_received) == 2


class TestEventFiltering:
    """Tests for event filtering"""

    def test_filter_matches(self, manager):
        """Test filter expression matching"""
        result = manager._evaluate_filter(
            IntegrationEvent(
                id="test",
                event_type=IntegrationEventType.QUEUE_JOIN,
                timestamp=datetime.utcnow(),
                payload={"stage": "QUEUE_JOIN"}
            ),
            "stage=QUEUE_JOIN"
        )
        assert result is True

    def test_filter_not_matches(self, manager):
        """Test filter expression not matching"""
        result = manager._evaluate_filter(
            IntegrationEvent(
                id="test",
                event_type=IntegrationEventType.QUEUE_JOIN,
                timestamp=datetime.utcnow(),
                payload={"stage": "EXIT"}
            ),
            "stage=QUEUE_JOIN"
        )
        assert result is False

    def test_filter_not_equals(self, manager):
        """Test not-equals filter"""
        result = manager._evaluate_filter(
            IntegrationEvent(
                id="test",
                event_type=IntegrationEventType.QUEUE_JOIN,
                timestamp=datetime.utcnow(),
                payload={"stage": "EXIT"}
            ),
            "stage!=QUEUE_JOIN"
        )
        assert result is True


class TestDeliveryResult:
    """Tests for DeliveryResult dataclass"""

    def test_to_dict(self):
        """Test result serialization"""
        result = DeliveryResult(
            webhook_id="webhook_1",
            event_id="evt_001",
            status=DeliveryStatus.DELIVERED,
            attempt=1,
            timestamp=datetime.utcnow(),
            response_code=200,
            duration_ms=150.5
        )
        d = result.to_dict()

        assert d["webhook_id"] == "webhook_1"
        assert d["status"] == "delivered"
        assert d["response_code"] == 200


class TestIntegrationStats:
    """Tests for IntegrationStats dataclass"""

    def test_to_dict(self):
        """Test stats serialization"""
        stats = IntegrationStats(
            webhook_id="webhook_1",
            total_events=100,
            delivered=95,
            failed=5,
            avg_latency_ms=150.0
        )
        d = stats.to_dict()

        assert d["total_events"] == 100
        assert d["success_rate"] == 95.0


class TestWebhookDelivery:
    """Tests for webhook delivery (mocked)"""

    @patch('urllib.request.urlopen')
    def test_successful_delivery(self, mock_urlopen, manager, webhook_config):
        """Test successful webhook delivery"""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        manager.register_webhook(webhook_config)
        event = IntegrationEvent(
            id="test_evt",
            event_type=IntegrationEventType.QUEUE_JOIN,
            timestamp=datetime.utcnow(),
            payload={}
        )

        result = manager._deliver_to_webhook(event, webhook_config)
        assert result.status == DeliveryStatus.DELIVERED

    @patch('urllib.request.urlopen')
    def test_test_webhook(self, mock_urlopen, manager, webhook_config):
        """Test webhook testing"""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        manager.register_webhook(webhook_config)
        result = manager.test_webhook("test_webhook")

        assert result.status == DeliveryStatus.DELIVERED


class TestConfigurationLoading:
    """Tests for configuration loading"""

    def test_load_webhooks_from_config(self):
        """Test loading webhooks from config"""
        manager = IntegrationHooksManager(async_delivery=False)
        config = {
            "webhooks": [
                {
                    "id": "config_webhook",
                    "name": "Config Webhook",
                    "url": "https://example.com/hook",
                    "events": ["queue_join"],
                    "enabled": True
                }
            ]
        }

        loaded = load_webhooks_from_config(config, manager)
        assert loaded == 1
        assert "config_webhook" in manager._webhooks


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_hooks_manager(self):
        """Test global manager retrieval"""
        module = sys.modules["tap_station.integration_hooks"]
        module._hooks_manager = None

        manager = get_hooks_manager()
        assert manager is not None

        manager2 = get_hooks_manager()
        assert manager is manager2

    def test_emit_event_function(self):
        """Test emit_event convenience function"""
        module = sys.modules["tap_station.integration_hooks"]
        module._hooks_manager = None

        # Get manager first
        get_hooks_manager()

        event = emit_event(IntegrationEventType.HEALTH_CHECK, {"test": True})
        assert event is not None


class TestAsyncDelivery:
    """Tests for async delivery functionality"""

    def test_async_manager_starts_thread(self):
        """Test async manager starts delivery thread"""
        manager = IntegrationHooksManager(async_delivery=True)
        assert manager._running is True
        assert manager._delivery_thread is not None

        manager.shutdown()
        assert manager._running is False

    def test_sync_manager_no_thread(self):
        """Test sync manager doesn't start thread"""
        manager = IntegrationHooksManager(async_delivery=False)
        assert manager._delivery_thread is None
