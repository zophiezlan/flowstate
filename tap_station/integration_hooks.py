"""
Integration Hooks System

This module provides a flexible event-driven integration system that allows
the NFC Tap Logger to connect with external systems through:
- Webhooks (HTTP callbacks)
- Event streaming
- Custom handlers
- Export pipelines

Key Features:
- Event-driven architecture
- Retry with exponential backoff
- Event filtering and transformation
- Batch processing support
- Audit logging of integrations

Service Design Principles:
- Loose coupling with external systems
- Reliable delivery with retry logic
- Flexible data transformation
- Observable integration status
"""

import logging
import json
import hashlib
import hmac
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import urllib.request
import urllib.error
import time
import sqlite3

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


class IntegrationEventType(Enum):
    """Types of events that can trigger integrations"""
    # Participant events
    QUEUE_JOIN = "queue_join"
    SERVICE_START = "service_start"
    SUBSTANCE_RETURNED = "substance_returned"
    EXIT = "exit"

    # Operational events
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RESOLVED = "alert_resolved"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    SLO_BREACHED = "slo_breached"

    # Session events
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    SHIFT_HANDOFF = "shift_handoff"

    # System events
    HEALTH_CHECK = "health_check"
    ANOMALY_DETECTED = "anomaly_detected"
    DATA_EXPORT = "data_export"

    # All events wildcard
    ALL = "*"


class DeliveryStatus(Enum):
    """Status of event delivery"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DROPPED = "dropped"


@dataclass
class IntegrationEvent:
    """An event to be delivered to integrations"""
    id: str
    event_type: IntegrationEventType
    timestamp: datetime
    payload: Dict[str, Any]
    source: str = "nfc_tap_logger"
    version: str = "1.0"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for delivery"""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "source": self.source,
            "version": self.version,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint"""
    id: str
    name: str
    url: str
    events: List[IntegrationEventType]
    enabled: bool = True
    secret: Optional[str] = None  # For HMAC signing
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    batch_size: int = 1
    batch_delay_seconds: int = 0
    transform: Optional[str] = None  # JSONPath or jq-like transform
    filter_expression: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "events": [e.value for e in self.events],
            "enabled": self.enabled,
            "has_secret": bool(self.secret),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "batch_size": self.batch_size
        }


@dataclass
class DeliveryResult:
    """Result of an event delivery attempt"""
    webhook_id: str
    event_id: str
    status: DeliveryStatus
    attempt: int
    timestamp: datetime
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "webhook_id": self.webhook_id,
            "event_id": self.event_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "timestamp": self.timestamp.isoformat(),
            "response_code": self.response_code,
            "error": self.error,
            "duration_ms": self.duration_ms
        }


@dataclass
class IntegrationStats:
    """Statistics for an integration"""
    webhook_id: str
    total_events: int = 0
    delivered: int = 0
    failed: int = 0
    retried: int = 0
    avg_latency_ms: float = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        success_rate = (self.delivered / self.total_events * 100) if self.total_events > 0 else 100
        return {
            "webhook_id": self.webhook_id,
            "total_events": self.total_events,
            "delivered": self.delivered,
            "failed": self.failed,
            "retried": self.retried,
            "success_rate": success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_error": self.last_error
        }


class EventTransformer:
    """Transforms events before delivery"""

    @staticmethod
    def transform(event: IntegrationEvent, transform_spec: Optional[str]) -> Dict[str, Any]:
        """
        Transform an event payload according to specification.

        Supported transforms:
        - "flatten": Flatten nested structures
        - "minimal": Only include essential fields
        - "full": Include all fields (default)
        """
        data = event.to_dict()

        if not transform_spec:
            return data

        if transform_spec == "flatten":
            return EventTransformer._flatten(data)
        elif transform_spec == "minimal":
            return {
                "event_type": data["event_type"],
                "timestamp": data["timestamp"],
                "payload": data["payload"]
            }
        elif transform_spec == "full":
            return data
        else:
            # Custom transform - try to evaluate as simple path
            return data

    @staticmethod
    def _flatten(d: Dict, parent_key: str = "", sep: str = "_") -> Dict:
        """Flatten nested dictionary"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(EventTransformer._flatten(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class IntegrationHooksManager:
    """
    Manages integration hooks and event delivery.

    This manager:
    - Registers webhook endpoints
    - Routes events to appropriate webhooks
    - Handles retries with exponential backoff
    - Tracks delivery statistics
    - Supports batch delivery
    """

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        async_delivery: bool = True
    ):
        """
        Initialize the integration hooks manager.

        Args:
            conn: Database connection for persistence
            async_delivery: Use async delivery queue
        """
        self._conn = conn
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._stats: Dict[str, IntegrationStats] = {}
        self._event_counter = 0
        self._delivery_history: List[DeliveryResult] = []
        self._max_history = 1000

        # Custom event handlers
        self._handlers: Dict[IntegrationEventType, List[Callable]] = {}

        # Async delivery
        self._async_delivery = async_delivery
        self._event_queue: queue.Queue = queue.Queue()
        self._delivery_thread: Optional[threading.Thread] = None
        self._running = False

        if async_delivery:
            self._start_delivery_thread()

    def _start_delivery_thread(self) -> None:
        """Start the async delivery thread"""
        self._running = True
        self._delivery_thread = threading.Thread(
            target=self._delivery_worker,
            daemon=True,
            name="integration-delivery"
        )
        self._delivery_thread.start()
        logger.info("Integration delivery thread started")

    def _delivery_worker(self) -> None:
        """Worker thread for async event delivery"""
        while self._running:
            try:
                # Get event with timeout to allow shutdown
                event, webhook_id = self._event_queue.get(timeout=1.0)
                webhook = self._webhooks.get(webhook_id)
                if webhook and webhook.enabled:
                    self._deliver_to_webhook(event, webhook)
                self._event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Delivery worker error: {e}")

    def shutdown(self) -> None:
        """Shutdown the delivery thread and drain pending events"""
        self._running = False
        
        # Try to drain remaining events in the queue with a timeout
        if self._delivery_thread:
            deadline = time.time() + 5.0
            while not self._event_queue.empty() and time.time() < deadline:
                try:
                    event, webhook_id = self._event_queue.get_nowait()
                    webhook = self._webhooks.get(webhook_id)
                    if webhook and webhook.enabled:
                        self._deliver_to_webhook(event, webhook)
                    self._event_queue.task_done()
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error draining event queue during shutdown: {e}")
            
            # Log if we had to drop events
            if not self._event_queue.empty():
                remaining = self._event_queue.qsize()
                logger.warning(f"Dropping {remaining} events during shutdown")
            
            self._delivery_thread.join(timeout=5.0)
            logger.info("Integration delivery thread stopped")

    def register_webhook(self, config: WebhookConfig) -> None:
        """
        Register a webhook endpoint.

        Args:
            config: Webhook configuration
        """
        self._webhooks[config.id] = config
        self._stats[config.id] = IntegrationStats(webhook_id=config.id)
        logger.info(f"Registered webhook: {config.id} ({config.name})")

    def register_webhook_from_dict(self, config: Dict[str, Any]) -> WebhookConfig:
        """
        Register a webhook from configuration dictionary.

        Args:
            config: Dictionary with webhook configuration

        Returns:
            The created WebhookConfig
        """
        events = [
            IntegrationEventType(e) if e != "*" else IntegrationEventType.ALL
            for e in config.get("events", ["*"])
        ]

        webhook = WebhookConfig(
            id=config["id"],
            name=config.get("name", config["id"]),
            url=config["url"],
            events=events,
            enabled=config.get("enabled", True),
            secret=config.get("secret"),
            headers=config.get("headers", {}),
            timeout_seconds=config.get("timeout_seconds", 30),
            max_retries=config.get("max_retries", 3),
            retry_delay_seconds=config.get("retry_delay_seconds", 5),
            batch_size=config.get("batch_size", 1),
            batch_delay_seconds=config.get("batch_delay_seconds", 0),
            transform=config.get("transform"),
            filter_expression=config.get("filter")
        )

        self.register_webhook(webhook)
        return webhook

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister a webhook"""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
            return True
        return False

    def enable_webhook(self, webhook_id: str) -> bool:
        """Enable a webhook"""
        if webhook_id in self._webhooks:
            self._webhooks[webhook_id].enabled = True
            return True
        return False

    def disable_webhook(self, webhook_id: str) -> bool:
        """Disable a webhook"""
        if webhook_id in self._webhooks:
            self._webhooks[webhook_id].enabled = False
            return True
        return False

    def register_handler(
        self,
        event_type: IntegrationEventType,
        handler: Callable[[IntegrationEvent], None]
    ) -> None:
        """
        Register a custom event handler.

        Args:
            event_type: Event type to handle
            handler: Callable that receives the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}")

    def emit(
        self,
        event_type: IntegrationEventType,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IntegrationEvent:
        """
        Emit an integration event.

        Args:
            event_type: Type of event
            payload: Event payload data
            correlation_id: Optional correlation ID for tracing
            metadata: Optional metadata

        Returns:
            The created event
        """
        self._event_counter += 1
        event = IntegrationEvent(
            id=f"evt_{self._event_counter:08d}_{int(time.time() * 1000)}",
            event_type=event_type,
            timestamp=utc_now(),
            payload=payload,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )

        # Invoke custom handlers
        self._invoke_handlers(event)

        # Route to webhooks
        self._route_to_webhooks(event)

        return event

    def emit_tap_event(
        self,
        stage: str,
        token_id: str,
        session_id: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> IntegrationEvent:
        """
        Convenience method to emit a tap event.

        Args:
            stage: Workflow stage
            token_id: Token/card ID
            session_id: Session ID
            extra_data: Additional data

        Returns:
            The created event
        """
        event_type_map = {
            "QUEUE_JOIN": IntegrationEventType.QUEUE_JOIN,
            "SERVICE_START": IntegrationEventType.SERVICE_START,
            "SUBSTANCE_RETURNED": IntegrationEventType.SUBSTANCE_RETURNED,
            "EXIT": IntegrationEventType.EXIT
        }

        event_type = event_type_map.get(stage)
        if not event_type:
            logger.warning(f"Unknown stage for integration event: {stage}")
            return None

        payload = {
            "stage": stage,
            "token_id": token_id,
            "session_id": session_id,
            **(extra_data or {})
        }

        return self.emit(event_type, payload, correlation_id=token_id)

    def emit_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> IntegrationEvent:
        """
        Emit an alert event.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            message: Alert message
            details: Additional details

        Returns:
            The created event
        """
        payload = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "details": details or {}
        }

        return self.emit(IntegrationEventType.ALERT_TRIGGERED, payload)

    def _invoke_handlers(self, event: IntegrationEvent) -> None:
        """Invoke registered handlers for an event"""
        # Specific handlers
        handlers = self._handlers.get(event.event_type, [])
        # Wildcard handlers
        handlers.extend(self._handlers.get(IntegrationEventType.ALL, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.event_type.value}: {e}")

    def _route_to_webhooks(self, event: IntegrationEvent) -> None:
        """Route event to matching webhooks"""
        for webhook in self._webhooks.values():
            if not webhook.enabled:
                continue

            # Check if webhook subscribes to this event
            if IntegrationEventType.ALL not in webhook.events:
                if event.event_type not in webhook.events:
                    continue

            # Check filter expression
            if webhook.filter_expression:
                if not self._evaluate_filter(event, webhook.filter_expression):
                    continue

            # Queue or deliver
            if self._async_delivery:
                self._event_queue.put((event, webhook.id))
            else:
                self._deliver_to_webhook(event, webhook)

    def _evaluate_filter(self, event: IntegrationEvent, filter_expr: str) -> bool:
        """
        Evaluate a filter expression against an event.

        Simple filter syntax: "field=value" or "field!=value"
        """
        try:
            if "!=" in filter_expr:
                field, value = filter_expr.split("!=", 1)
                actual = event.payload.get(field.strip())
                return str(actual) != value.strip()
            elif "=" in filter_expr:
                field, value = filter_expr.split("=", 1)
                actual = event.payload.get(field.strip())
                return str(actual) == value.strip()
            return True
        except Exception:
            return True

    def _deliver_to_webhook(
        self,
        event: IntegrationEvent,
        webhook: WebhookConfig,
        attempt: int = 1
    ) -> DeliveryResult:
        """Deliver an event to a webhook"""
        stats = self._stats.get(webhook.id)
        if stats:
            stats.total_events += 1

        # Transform event
        data = EventTransformer.transform(event, webhook.transform)

        # Prepare request
        body = json.dumps(data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NFC-Tap-Logger/1.0",
            "X-Event-Type": event.event_type.value,
            "X-Event-ID": event.id,
            **webhook.headers
        }

        # Add HMAC signature if secret configured
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            headers["X-Signature"] = f"sha256={signature}"

        start_time = time.time()
        result = DeliveryResult(
            webhook_id=webhook.id,
            event_id=event.id,
            status=DeliveryStatus.PENDING,
            attempt=attempt,
            timestamp=utc_now()
        )

        try:
            request = urllib.request.Request(
                webhook.url,
                data=body,
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(
                request,
                timeout=webhook.timeout_seconds
            ) as response:
                result.response_code = response.getcode()
                result.response_body = response.read().decode("utf-8")[:500]
                result.status = DeliveryStatus.DELIVERED
                result.duration_ms = (time.time() - start_time) * 1000

                if stats:
                    stats.delivered += 1
                    stats.last_success = utc_now()
                    # Update running average latency
                    stats.avg_latency_ms = (
                        (stats.avg_latency_ms * (stats.delivered - 1) + result.duration_ms)
                        / stats.delivered
                    )

        except urllib.error.HTTPError as e:
            result.response_code = e.code
            result.error = str(e)
            result.status = DeliveryStatus.FAILED
            result.duration_ms = (time.time() - start_time) * 1000

            if stats:
                stats.last_failure = utc_now()
                stats.last_error = result.error

        except Exception as e:
            result.error = str(e)
            result.status = DeliveryStatus.FAILED
            result.duration_ms = (time.time() - start_time) * 1000

            if stats:
                stats.last_failure = utc_now()
                stats.last_error = result.error

        # Retry if failed and attempts remaining
        if result.status == DeliveryStatus.FAILED and attempt < webhook.max_retries:
            if stats:
                stats.retried += 1

            result.status = DeliveryStatus.RETRYING
            delay = webhook.retry_delay_seconds * (2 ** (attempt - 1))  # Exponential backoff
            time.sleep(delay)
            return self._deliver_to_webhook(event, webhook, attempt + 1)

        if result.status == DeliveryStatus.FAILED and stats:
            stats.failed += 1

        # Record history
        self._record_delivery(result)

        return result

    def _record_delivery(self, result: DeliveryResult) -> None:
        """Record delivery result in history"""
        self._delivery_history.append(result)
        if len(self._delivery_history) > self._max_history:
            self._delivery_history = self._delivery_history[-self._max_history // 2:]

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get a webhook configuration"""
        return self._webhooks.get(webhook_id)

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks"""
        return [w.to_dict() for w in self._webhooks.values()]

    def get_stats(self, webhook_id: str) -> Optional[IntegrationStats]:
        """Get statistics for a webhook"""
        return self._stats.get(webhook_id)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all webhooks"""
        return {k: v.to_dict() for k, v in self._stats.items()}

    def get_recent_deliveries(
        self,
        webhook_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent delivery history"""
        history = self._delivery_history
        if webhook_id:
            history = [d for d in history if d.webhook_id == webhook_id]
        return [d.to_dict() for d in history[-limit:]]

    def test_webhook(self, webhook_id: str) -> DeliveryResult:
        """
        Send a test event to a webhook.

        Args:
            webhook_id: Webhook to test

        Returns:
            Delivery result
        """
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return DeliveryResult(
                webhook_id=webhook_id,
                event_id="test",
                status=DeliveryStatus.FAILED,
                attempt=1,
                timestamp=utc_now(),
                error="Webhook not found"
            )

        test_event = IntegrationEvent(
            id="test_event",
            event_type=IntegrationEventType.HEALTH_CHECK,
            timestamp=utc_now(),
            payload={
                "test": True,
                "message": "Test event from NFC Tap Logger"
            }
        )

        return self._deliver_to_webhook(test_event, webhook)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall integration health status"""
        total_webhooks = len(self._webhooks)
        enabled_webhooks = sum(1 for w in self._webhooks.values() if w.enabled)

        total_events = sum(s.total_events for s in self._stats.values())
        total_delivered = sum(s.delivered for s in self._stats.values())
        total_failed = sum(s.failed for s in self._stats.values())

        # Calculate overall success rate
        success_rate = (total_delivered / total_events * 100) if total_events > 0 else 100

        # Identify unhealthy webhooks
        unhealthy = [
            webhook_id for webhook_id, stats in self._stats.items()
            if stats.failed > stats.delivered * 0.1  # >10% failure rate
        ]

        return {
            "status": "healthy" if not unhealthy else "degraded",
            "total_webhooks": total_webhooks,
            "enabled_webhooks": enabled_webhooks,
            "total_events_processed": total_events,
            "total_delivered": total_delivered,
            "total_failed": total_failed,
            "overall_success_rate": success_rate,
            "unhealthy_webhooks": unhealthy,
            "queue_size": self._event_queue.qsize() if self._async_delivery else 0
        }


# =============================================================================
# Configuration Loading
# =============================================================================

def load_webhooks_from_config(
    config: Dict[str, Any],
    manager: IntegrationHooksManager
) -> int:
    """
    Load webhook configurations from config dictionary.

    Args:
        config: Configuration with 'webhooks' key
        manager: Integration manager

    Returns:
        Number of webhooks loaded
    """
    webhook_configs = config.get("webhooks", config.get("integrations", {}).get("webhooks", []))
    loaded = 0

    for webhook_config in webhook_configs:
        if not webhook_config.get("enabled", True):
            continue
        try:
            manager.register_webhook_from_dict(webhook_config)
            loaded += 1
        except Exception as e:
            logger.error(f"Error loading webhook {webhook_config.get('id', 'unknown')}: {e}")

    return loaded


# =============================================================================
# Global Instance
# =============================================================================

_hooks_manager: Optional[IntegrationHooksManager] = None


def get_hooks_manager(
    conn: Optional[sqlite3.Connection] = None
) -> IntegrationHooksManager:
    """Get or create the global integration hooks manager"""
    global _hooks_manager
    if _hooks_manager is None:
        _hooks_manager = IntegrationHooksManager(conn)
    return _hooks_manager


def emit_event(
    event_type: IntegrationEventType,
    payload: Dict[str, Any],
    **kwargs
) -> Optional[IntegrationEvent]:
    """Convenience function to emit an event"""
    if _hooks_manager:
        return _hooks_manager.emit(event_type, payload, **kwargs)
    return None
